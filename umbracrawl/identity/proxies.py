"""Proxy pool: sticky per session, cooldown on failure."""
from __future__ import annotations

import time

FAIL_LIMIT = 3
COOLDOWN_SEC = 15 * 60


class ProxyPool:
    def __init__(self, proxies: list[str] | None = None) -> None:
        self.proxies = list(proxies or [])
        self._fails: dict[str, int] = {}
        self._cool_until: dict[str, float] = {}
        self._sticky: dict[str, str] = {}
        self._cursor = 0

    def _healthy(self, p: str) -> bool:
        return self._cool_until.get(p, 0.0) <= time.time()

    def checkout(self, session_id: str) -> str | None:
        if not self.proxies:
            return None  # direct connection
        if self._sticky.get(session_id) and \
                self._healthy(self._sticky[session_id]):
            return self._sticky[session_id]
        for _ in self.proxies:
            p = self.proxies[self._cursor % len(self.proxies)]
            self._cursor += 1
            if self._healthy(p):
                self._sticky[session_id] = p
                return p
        return self.proxies[0]  # all cooling: least-bad fallback

    def report(self, proxy: str | None, ok: bool) -> None:
        if not proxy:
            return
        if ok:
            self._fails[proxy] = 0
            return
        self._fails[proxy] = self._fails.get(proxy, 0) + 1
        if self._fails[proxy] >= FAIL_LIMIT:
            self._cool_until[proxy] = time.time() + COOLDOWN_SEC
            self._fails[proxy] = 0
