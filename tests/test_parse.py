import os
import sys

import yaml

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from umbracrawl.parser import adaptive, markdown, relearn
from umbracrawl.storage import sqlite as store

FIX = os.path.join(os.path.dirname(__file__), "fixtures")


def _read(name: str) -> str:
    with open(os.path.join(FIX, name)) as f:
        return f.read()


def _specs() -> dict:
    with open(os.path.join(os.path.dirname(os.path.dirname(__file__)),
                           "umbracrawl", "parser", "selectors.yml")) as f:
        return yaml.safe_load(f)["fields"]


def test_recall_above_threshold():
    specs = _specs()
    total = got = 0
    for name in ("book_a.html", "book_b.html", "book_c.html"):
        fields = adaptive.extract_fields(_read(name), specs)
        total += len(fields)
        got += sum(1 for v in fields.values() if v)
    assert adaptive.recall(
        {i: True for i in range(got)} | {f"x{i}": None
                                         for i in range(total - got)}) \
        == got / total
    assert got / total >= 0.95


def test_values_spot_check():
    fields = adaptive.extract_fields(_read("book_a.html"), _specs())
    assert fields["title"]["value"] == "Dune"
    assert fields["author"]["value"] == "Frank Herbert"
    assert "$9.99" in fields["price"]["value"]


def test_win_rate_reranks():
    specs = {"title": [{"css": "h1.book-title"}, {"css": "h1"}]}
    html = _read("book_a.html")
    stats = {"title|h1": (10, 10), "title|h1.book-title": (0, 0)}
    fields = adaptive.extract_fields(html, specs, stats)
    assert fields["title"]["selector"] == {"css": "h1"}


def test_relearn_roundtrip(tmp_path):
    con = store.connect(str(tmp_path / "r.db"))
    relearn.snapshot(con, "https://x.example/b", "<html></html>", ["price"])
    relearn.record(con, "price", ".price-current", True)
    relearn.record(con, "price", ".price-current", False)
    rates = relearn.rates(con)
    assert rates["price|.price-current"] == (1, 2)
    rows = con.execute("SELECT missing FROM snapshots").fetchall()
    assert rows[0][0] == "price"
    con.close()


def test_drift_detects_dead_selector():
    specs = {"title": [{"css": "h1.book-title"}]}
    old = _read("book_a.html")
    new = old.replace("book-title", "renamed-title")
    dead = relearn.drifted(old, new, specs)
    assert dead == {"title": [{"css": "h1.book-title"}]}
    assert relearn.drifted(old, old, specs) == {}


def test_markdown_basics():
    md = markdown.to_markdown(
        "https://x.example/b",
        "<h1>T</h1><p>Hello <a href='/x'>link</a>.</p>"
        "<ul><li>one</li></ul><script>var z=1;</script>")
    assert "# T" in md
    assert "[link](https://x.example/x)" in md
    assert "- one" in md
    assert "var z" not in md


def test_research_records_and_consumes_win_rates(tmp_path):
    """The relearn loop is wired: research() records per-selector hits and
    feeds the accumulated rates back into the next extraction."""
    import umbracrawl.cli.run as run_mod
    import umbracrawl.fetchers.http_impersonate as http_mod
    from umbracrawl import search
    html = _read("book_a.html")

    def ok(url, **kw):
        return {"status": 200, "text": html, "headers": {}, "cookies": {},
                "ms": 1, "backend": "fake"}

    old_fetch, old_search = http_mod.fetch, search.search_links
    http_mod.fetch = ok
    search.search_links = lambda q: ["https://x.example/book"]
    try:
        db = str(tmp_path / "w.db")
        assert run_mod.research("book", db, max_workers=1)["pages"] == 1
        # second run on the same db: rates now feed extraction
        assert run_mod.research("book", db, max_workers=1,
                                fresh=True)["pages"] == 1
    finally:
        http_mod.fetch, search.search_links = old_fetch, old_search
    con = store.connect(db)
    rates = relearn.rates(con)
    con.close()
    # one page crawled: a matching selector is a win, a miss is still a try
    assert rates["title|h1.book-title"] == (2, 2)
    assert rates["price|.price-current"] == (2, 2)
    assert rates["title|h1.product-title"] == (0, 2)
    # the winner re-ranked above the no-hit candidate wins the next page
    ranked = adaptive.extract_fields(html, _specs(), rates)
    assert ranked["title"]["selector"] == {"css": "h1.book-title"}
