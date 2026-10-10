"""Compose the cited answer from local SQLite rows."""
from __future__ import annotations

import time

from .. import storage

STALE_DAYS = 30


def compose(query: str, db_path: str, limit: int = 8,
            max_age_days: int = STALE_DAYS) -> str:
    con = storage.connect(db_path)
    rows = storage.search_items(con, query, limit * 2)
    cutoff = time.time() - max_age_days * 86400
    fresh = []
    for (url, title, snip) in rows:
        age = con.execute("SELECT fetched_at FROM items WHERE url=?",
                          (url,)).fetchone()
        if age and age[0] >= cutoff:
            fresh.append((url, title, snip))
        if len(fresh) >= limit:
            break
    con.close()
    if not fresh:
        return f"No local rows for '{query}'. Run the crawl first."
    lines = [f"# Research: {query}", ""]
    for i, (url, title, snip) in enumerate(fresh, 1):
        lines.append(f"## [{i}] {title or url}")
        lines.append(f"{snip}")
        lines.append(f"Source: {url}")
        lines.append("")
    lines.append(f"_{len(fresh)} sources from local SQLite store._")
    return "\n".join(lines)
