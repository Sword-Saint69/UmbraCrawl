"""Per-host politeness gate."""
from __future__ import annotations

import time
from urllib.parse import urlparse
from urllib.robotparser import RobotFileParser


class Gate:
    def __init__(self, min_delay: float = 2.0) -> None:
        self.min_delay = min_delay
        self._last: dict[str, float] = {}

    def wait(self, url: str) -> None:
        host = urlparse(url).hostname or ""
        due = self._last.get(host, 0.0) + self.min_delay - time.time()
        if due > 0:
            time.sleep(due)
        self._last[host] = time.time()


def can_fetch(url: str, ua: str = "UmbraCrawl/0.1", timeout: float = 10) -> bool:
    try:
        p = urlparse(url)
        rp = RobotFileParser()
        rp.set_url(f"{p.scheme}://{p.netloc}/robots.txt")
        rp.read()
        return rp.can_fetch(ua, url)
    except Exception:
        return True
