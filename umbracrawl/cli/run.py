"""Deep crawl loop: uncapped frontier, 4 workers, SQLite throughout."""
from __future__ import annotations

import re
from concurrent.futures import ThreadPoolExecutor

from .. import extract as _extract
from .. import search as _search
from .. import storage
from ..fetchers import http_impersonate as _http
from ..identity import fingerprints, leakcheck, proxies, sessions
from ..scheduler import politeness, queue

WORKERS = 4


def _tokens(query: str) -> set[str]:
    return {t for t in re.findall(r"[a-z0-9]+", query.lower()) if len(t) > 2}


def in_scope(query: str, url: str, title: str = "") -> bool:
    toks = _tokens(query)
    if not toks:
        return True
    hay = f"{url} {title}".lower()
    return any(t in hay for t in toks)


def _crawl_one(args: tuple) -> dict:
    tid, url, depth, gate, ident = args
    gate.wait(url)
    try:
        res = _http.fetch(url, cookies=ident["cookies"],
                          proxy=ident["proxy"], headers=ident["headers"])
    except Exception as e:
        return {"tid": tid, "ok": False, "error": str(e)[:120]}
    blocked, reason = _http.is_challenge(res["status"], res["text"])
    if blocked:
        return {"tid": tid, "ok": False, "error": f"challenge:{reason}"}
    try:
        page = _extract.extract(url, res["text"])
    except Exception as e:
        return {"tid": tid, "ok": False, "error": f"parse:{e}"[:120]}
    return {"tid": tid, "ok": True, "page": page,
            "cookies": res.get("cookies", {})}


def research(query: str, db_path: str, max_workers: int = WORKERS,
             fetcher=None, proxy_list: list[str] | None = None) -> dict:
    con = storage.connect(db_path)
    gate = politeness.Gate()
    pool = sessions.SessionPool(con)
    px = proxies.ProxyPool(proxy_list)
    profile = fingerprints.pick_profile()
    headers = fingerprints.headers_for(profile)
    env = {"webdriver": None, "cdp_keys": [],
           "webgl_renderer": profile["webgl"],
           "profile_renderer": profile["webgl"],
           "headers": list(headers)}
    assert leakcheck.gate(env), "identity failed leak gate"
    seeds = _search.search_links(query)
    queue.add_urls(con, seeds, 0, storage)
    pages = blocked = 0
    with ThreadPoolExecutor(max_workers=max_workers) as ex:
        while storage.pending(con):
            batch = storage.lease(con, max_workers)
            if not batch:
                break
            args = []
            for (t0, url, depth, _) in batch:
                ses = pool.checkout()
                ident = {"cookies": ses.cookies,
                         "proxy": px.checkout(ses.sid), "headers": headers,
                         "sid": ses.sid}
                args.append((t0, url, depth, gate, ident))
            for out, (_, url, _, _, ident) in zip(ex.map(_crawl_one, args), args):
                px.report(ident["proxy"], out["ok"])
                if out["ok"]:
                    p = out["page"]
                    pool.save_cookies(ident["sid"], out["cookies"])
                    meta = {"description": p["description"]}
                    storage.store_item(con, p["url"], p["title"], p["text"], meta)
                    storage.mark(con, out["tid"], "done")
                    depth = con.execute(
                        "SELECT depth FROM tasks WHERE id=?",
                        (out["tid"],)).fetchone()[0]
                    kids = [u for (u, t) in p["links"]
                            if in_scope(query, u, t)]
                    queue.add_urls(con, kids, depth + 1, storage)
                    pages += 1
                else:
                    if out["error"].startswith("challenge"):
                        pool.note_challenge(ident["sid"])
                        storage.mark(con, out["tid"], "poison")
                        blocked += 1
                    else:
                        storage.mark(con, out["tid"], "failed")
    con.close()
    return {"query": query, "pages": pages, "blocked": blocked, "db": db_path}
