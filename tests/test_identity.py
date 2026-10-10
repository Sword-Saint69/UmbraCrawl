import os
import random
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from umbracrawl.identity import fingerprints, leakcheck, proxies, sessions
from umbracrawl.storage import sqlite as store


def test_session_retire(tmp_path):
    con = store.connect(str(tmp_path / "s.db"))
    pool = sessions.SessionPool(con)
    s = pool.checkout()
    pool.save_cookies(s.sid, {"a": "1"})
    assert pool.checkout().cookies == {"a": "1"}
    assert pool.note_challenge(s.sid) is False
    assert pool.note_challenge(s.sid) is True  # 2nd strike retires
    s2 = pool.checkout()
    assert s2.sid != s.sid
    con.close()


def test_proxy_sticky_cooldown():
    px = proxies.ProxyPool(["http://p1", "http://p2"])
    a = px.checkout("s1")
    assert px.checkout("s1") == a
    for _ in range(3):
        px.report(a, False)
    b = px.checkout("s2")
    assert b != a  # a is cooling
    px.report(b, True)
    assert proxies.ProxyPool().checkout("x") is None


def test_profile_consistent():
    p = fingerprints.pick_profile(random.Random(7))
    h = fingerprints.headers_for(p)
    assert p["ua"] in h["User-Agent"]
    assert "Chromium" in h["Sec-CH-UA"]
    assert p["os"] in ("windows", "macos", "browserforge")


def test_leak_gate():
    good = {"webdriver": None, "cdp_keys": [],
            "webgl_renderer": "X", "profile_renderer": "X",
            "headers": ["Host", "User-Agent", "Accept", "Accept-Language"]}
    assert leakcheck.gate(good) is True
    bad = dict(good, webdriver=True, cdp_keys=["cdc_foo"],
               webgl_renderer="Y")
    assert leakcheck.gate(bad) is False
    assert set(leakcheck.evaluate(good)) == {
        "check_webdriver", "check_cdp", "check_webgl", "check_headers"}
