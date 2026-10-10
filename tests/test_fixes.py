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


def test_gate_same_host_spaced_not_stacked():
    g = politeness.Gate(min_delay=0.2)
    t0 = time.time()
    g.wait("https://s.example/a")
    g.wait("https://s.example/b")
    assert time.time() - t0 >= 0.2


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


def test_metrics_thread_safe(tmp_path):
    import threading
    from umbracrawl.observability.metrics import Metrics
    m = Metrics(str(tmp_path / "m.jsonl"))

    def hammer():
        for i in range(500):
            m.event("fetch", i=i)

    ts = [threading.Thread(target=hammer) for _ in range(4)]
    [t.start() for t in ts]
    [t.join() for t in ts]
    m.flush()
    assert m.requests == 2000
    import json
    lines = open(str(tmp_path / "m.jsonl")).read().splitlines()
    assert len(lines) == 2000
    for ln in lines:
        json.loads(ln)  # no torn lines


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


def test_poison_event_carries_the_poisoned_url(tmp_path):
    """Every poison event names the task that actually died.

    With a multi-worker batch, the results loop used to stamp the leftover
    `url` from the lease unpack, so all poison events in one batch carried
    the last URL of that batch.
    """
    import json

    import umbracrawl.cli.run as run_mod
    from umbracrawl.fetchers import camoufox_pool

    wall = open(os.path.join(os.path.dirname(__file__), "fixtures",
                             "cloudflare.html")).read()
    seeds = ["https://first.example/poison", "https://second.example/poison"]
    old_fetch, old_search = http_mod.fetch, search.search_links
    http_mod.fetch = lambda url, **kw: {
        "status": 200, "text": wall, "headers": {}, "cookies": {},
        "ms": 1, "backend": "fake"}
    search.search_links = lambda q: seeds
    try:
        db = str(tmp_path / "p.db")
        stats = run_mod.research("guide", db, max_workers=4,
                                 browser_slot=camoufox_pool.BrowserSlot())
    finally:
        http_mod.fetch, search.search_links = old_fetch, old_search
    assert stats["blocked"] == 2
    events = [json.loads(l) for l in open(db + ".metrics.jsonl")]
    poisons = [e["url"] for e in events if e["k"] == "poison"]
    assert sorted(poisons) == sorted(seeds)
    con = store.connect(db)
    notes = [r[0] for r in con.execute(
        "SELECT note FROM tasks WHERE status='poison'").fetchall()]
    con.close()
    assert len(notes) == 2  # both tasks, each with its own reason


def test_snapshot_commit_false_keeps_batch_atomic(tmp_path):
    """ensure() runs executescript, which COMMITs an open transaction."""
    from umbracrawl.parser import relearn
    con = store.connect(str(tmp_path / "e.db"))
    relearn.ensure(con)  # tables exist before any pending write
    store.enqueue(con, [("https://a.example/", "h", 0, 0.0)], commit=False)
    relearn.snapshot(con, "https://a.example/", "<html></html>", ["price"],
                     commit=False)
    con.rollback()
    assert con.execute("SELECT COUNT(*) FROM tasks").fetchone()[0] == 0
    assert con.execute("SELECT COUNT(*) FROM snapshots").fetchone()[0] == 0
    con.close()


def test_can_fetch_fails_open_and_honors_timeout():
    from umbracrawl.scheduler import politeness
    import urllib.request
    seen = {}

    class _Resp:
        def read(self):
            return b"User-agent: *\nDisallow: /private\n"

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    old = urllib.request.urlopen

    def fake_urlopen(u, timeout=None):
        seen["timeout"] = timeout
        return _Resp()

    urllib.request.urlopen = fake_urlopen
    try:
        assert politeness.can_fetch("https://x.example/private") is False
        assert politeness.can_fetch("https://x.example/public") is True
        assert seen["timeout"] == 10
        # unreachable host: the gate fails open instead of blocking a crawl
        assert politeness.can_fetch("http://127.0.0.1:1/x") is True
    finally:
        urllib.request.urlopen = old
