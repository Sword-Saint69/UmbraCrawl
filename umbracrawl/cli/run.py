"""Deep crawl loop: uncapped frontier, 4 workers, SQLite throughout."""
from __future__ import annotations

import re
from concurrent.futures import ThreadPoolExecutor

from .. import extract as _extract
from .. import search as _search
from .. import storage
from ..fetchers import camoufox_pool, http_impersonate as _http
from ..fetchers import router as _router
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
    tid, url, depth, attempts, challenges, gate, ident, slot = args
    gate.wait(url)
    try:
        res = _http.fetch(url, cookies=ident["cookies"],
                          proxy=ident["proxy"], headers=ident["headers"])
    except Exception as e:
        return {"tid": tid, "ok": False, "error": str(e)[:120]}
    status, text = res.get("status", 0), res.get("text", "")
    blocked, reason = _http.is_challenge(status, text)
    if blocked:
        decision = _router.route(challenges + 1, attempts)
        if decision == "http":
            return {"tid": tid, "ok": False, "challenge": True,
                    "error": f"challenge:{reason}", "retry": True}
        if decision == "browser":
            if slot is not None and slot.available():
                try:
                    res = slot.fetch(url, ident.get("profile"), ident["proxy"])
                except Exception as e:
                    return {"tid": tid, "ok": False, "challenge": True,
                            "error": f"browser:{e}"[:120]}
                st2, tx2 = res.get("status", 200), res.get("text", "")
                blocked2, _ = _http.is_challenge(st2, tx2)
                if blocked2 or _http.is_thin(st2, tx2):
                    return {"tid": tid, "ok": False, "challenge": True,
                            "error": "challenge:browser-walled"}
                try:
                    page = _extract.extract(url, tx2)
                except Exception as e:
                    return {"tid": tid, "ok": False,
                            "error": f"parse:{e}"[:120]}
                return {"tid": tid, "ok": True, "page": page,
                        "cookies": res.get("cookies", {}), "escalated": True}
            return {"tid": tid, "ok": False, "challenge": True,
                    "error": "challenge:no-browser"}
        return {"tid": tid, "ok": False, "challenge": True,
                "error": f"challenge:{reason}"}
    if not (200 <= status < 300):
        return {"tid": tid, "ok": False, "error": f"http-{status}"}
    try:
        page = _extract.extract(url, text)
    except Exception as e:
        return {"tid": tid, "ok": False, "error": f"parse:{e}"[:120]}
    return {"tid": tid, "ok": True, "page": page,
            "cookies": res.get("cookies", {})}


def research(query: str, db_path: str, max_workers: int = WORKERS,
             fetcher=None, proxy_list: list[str] | None = None,
             browser_slot=None, fresh: bool = False) -> dict:
    con = storage.connect(db_path)
    try:
        return _run(query, con, max_workers, proxy_list, browser_slot,
                    fresh, db_path)
    finally:
        con.close()


def _run(query: str, con, max_workers: int, proxy_list, browser_slot,
         fresh: bool, db_path: str) -> dict:
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
    if browser_slot is None:
        browser_slot = camoufox_pool.BrowserSlot()
    if fresh:
        con.execute("UPDATE tasks SET status='queued', attempts=0,"
                    " challenges=0, note='' WHERE status != 'queued'")
        con.commit()
    seeds = _search.search_links(query)
    queue.add_urls(con, seeds, 0, storage)
    pages = blocked = escalated = 0
    with ThreadPoolExecutor(max_workers=max_workers) as ex:
        while storage.pending(con):
            batch = storage.lease(con, max_workers)
            if not batch:
                break
            args = []
            for (t0, url, depth, attempts, challenges) in batch:
                ses = pool.checkout()
                ident = {"cookies": ses.cookies,
                         "proxy": px.checkout(ses.sid), "headers": headers,
                         "profile": profile, "sid": ses.sid}
                args.append((t0, url, depth, attempts, challenges, gate,
                             ident, browser_slot))
            for out, arg in zip(ex.map(_crawl_one, args), args):
                ident = arg[6]
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
                    escalated += bool(out.get("escalated"))
                elif out.get("challenge"):
                    con.execute("UPDATE tasks SET challenges=challenges+1"
                                " WHERE id=?", (out["tid"],))
                    pool.note_challenge(ident["sid"])
                    if out.get("retry"):
                        con.execute("UPDATE tasks SET status='queued'"
                                    " WHERE id=?", (out["tid"],))
                    else:
                        con.execute("UPDATE tasks SET status='poison',"
                                    " note=? WHERE id=?",
                                    (out["error"][:120], out["tid"]))
                        blocked += 1
                    con.commit()
                else:
                    con.execute("UPDATE tasks SET status='failed', note=?"
                                " WHERE id=?",
                                (out["error"][:120], out["tid"]))
                    con.commit()
    return {"query": query, "pages": pages, "blocked": blocked,
            "escalated": escalated, "db": db_path}
