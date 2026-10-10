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
                 "challenge-platform", "verify you are human")

BLOCK_STATUS = {403, 429, 503}


def fetch(url: str, timeout: int = 30, cookies: dict | None = None,
          proxy: str | None = None, headers: dict | None = None) -> dict:
    t0 = time.time()
    base = {"User-Agent": UA}
    if headers:
        base.update(headers)
    else:
        headers = base
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
    req = urllib.request.Request(url, headers=base)
    if proxy:
        req.set_proxy(proxy, "http")
        req.set_proxy(proxy, "https")
    opener = urllib.request.build_opener()
    if cookies:
        opener.addheaders.append(("Cookie", "; ".join(
            f"{k}={v}" for k, v in cookies.items())))
    with opener.open(req, timeout=timeout) as r:
        body = r.read().decode("utf-8", "replace")
    return {"status": r.status, "text": body, "headers": {}, "cookies": {},
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
