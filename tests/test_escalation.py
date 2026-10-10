import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from umbracrawl.cli import run
from umbracrawl import search
from umbracrawl.fetchers import camoufox_pool, router

FIX = os.path.join(os.path.dirname(__file__), "fixtures")


def _read(name: str) -> str:
    with open(os.path.join(FIX, name)) as f:
        return f.read()


def test_route_ladder():
    assert router.route(0) == "http"
    assert router.route(1) == "http"
    assert router.route(2) == "browser"
    assert router.route(3) == "browser"
    assert router.route(4) == "poison"


def test_slot_unavailable_without_backend_or_stub():
    slot = camoufox_pool.BrowserSlot()
    assert slot.available() == camoufox_pool.HAVE_CAMOUFOX


def test_escalation_recovers_body(tmp_path):
    wall = _read("cloudflare.html")
    article = _read("article.html")
    assert len(article) > 5 * 1024

    calls = {"n": 0}

    def fake_fetch(url, **kw):
        calls["n"] += 1
        return {"status": 200, "text": wall, "headers": {}, "cookies": {},
                "ms": 1, "backend": "fake"}

    class FakeDriver:
        def get(self, url, profile, proxy):
            return article

    import umbracrawl.fetchers.http_impersonate as http_mod
    import umbracrawl.cli.run as run_mod
    old_fetch, old_search = http_mod.fetch, search.search_links
    http_mod.fetch = fake_fetch
    search.search_links = lambda q: ["https://walled.example/guide"]
    try:
        stats = run_mod.research("guide", str(tmp_path / "e.db"),
                                 max_workers=1,
                                 browser_slot=camoufox_pool.BrowserSlot(
                                     driver=FakeDriver()))
    finally:
        http_mod.fetch = old_fetch
        search.search_links = old_search
    assert stats["pages"] == 1
    assert stats["escalated"] == 1
    assert stats["blocked"] == 0


def _patch(monkey_targets, fetch_fn, seeds):
    import umbracrawl.fetchers.http_impersonate as http_mod
    old_fetch, old_search = http_mod.fetch, search.search_links
    http_mod.fetch = fetch_fn
    search.search_links = lambda q: seeds
    return old_fetch, old_search


def _unpatch(old):
    import umbracrawl.fetchers.http_impersonate as http_mod
    http_mod.fetch, search.search_links = old[0], old[1]


def _wall_fetch(url, **kw):
    return {"status": 200, "text": _read("cloudflare.html"), "headers": {},
            "cookies": {}, "ms": 1, "backend": "fake"}


def test_retry_requeues_then_poison_without_browser(tmp_path):
    import umbracrawl.cli.run as run_mod
    from umbracrawl.storage import sqlite as store
    db = str(tmp_path / "r.db")
    old = _patch(None, _wall_fetch, ["https://walled.example/guide"])
    try:
        stats = run_mod.research("guide", db, max_workers=1,
                                 browser_slot=camoufox_pool.BrowserSlot())
    finally:
        _unpatch(old)
    assert stats["pages"] == 0
    assert stats["blocked"] == 1  # terminated, not looping
    con = store.connect(db)
    row = con.execute(
        "SELECT status,attempts,challenges,note FROM tasks").fetchone()
    assert row[0] == "poison" and row[1] == 2 and row[2] == 2
    assert "no-browser" in row[3]
    con.close()


def test_browser_walled_poison(tmp_path):
    import umbracrawl.cli.run as run_mod
    from umbracrawl.storage import sqlite as store
    db = str(tmp_path / "w.db")

    class WallDriver:
        def get(self, url, profile, proxy):
            return _read("cloudflare.html")

    old = _patch(None, _wall_fetch, ["https://walled.example/guide"])
    try:
        stats = run_mod.research("guide", db, max_workers=1,
                                 browser_slot=camoufox_pool.BrowserSlot(
                                     driver=WallDriver()))
    finally:
        _unpatch(old)
    assert stats["blocked"] == 1 and stats["pages"] == 0
    con = store.connect(db)
    row = con.execute("SELECT status,note FROM tasks").fetchone()
    assert row[0] == "poison" and "browser-walled" in row[1]
    con.close()


def test_404_failed_no_store(tmp_path):
    import umbracrawl.cli.run as run_mod
    from umbracrawl.storage import sqlite as store
    db = str(tmp_path / "n.db")

    def gone(url, **kw):
        return {"status": 404, "text": "<h1>not here</h1>", "headers": {},
                "cookies": {}, "ms": 1, "backend": "fake"}

    old = _patch(None, gone, ["https://gone.example/missing"])
    try:
        stats = run_mod.research("missing", db, max_workers=1)
    finally:
        _unpatch(old)
    assert stats["pages"] == 0
    con = store.connect(db)
    assert con.execute("SELECT status FROM tasks").fetchone()[0] == "failed"
    assert con.execute("SELECT COUNT(*) FROM items").fetchone()[0] == 0
    con.close()


def test_strikes_accumulate_on_retry(tmp_path):
    import umbracrawl.cli.run as run_mod
    from umbracrawl.storage import sqlite as store
    db = str(tmp_path / "s.db")
    old = _patch(None, _wall_fetch, ["https://walled.example/guide"])
    try:
        run_mod.research("guide", db, max_workers=1,
                         browser_slot=camoufox_pool.BrowserSlot())
    finally:
        _unpatch(old)
    con = store.connect(db)
    retired = con.execute(
        "SELECT COUNT(*) FROM sessions WHERE alive=0").fetchone()[0]
    assert retired >= 1
    con.close()


def test_fresh_recrawls(tmp_path):
    import umbracrawl.cli.run as run_mod
    db = str(tmp_path / "f.db")
    article = _read("article.html")

    def ok(url, **kw):
        return {"status": 200, "text": article, "headers": {}, "cookies": {},
                "ms": 1, "backend": "fake"}

    old = _patch(None, ok, ["https://fresh.example/guide"])
    try:
        assert run_mod.research("guide", db, max_workers=1)["pages"] == 1
        assert run_mod.research("guide", db, max_workers=1)["pages"] == 0
        assert run_mod.research("guide", db, max_workers=1,
                                fresh=True)["pages"] == 1
    finally:
        _unpatch(old)
