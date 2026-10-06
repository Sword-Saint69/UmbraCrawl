import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from umbracrawl import extract
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
