"""Deep crawl loop: uncapped frontier, 4 workers, SQLite throughout."""
from __future__ import annotations

import re
import time
from concurrent.futures import ThreadPoolExecutor

from .. import extract as _extract
from .. import search as _search
from .. import storage
from ..fetchers import camoufox_pool, http_impersonate as _http
from ..fetchers import patchright_pool
from ..fetchers import router as _router
from ..identity import fingerprints, leakcheck, proxies, sessions
from ..observability import metrics as _metrics
from ..scheduler import politeness, queue

try:
    from ..parser import adaptive as _adaptive
    from ..parser import markdown as _md
    from ..parser import relearn as _relearn
    HAVE_PARSER = True
except ImportError:
    HAVE_PARSER = False

WORKERS = 4

_SPECS = None


def _specs() -> dict:
    global _SPECS
    if _SPECS is None:
        _SPECS = {}
        if HAVE_PARSER:
            try:
                import pathlib
                import yaml
                p = pathlib.Path(__file__).parent.parent / "parser" \
                    / "selectors.yml"
                _SPECS = yaml.safe_load(p.read_text())["fields"]
            except Exception:
                _SPECS = {}
    return _SPECS


def _enrich(url: str, text: str, page: dict) -> dict:
    page["html"] = text[:50000]  # snapshot budget: relearn needs source
    if HAVE_PARSER and _specs():
        fields = _adaptive.extract_fields(text, _specs())
        page["fields"] = {f: v["value"] for f, v in fields.items() if v}
        page["missing"] = [f for f, v in fields.items() if not v]
        page["markdown"] = _md.to_markdown(url, text)
    else:
        page["fields"], page["missing"] = {}, []
        page["markdown"] = ""
    return page


def _tokens(query: str) -> set[str]:
    return {t for t in re.findall(r"[a-z0-9]+", query.lower()) if len(t) > 2}


def in_scope(query: str, url: str, title: str = "") -> bool:
    toks = _tokens(query)
    if not toks:
        return True
    hay = f"{url} {title}".lower()
    return any(t in hay for t in toks)


def _crawl_one(args: tuple) -> dict:
    tid, url, depth, attempts, challenges, gate, ident, slots, met = args
    gate.wait(url)
    met.event("fetch", url=url)
    try:
        res = _http.fetch(url, cookies=ident["cookies"],
                          proxy=ident["proxy"], headers=ident["headers"])
    except Exception as e:
        return {"tid": tid, "ok": False, "error": str(e)[:120]}
    status, text = res.get("status", 0), res.get("text", "")
    blocked, reason = _http.is_challenge(status, text)
    if blocked:
        met.event("challenge", url=url, reason=reason)
        decision = _router.route(challenges + 1, attempts)
        if decision == "http":
            return {"tid": tid, "ok": False, "challenge": True,
                    "error": f"challenge:{reason}", "retry": True}
        if decision == "browser":
            seen_backend = False
            for slot in slots:
                if slot is None or not slot.available():
                    continue
                seen_backend = True
                try:
                    res = slot.fetch(url, ident.get("profile"),
                                     ident["proxy"])
                except Exception as e:
                    return {"tid": tid, "ok": False, "challenge": True,
                            "error": f"browser:{e}"[:120]}
                st2, tx2 = res.get("status", 200), res.get("text", "")
                blocked2, _ = _http.is_challenge(st2, tx2)
                if blocked2 or _http.is_thin(st2, tx2):
                    continue  # next backend in the chain
                try:
                    page = _enrich(url, tx2, _extract.extract(url, tx2))
                except Exception as e:
                    return {"tid": tid, "ok": False,
                            "error": f"parse:{e}"[:120]}
                met.event("escalated", url=url,
                          backend=res.get("backend", "?"))
                return {"tid": tid, "ok": True, "page": page,
                        "cookies": res.get("cookies", {}), "escalated": True}
            if not seen_backend:
                return {"tid": tid, "ok": False, "challenge": True,
                        "error": "challenge:no-browser"}
            return {"tid": tid, "ok": False, "challenge": True,
                    "error": "challenge:browser-walled"}
        return {"tid": tid, "ok": False, "challenge": True,
                "error": f"challenge:{reason}"}
    if not (200 <= status < 300):
        return {"tid": tid, "ok": False, "error": f"http-{status}"}
    try:
        page = _enrich(url, text, _extract.extract(url, text))
    except Exception as e:
        return {"tid": tid, "ok": False, "error": f"parse:{e}"[:120]}
    return {"tid": tid, "ok": True, "page": page,
            "cookies": res.get("cookies", {})}


