"""Leak gate: all four checks pass before an identity ships.

env keys (snapshot of a live page / request):
  webdriver: value of navigator.webdriver (None when absent)
  cdp_keys: list of CDP-artifact globals found on the page
  webgl_renderer: renderer string seen on the page
  profile_renderer: renderer string the profile claims
  headers: outgoing header names in send order
"""
from __future__ import annotations

CHROME_ORDER = ["host", "connection", "upgrade-insecure-requests", "user-agent",
                "accept", "sec-fetch-site", "sec-fetch-mode",
                "sec-fetch-user", "sec-fetch-dest", "accept-language"]


def check_webdriver(env: dict) -> tuple[bool, str]:
    ok = env.get("webdriver") in (None, False)
    return ok, "webdriver-absent" if ok else "webdriver-exposed"


def check_cdp(env: dict) -> tuple[bool, str]:
    keys = env.get("cdp_keys") or []
    return (not keys, "cdp-clean" if not keys else f"cdp-leak:{keys[0]}")


def check_webgl(env: dict) -> tuple[bool, str]:
    ok = env.get("webgl_renderer") == env.get("profile_renderer")
    return ok, "webgl-match" if ok else "webgl-mismatch"


def check_headers(env: dict) -> tuple[bool, str]:
    seen = [h.lower() for h in (env.get("headers") or [])]
    core = [h for h in CHROME_ORDER if h in seen]
    want = [h for h in CHROME_ORDER if h in core]
    ok = core == [h for h in want if h in seen][:len(core)] and \
        "user-agent" in seen
    return ok, "header-order-ok" if ok else "header-order-bad"


CHECKS = (check_webdriver, check_cdp, check_webgl, check_headers)


def evaluate(env: dict) -> dict[str, tuple[bool, str]]:
    return {fn.__name__: fn(env) for fn in CHECKS}


def gate(env: dict) -> bool:
    return all(ok for (ok, _) in evaluate(env).values())
