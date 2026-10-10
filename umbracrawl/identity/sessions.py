"""Session pool: isolated cookies, challenge budgets, SQLite persistence.

Thread-safe: one RLock guards every read/write on the shared connection.
"""
from __future__ import annotations

import json
import sqlite3
import threading
import time
import uuid

SCHEMA = """
CREATE TABLE IF NOT EXISTS sessions(
  sid TEXT PRIMARY KEY,
  cookies TEXT DEFAULT '{}',
  created REAL NOT NULL,
  uses INTEGER NOT NULL DEFAULT 0,
  challenges INTEGER NOT NULL DEFAULT 0,
  alive INTEGER NOT NULL DEFAULT 1
);
"""

MAX_CHALLENGES = 2


class Session:
    def __init__(self, sid: str, cookies: dict, created: float,
                 uses: int, challenges: int) -> None:
        self.sid = sid
        self.cookies = cookies
        self.created = created
        self.uses = uses
        self.challenges = challenges


class SessionPool:
    def __init__(self, con: sqlite3.Connection, size: int = 4,
                 max_challenges: int = MAX_CHALLENGES) -> None:
        self.con = con
        self.size = size
        self.max_challenges = max_challenges
        self._lock = threading.RLock()
        con.executescript(SCHEMA)
        con.commit()

    def _row(self, sid: str) -> Session:
        r = self.con.execute(
            "SELECT sid,cookies,created,uses,challenges FROM sessions"
            " WHERE sid=?", (sid,)).fetchone()
        return Session(r[0], json.loads(r[1]), r[2], r[3], r[4])

    def checkout(self, commit: bool = True) -> Session:
        with self._lock:
            r = self.con.execute(
                "SELECT sid FROM sessions WHERE alive=1"
                " ORDER BY uses ASC, created ASC LIMIT 1").fetchone()
            if r is None:
                sid = uuid.uuid4().hex[:12]
                self.con.execute(
                    "INSERT INTO sessions(sid,cookies,created)"
                    " VALUES(?, '{}', ?)", (sid, time.time()))
                self.con.commit()
                r = (sid,)
            self.con.execute("UPDATE sessions SET uses=uses+1 WHERE sid=?", r)
            if commit:
                self.con.commit()
            return self._row(r[0])

    def save_cookies(self, sid: str, cookies: dict,
                     commit: bool = True) -> None:
        with self._lock:
            cur = self.con.execute(
                "SELECT cookies FROM sessions WHERE sid=?", (sid,)).fetchone()
            merged = json.loads(cur[0]) if cur else {}
            merged.update(cookies)
            self.con.execute("UPDATE sessions SET cookies=? WHERE sid=?",
                             (json.dumps(merged), sid))
            if commit:
                self.con.commit()

    def note_challenge(self, sid: str,
                     commit: bool = True) -> bool:
        """Record a challenge. Returns True when the session is retired."""
        with self._lock:
            self.con.execute(
                "UPDATE sessions SET challenges=challenges+1 WHERE sid=?",
                (sid,))
            n = self.con.execute(
                "SELECT challenges FROM sessions WHERE sid=?",
                (sid,)).fetchone()[0]
            retired = n >= self.max_challenges
            if retired:
                self.con.execute(
                    "UPDATE sessions SET alive=0, cookies='{}'"
                    " WHERE sid=?", (sid,))
            if commit:
                self.con.commit()
            return retired