def research(query: str, db_path: str, max_workers: int = WORKERS,
             fetcher=None, proxy_list: list[str] | None = None,
             browser_slot=None, fresh: bool = False, max_pages: int = 0,
             max_depth: int = 0, timeout: int = 0) -> dict:
    con = storage.connect(db_path)
    try:
        return _run(query, con, max_workers, proxy_list, browser_slot,
                    fresh, db_path, max_pages, max_depth, timeout)
    finally:
        con.close()


def _run(query: str, con, max_workers: int, proxy_list, browser_slot,
         fresh: bool, db_path: str, max_pages: int, max_depth: int,
         timeout: int) -> dict:
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
        slots = [camoufox_pool.BrowserSlot(), patchright_pool.BrowserSlot()]
    elif isinstance(browser_slot, list):
        slots = browser_slot
    else:
        slots = [browser_slot]
    met = _metrics.Metrics(db_path + ".metrics.jsonl")
    if fresh:
        con.execute("UPDATE tasks SET status='queued', attempts=0,"
                    " challenges=0, note='' WHERE status != 'queued'")
        con.commit()
    else:
        storage.recover(con)  # crashed run left rows leased: requeue them
    seeds = _search.search_links(query)
    queue.add_urls(con, seeds, 0, storage)
    pages = blocked = escalated = 0
    deadline = time.time() + timeout if timeout else 0.0
    with ThreadPoolExecutor(max_workers=max_workers) as ex:
        while storage.pending(con):
            if max_pages and pages >= max_pages:
                break
            if deadline and time.time() >= deadline:
                break
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
                             ident, slots, met))
            for out, arg in zip(ex.map(_crawl_one, args), args):
                ident = arg[6]
                px.report(ident["proxy"], out["ok"])
                if out["ok"]:
                    p = out["page"]
                    pool.save_cookies(ident["sid"], out["cookies"])
                    meta = {"description": p["description"],
                            "fields": p.get("fields", {}),
                            "markdown": p.get("markdown", "")}
                    if HAVE_PARSER and p.get("missing"):
                        _relearn.snapshot(con, p["url"], p.get("html", ""),
                                          p["missing"])
                    storage.store_item(con, p["url"], p["title"], p["text"], meta)
                    storage.mark(con, out["tid"], "done")
                    depth = con.execute(
                        "SELECT depth FROM tasks WHERE id=?",
                        (out["tid"],)).fetchone()[0]
                    kids = [u for (u, t) in p["links"]
                            if in_scope(query, u, t)]
                    if not max_depth or depth + 1 <= max_depth:
                        queue.add_urls(con, kids, depth + 1, storage)
                    pages += 1
                    met.event("page", url=p["url"])
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
                        met.event("poison", url=url,
                                  reason=out["error"][:120])
                        blocked += 1
                    con.commit()
                else:
                    con.execute("UPDATE tasks SET status='failed', note=?"
                                " WHERE id=?",
                                (out["error"][:120], out["tid"]))
                    con.commit()
    summary = met.summary()
    return {"query": query, "pages": pages, "blocked": blocked,
            "escalated": escalated, "db": db_path, "metrics": summary,
            "alerts": met.alerts()}
