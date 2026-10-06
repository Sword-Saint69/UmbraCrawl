"""Compose the cited answer from local SQLite rows."""
from __future__ import annotations

from .. import storage


def compose(query: str, db_path: str, limit: int = 8) -> str:
    con = storage.connect(db_path)
    rows = storage.search_items(con, query, limit)
    con.close()
    if not rows:
        return f"No local rows for '{query}'. Run the crawl first."
    lines = [f"# Research: {query}", ""]
    for i, (url, title, snip) in enumerate(rows, 1):
        lines.append(f"## [{i}] {title or url}")
        lines.append(f"{snip}")
        lines.append(f"Source: {url}")
        lines.append("")
    lines.append(f"_{len(rows)} sources from local SQLite store._")
    return "\n".join(lines)
