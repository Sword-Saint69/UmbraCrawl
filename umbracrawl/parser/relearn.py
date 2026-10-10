"""Relearn loop: snapshots of zero-match pages, drift diffs, win rates."""
from __future__ import annotations

import sqlite3
import time

SCHEMA = """
CREATE TABLE IF NOT EXISTS snapshots(
  url TEXT PRIMARY KEY, html TEXT NOT NULL,
  missing TEXT NOT NULL DEFAULT '', created REAL NOT NULL);
CREATE TABLE IF NOT EXISTS selector_stats(
  field TEXT NOT NULL, selector TEXT NOT NULL,
  wins INTEGER NOT NULL DEFAULT 0, tries INTEGER NOT NULL DEFAULT 0,
  PRIMARY KEY (field, selector));
"""


def ensure(con: sqlite3.Connection) -> None:
    con.executescript(SCHEMA)
    con.commit()


def snapshot(con: sqlite3.Connection, url: str, html: str,
             missing: list[str], commit: bool = True) -> None:
    ensure(con)
    con.execute("INSERT OR REPLACE INTO snapshots(url,html,missing,created)"
                " VALUES(?,?,?,?)",
                (url, html[:50000], ",".join(missing), time.time()))
    if commit:
        con.commit()


def record(con: sqlite3.Connection, field: str, selector: str,
           hit: bool) -> None:
    ensure(con)
    con.execute("INSERT OR IGNORE INTO selector_stats(field,selector)"
                " VALUES(?,?)", (field, selector))
    con.execute("UPDATE selector_stats SET tries=tries+1,"
                " wins=wins+? WHERE field=? AND selector=?",
                (1 if hit else 0, field, selector))
    con.commit()


def rates(con: sqlite3.Connection) -> dict:
    ensure(con)
    rows = con.execute(
        "SELECT field,selector,wins,tries FROM selector_stats").fetchall()
    return {f"{f}|{s}": (w, t) for (f, s, w, t) in rows}


def drifted(old_html: str, new_html: str, specs: dict) -> dict:
    """Which selectors matched the last-good page but miss now."""
    from .adaptive import _texts
    from lxml import html as _lhtml
    try:
        old, new = _lhtml.fromstring(old_html), _lhtml.fromstring(new_html)
    except Exception:
        return {}
    out = {}
    for field, sels in specs.items():
        dead = [s for s in sels if _texts(old, s) and not _texts(new, s)]
        if dead:
            out[field] = dead
    return out
