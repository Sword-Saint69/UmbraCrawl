"""Counters + alert evaluation. Local file, no server. Thread-safe."""
from __future__ import annotations

import json
import threading
import time

CHALLENGE_ALERT_RATE = 0.25
CHALLENGE_ALERT_MIN = 20


class Metrics:
    def __init__(self, path: str | None = None) -> None:
        self.path = path
        self.requests = 0
        self.challenges = 0
        self.pages = 0
        self.escalated = 0
        self.poisoned = 0
        self.started = time.time()
        self._buf: list[str] = []
        self._lock = threading.Lock()

    def event(self, kind: str, **fields) -> None:
        with self._lock:
            self.requests += kind == "fetch"
            self.challenges += kind == "challenge"
            self.pages += kind == "page"
            self.escalated += kind == "escalated"
            self.poisoned += kind == "poison"
            if self.path:
                self._buf.append(json.dumps({"t": time.time(), "k": kind,
                                             **fields}))
                if len(self._buf) >= 50:
                    self._write_locked()

    def _write_locked(self) -> None:
        with open(self.path, "a") as f:
            f.write("\n".join(self._buf) + "\n")
        self._buf = []

    def flush(self) -> None:
        with self._lock:
            if self.path and self._buf:
                self._write_locked()

    def summary(self) -> dict:
        elapsed = max(time.time() - self.started, 1e-3)
        rate = (self.challenges / self.requests) if self.requests else 0.0
        return {"requests": self.requests, "challenges": self.challenges,
                "pages": self.pages, "escalated": self.escalated,
                "poisoned": self.poisoned,
                "challenge_rate": round(rate, 3),
                "pages_per_min": round(self.pages / elapsed * 60, 1)}

    def alerts(self) -> list[str]:
        out = []
        s = self.summary()
        if s["requests"] >= CHALLENGE_ALERT_MIN and \
                s["challenge_rate"] > CHALLENGE_ALERT_RATE:
            out.append(f"challenge-rate {s['challenge_rate']} over"
                       f" {s['requests']} requests")
        return out
