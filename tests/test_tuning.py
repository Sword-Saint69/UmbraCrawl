import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from umbracrawl import extract
from umbracrawl.cli import run
from umbracrawl import search
from umbracrawl.storage import sqlite as store


def test_main_scopes_text_but_keeps_links():
    html = ("<html><body><nav><p>Menu clutter</p></nav>"
            "<main><p>Real content here.</p></main>"
            "<a href='https://x.example/nav'>NavLink</a></body></html>")
    p = extract.extract("https://x.example/", html)
    assert "Real content" in p["text"]
    assert "Menu clutter" not in p["text"]
    assert any(u == "https://x.example/nav" for (u, _) in p["links"])


def test_no_main_keeps_everything():
    p = extract.extract("https://x.example/",
                        "<html><body><p>Just text.</p></body></html>")
    assert "Just text" in p["text"]


def test_recover_requeues_leased(tmp_path):
    con = store.connect(str(tmp_path / "c.db"))
    store.enqueue(con, [("https://a.example/", "h1", 0, 0.0)])
    store.lease(con, 1)
    assert store.pending(con) == 1
    assert store.recover(con) == 1
    row = con.execute("SELECT status FROM tasks").fetchone()
    assert row[0] == "queued"
    con.close()


def test_bm25_orders_best_first(tmp_path):
    con = store.connect(str(tmp_path / "b.db"))
    store.store_item(con, "https://a.example/1", "Dune guide",
                     "dune dune dune spice", {})
    store.store_item(con, "https://a.example/2", "Cooking",
                     "a passing mention of dune", {})
    rows = store.search_items(con, "dune", 2)
    assert rows[0][0] == "https://a.example/1"
    con.close()


def test_budgets_stop_loop(tmp_path):
    import umbracrawl.cli.run as run_mod
    n = {"i": 0}

    def pages(url, **kw):
        n["i"] += 1
        return {"status": 200,
                "text": f"<html><body><p>page {n['i']}</p>"
                        f"<a href='https://loop.example/{n['i']}'>n</a>"
                        "</body></html>",
                "headers": {}, "cookies": {}, "ms": 1, "backend": "fake"}

    import umbracrawl.fetchers.http_impersonate as http_mod
    old_fetch, old_search = http_mod.fetch, search.search_links
    http_mod.fetch = pages
    search.search_links = lambda q: ["https://loop.example/0"]
    try:
        db = str(tmp_path / "u.db")
        s1 = run_mod.research("loop", db, max_workers=1, max_pages=3)
        assert s1["pages"] == 3
        s2 = run_mod.research("loop", str(tmp_path / "v.db"), max_workers=1,
                              max_depth=0, timeout=60)
        assert s2["pages"] >= 1
        s3 = run_mod.research("loop", str(tmp_path / "w.db"), max_workers=1,
                              max_depth=1)
        depths = True
        con = store.connect(str(tmp_path / "w.db"))
        depths = con.execute("SELECT MAX(depth) FROM tasks").fetchone()[0]
        con.close()
        assert depths is not None and depths <= 1
    finally:
        http_mod.fetch, search.search_links = old_fetch, old_search
