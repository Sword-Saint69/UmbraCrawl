"""Patchright fallback slot. Same interface as the Camoufox slot.

Lazy import: the patched driver runs only when installed. Tests inject a
stub driver. Patchright could not be installed in this environment, so the
real path is validated by API shape only (mirrors playwright sync API).
"""
from __future__ import annotations

import threading
import time

try:
    from patchright.sync_api import sync_playwright  # type: ignore
    HAVE_PATCHRIGHT = True
except ImportError:
    HAVE_PATCHRIGHT = False


class BrowserSlot:
    def __init__(self, driver=None, timeout: int = 60) -> None:
        self._driver = driver
        self.timeout = timeout
        self._lock = threading.Semaphore(1)
        self.uses = 0

    def available(self) -> bool:
        return self._driver is not None or HAVE_PATCHRIGHT

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
        with sync_playwright() as pw:  # type: ignore
            browser = pw.chromium.launch(headless=True,
                                         proxy={"server": proxy} if proxy
                                         else None)
            ctx = browser.new_context(
                user_agent=profile.get("ua"),
                locale=profile.get("locale", "en-US"),
                viewport={"width": 1920, "height": 1080})
            page = ctx.new_page()
            page.mouse.move(400, 300)
            page.goto(url, timeout=self.timeout * 1000)
            page.mouse.wheel(0, 600)
            page.wait_for_timeout(1500)
            text = page.content()
            browser.close()
            return {"status": 200, "text": text, "headers": {},
                    "cookies": {},
                    "ms": int((time.time() - t0) * 1000),
                    "backend": "patchright"}
