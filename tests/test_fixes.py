import os
import sys
import threading
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from umbracrawl.cli import run
from umbracrawl import search
from umbracrawl.fetchers import http_impersonate as http_mod
from umbracrawl.scheduler import politeness
from umbracrawl.storage import sqlite as store


def test_gate_serializes_same_host():
    g = politeness.Gate(min_delay=0.3)
    t0 = time.time()
    ts = [threading.Thread(target=g.wait, args=("https://h.example/%d" % i,))
          for i in range(4)]
    [t.start() for t in ts]
    [t.join() for t in ts]
    assert time.time() - t0 >= 0.6  # 3 gaps x 0.3 minus scheduling slack


def test_transient_retries_then_succeeds(tmp_path):
    import umbracrawl.cli.run as run_mod
    calls = {"n": 0}
    article = "<html><body><p>fine content here</p></body></html>"

    def flaky(url, **kw):
        calls["n"] += 1
        if calls["n"] < 3:
            raise TimeoutError("timed out x%d" % calls["n"])
        return {"status": 200, "text": article, "headers": {}, "cookies": {},
                "ms": 1, "backend": "fake"}

    assert http_mod.is_transient(TimeoutError("timed out")) is True
    assert http_mod.is_transient(ValueError("boom")) is False
    old_fetch, old_search = http_mod.fetch, search.search_links
    http_mod.fetch = flaky
    search.search_links = lambda q: ["https://flaky.example/a"]
    try:
        stats = run_mod.research("flaky", str(tmp_path / "t.db"),
                                 max_workers=1)
    finally:
        http_mod.fetch, search.search_links = old_fetch, old_search
    assert stats["pages"] == 1 and calls["n"] == 3


def test_permanent_fails_without_retry(tmp_path):
    import umbracrawl.cli.run as run_mod
    calls = {"n": 0}

    def bad(url, **kw):
        calls["n"] += 1
        raise ValueError("boom")

    old_fetch, old_search = http_mod.fetch, search.search_links
    http_mod.fetch = bad
    search.search_links = lambda q: ["https://bad.example/a"]
    try:
        stats = run_mod.research("bad", str(tmp_path / "p.db"),
                                 max_workers=1)
    finally:
        http_mod.fetch, search.search_links = old_fetch, old_search
    assert stats["pages"] == 0 and calls["n"] == 1
    con = store.connect(str(tmp_path / "p.db"))
    row = con.execute("SELECT status,note FROM tasks").fetchone()
    assert row[0] == "failed" and "boom" in row[1]
    con.close()


def test_fts_punctuation_safe(tmp_path):
    con = store.connect(str(tmp_path / "f.db"))
    store.store_item(con, "https://a.example/d", "Dune (novel) guide",
                     "dune novel frank herbert arrakis", {})
    rows = store.search_items(con, "Dune (novel)")
    assert rows and rows[0][0] == "https://a.example/d"
    con.close()


def test_scope_needs_coverage():
    assert run.in_scope("book dune guide",
                        "https://x.example/book") is False  # 1 of 3
    assert run.in_scope("book dune guide",
                        "https://x.example/book-dune") is True  # 2 of 3
    assert run.in_scope("dune", "https://x.example/anything") is False
    assert run.in_scope("", "https://x.example/anything") is True


def test_answer_filters_stale(tmp_path):
    from umbracrawl.cli import answer
    db = str(tmp_path / "s.db")
    con = store.connect(db)
    store.store_item(con, "https://a.example/new", "Fresh dune piece",
                     "dune spice fresh", {})
    con.execute("INSERT INTO items(url,title,text,meta,fetched_at)"
                " VALUES(?,?,?,?,?)",
                ("https://a.example/old", "Old dune piece",
                 "dune spice old", "{}", time.time() - 40 * 86400))
    con.commit()
    con.close()
    out = answer.compose("dune", db, max_age_days=30)
    assert "Fresh dune piece" in out
    assert "Old dune piece" not in out
