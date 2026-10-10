"""Priority + leasing over the SQLite task table."""
from __future__ import annotations

import sqlite3

from .dedupe import normalize, url_hash


def priority_for(depth: int) -> float:
    return float(-depth)  # breadth-first: shallow pages first


def add_urls(con: sqlite3.Connection, urls: list[str], depth: int,
             storage, commit: bool = True) -> int:
    rows = []
    for u in urls:
        try:
            norm = normalize(u)
        except ValueError:
            continue
        if not norm.startswith(("http://", "https://")):
            continue
        rows.append((norm, url_hash(norm), depth, priority_for(depth)))
    return storage.enqueue(con, rows, commit=commit)
