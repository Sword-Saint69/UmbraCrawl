import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from umbracrawl.cli import run
from umbracrawl import search
from umbracrawl.fetchers import camoufox_pool, patchright_pool
from umbracrawl.observability import metrics as metrics_mod

FIX = os.path.join(os.path.dirname(__file__), "fixtures")


def _read(name: str) -> str:
    with open(os.path.join(FIX, name)) as f:
        return f.read()


def test_patchright_unavailable_without_package_or_stub():
    slot = patchright_pool.BrowserSlot()
    assert slot.available() == patchright_pool.HAVE_PATCHRIGHT


def test_chain_falls_to_patchright(tmp_path):
    import umbracrawl.cli.run as run_mod
    wall = _read("cloudflare.html")
    article = _read("article.html")

    def fake_fetch(url, **kw):
        return {"status": 200, "text": wall, "headers": {}, "cookies": {},
                "ms": 1, "backend": "fake"}

    class WallDriver:
        def get(self, url, profile, proxy):
            return wall

    class GoodDriver:
        def get(self, url, profile, proxy):
            return article

    import umbracrawl.fetchers.http_impersonate as http_mod
    old_fetch, old_search = http_mod.fetch, search.search_links
    http_mod.fetch = fake_fetch
    search.search_links = lambda q: ["https://walled.example/guide"]
    try:
        stats = run_mod.research(
            "guide", str(tmp_path / "c.db"), max_workers=1, browser_slot=[
                camoufox_pool.BrowserSlot(driver=WallDriver()),
                patchright_pool.BrowserSlot(driver=GoodDriver())])
    finally:
        http_mod.fetch, search.search_links = old_fetch, old_search
    assert stats["pages"] == 1
    assert stats["escalated"] == 1


def test_metrics_and_alerts():
    m = metrics_mod.Metrics()
    for _ in range(20):
        m.event("fetch")
    for _ in range(6):
        m.event("challenge")
    s = m.summary()
    assert s["requests"] == 20 and s["challenges"] == 6
    assert s["challenge_rate"] == 0.3
    assert len(m.alerts()) == 1
    calm = metrics_mod.Metrics()
    for _ in range(20):
        calm.event("fetch")
    assert calm.alerts() == []


def test_research_reports_metrics(tmp_path):
    import umbracrawl.cli.run as run_mod
    article = _read("article.html")

    def ok(url, **kw):
        return {"status": 200, "text": article, "headers": {}, "cookies": {},
                "ms": 1, "backend": "fake"}

    import umbracrawl.fetchers.http_impersonate as http_mod
    old_fetch, old_search = http_mod.fetch, search.search_links
    http_mod.fetch = ok
    search.search_links = lambda q: ["https://m.example/guide"]
    try:
        stats = run_mod.research("guide", str(tmp_path / "m.db"),
                                 max_workers=1)
    finally:
        http_mod.fetch, search.search_links = old_fetch, old_search
    assert stats["metrics"]["pages"] >= 1
    assert stats["alerts"] == []
    assert os.path.exists(str(tmp_path / "m.db.metrics.jsonl"))
