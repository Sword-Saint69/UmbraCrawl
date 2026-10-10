"""Borrowed browser slot: one worker slot converts to Camoufox on challenge.

Lazy import: real Camoufox runs only when installed. Tests inject a stub
driver with the same two methods (launch/page). No browser boots at import.
"""
from __future__ import annotations

import threading
import time

try:
    from camoufox.sync_api import Camoufox  # type: ignore
    HAVE_CAMOUFOX = True
except ImportError:
    HAVE_CAMOUFOX = False


class BrowserSlot:
    def __init__(self, driver=None, timeout: int = 60) -> None:
        self._driver = driver
        self.timeout = timeout
        self._lock = threading.Semaphore(1)
        self.uses = 0

    def available(self) -> bool:
        return self._driver is not None or HAVE_CAMOUFOX

    def fetch(self, url: str, profile: dict | None = None,
              proxy: str | None = None) -> dict:
        t0 = time.time()
        if not self.available():
            raise RuntimeError("no browser backend installed")
        with self._lock:
            self.uses += 1
            if self._driver is not None:
                text = self._driver.get(url, profile, proxy)
                return {"status": 200, "text": text, "headers": {},
                        "cookies": {},
                        "ms": int((time.time() - t0) * 1000),
                        "backend": "stub"}
            return self._real_fetch(url, profile, proxy, t0)

    def _real_fetch(self, url: str, profile: dict | None,
                    proxy: str | None, t0: float) -> dict:
        profile = profile or {}
        kw: dict = {"headless": True}
        if proxy:
            kw["proxy"] = {"server": proxy}
        locale = profile.get("locale")
        if locale:
            kw["locale"] = locale
        with Camoufox(**kw) as browser:  # type: ignore
            page = browser.new_page(viewport={
                "width": 1920, "height": 1080})
            page.mouse.move(400, 300)
            page.goto(url, timeout=self.timeout * 1000)
            page.mouse.wheel(0, 600)
            page.wait_for_timeout(1500)
            text = page.content()
            return {"status": 200, "text": text, "headers": {},
                    "cookies": {},
                    "ms": int((time.time() - t0) * 1000),
                    "backend": "camoufox"}
