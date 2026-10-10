"""Impersonated HTTP fetch. curl_cffi preferred, stdlib fallback."""
from __future__ import annotations

import time
import urllib.request

try:
    from curl_cffi import requests as _creq
    HAVE_CREL = True
except ImportError:
    HAVE_CREL = False

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
      " (KHTML, like Gecko) Chrome/124.0 Safari/537.36")

WALL_KEYWORDS = ("captcha", "just a moment", "attention required",
                 "turnstile", "datadome", "perimeterx", "imperva",
                 "challenge-platform", "verify you are human",
                 "verifying you are human")

BLOCK_STATUS = {403, 429, 503}

TRANSIENT_MARKS = ("timed out", "timeout", "connection reset",
                   "connection aborted", "temporary failure",
                   "service unavailable", "bad gateway", "gateway timeout",
                   "too many requests")

MAX_TRANSIENT_TRIES = 4


def is_transient(exc: Exception) -> bool:
    name = type(exc).__name__.lower()
    text = f"{name} {exc}".lower()
    return any(m in text for m in TRANSIENT_MARKS) or \
        isinstance(exc, TimeoutError)


def fetch(url: str, timeout: int = 30, cookies: dict | None = None,
          proxy: str | None = None, headers: dict | None = None) -> dict:
    t0 = time.time()
    headers = {"User-Agent": UA, **(headers or {})}
    proxies = {"http": proxy, "https": proxy} if proxy else None
    if HAVE_CREL:
        kw: dict = {"impersonate": "chrome124", "timeout": timeout,
                    "headers": headers}
        if cookies:
            kw["cookies"] = cookies
        if proxies:
            kw["proxies"] = proxies
        r = _creq.get(url, **kw)
        try:
            jar = dict(r.cookies)
        except Exception:
            jar = {}
        return {"status": r.status_code, "text": r.text,
                "headers": dict(r.headers), "cookies": jar,
                "ms": int((time.time() - t0) * 1000), "backend": "curl_cffi"}
    req = urllib.request.Request(url, headers=headers)
    if proxy:
        req.set_proxy(proxy, "http")
        req.set_proxy(proxy, "https")
    opener = urllib.request.build_opener()
    if cookies:
        opener.addheaders.append(("Cookie", "; ".join(
            f"{k}={v}" for k, v in cookies.items())))
    try:
        with opener.open(req, timeout=timeout) as r:
            status, body = r.status, r.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        status, body = e.code, e.read().decode("utf-8", "replace")
    return {"status": status, "text": body, "headers": {}, "cookies": {},
            "ms": int((time.time() - t0) * 1000), "backend": "urllib"}


def is_challenge(status: int, text: str) -> tuple[bool, str]:
    low = text.lower()
    if status in BLOCK_STATUS:
        return True, f"http-{status}"
    if any(k in low for k in WALL_KEYWORDS):
        return True, "wall-keyword"
    return False, "clean"


def is_thin(status: int, text: str) -> bool:
    return status == 200 and len(text) < 512
