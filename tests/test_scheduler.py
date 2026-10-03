import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from umbracrawl.scheduler import dedupe, politeness


def test_normalize_coats():
    a = dedupe.normalize("HTTPS://Example.COM:443/A?b=2&a=1#frag")
    b = dedupe.normalize("https://example.com/A?a=1&b=2")
    assert a == b
    assert dedupe.url_hash("https://example.com/A") == \
        dedupe.url_hash("https://EXAMPLE.com:443/A#x")


def test_gate_orders_hosts():
    g = politeness.Gate(min_delay=0.01)
    g.wait("https://a.example/1")
    g.wait("https://b.example/1")  # different host: no wait
    assert set(g._last) == {"a.example", "b.example"}
