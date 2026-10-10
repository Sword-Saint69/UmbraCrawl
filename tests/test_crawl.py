import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from umbracrawl import extract, search
from umbracrawl.cli import prompt
from umbracrawl.fetchers import http_impersonate as http

HTML = """<html><head><title>Dune Guide</title>
<meta name="description" content="A book guide."></head>
<body><h1>Dune</h1><p>Arrakis spice epic.</p>
<script>var x=1;</script>
<a href="/chapters">Chapters</a>
<a href="https://other.example/rev">Review</a></body></html>"""


def test_extract():
    p = extract.extract("https://book.example/dune", HTML)
    assert p["title"] == "Dune Guide"
    assert "Arrakis" in p["text"]
    assert "var x" not in p["text"]
    urls = [u for (u, _) in p["links"]]
    assert "https://book.example/chapters" in urls
    assert "https://other.example/rev" in urls


def test_prompt():
    assert prompt.to_query("research a book Dune") == "book Dune"
    assert prompt.to_query("RESEARCH the author Butler") == "author Butler"


def test_challenge():
    blocked, reason = http.is_challenge(403, "hello")
    assert blocked and reason == "http-403"
    blocked, _ = http.is_challenge(200, "x" * 600)
    assert not blocked
    assert http.is_thin(200, "short")


def test_walled_article_needs_browser():
    with open(os.path.join(os.path.dirname(__file__), "fixtures",
                           "walled_article.html")) as f:
        html = f.read()
    assert len(html) > 5 * 1024
    blocked, reason = http.is_challenge(200, html)
    assert blocked and reason == "wall-keyword"
    assert http.is_thin(200, html) is False


def test_clean_link_unwraps_redirect():
    wrapped = ("//duckduckgo.com/l/?uddg=https%3A%2F%2Fen.wikipedia.org"
               "%2Fwiki%2FDune_(novel)&rut=189b04")
    assert search.clean_link(wrapped) == \
        "https://en.wikipedia.org/wiki/Dune_(novel)"
    assert search.clean_link("//example.com/x") == "https://example.com/x"
    assert search.clean_link("//duckduckgo.com/?q=dune") is None
    assert search.clean_link("/relative/path") is None


def test_search_links_parses_wrapped_markup():
    html = ('<a rel="nofollow" class="result__a"'
            ' href="//duckduckgo.com/l/?uddg=https%3A%2F%2Fa.example'
            '%2Fbook&amp;rut=abc">T</a>')
    stub = lambda url: {"status": 200, "text": html, "headers": {},
                        "cookies": {}, "ms": 1, "backend": "fake"}
    assert search.search_links("book", fetcher=stub) == \
        ["https://a.example/book"]
