"""SQLite store: task queue, items, FTS5 search. WAL mode."""
from __future__ import annotations

import json
import re
import sqlite3
import time

SCHEMA = """
CREATE TABLE IF NOT EXISTS tasks(
  id INTEGER PRIMARY KEY,
  url TEXT UNIQUE NOT NULL,
  url_hash TEXT UNIQUE NOT NULL,
  status TEXT NOT NULL DEFAULT 'queued',
  depth INTEGER NOT NULL DEFAULT 0,
  priority REAL NOT NULL DEFAULT 0,
  attempts INTEGER NOT NULL DEFAULT 0,
  challenges INTEGER NOT NULL DEFAULT 0,
  note TEXT DEFAULT '',
  added_at REAL NOT NULL,
  leased_at REAL
);
CREATE INDEX IF NOT EXISTS idx_tasks_status
  ON tasks(status, priority DESC, depth ASC);
CREATE TABLE IF NOT EXISTS items(
  url TEXT PRIMARY KEY,
  title TEXT DEFAULT '',
  text TEXT DEFAULT '',
  meta TEXT DEFAULT '{}',
  fetched_at REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS kv(k TEXT PRIMARY KEY, v TEXT);
"""

FTS = """
CREATE VIRTUAL TABLE IF NOT EXISTS items_fts
  USING fts5(title, text, content='items', content_rowid='rowid');
CREATE TRIGGER IF NOT EXISTS items_ai AFTER INSERT ON items BEGIN
  INSERT INTO items_fts(rowid, title, text)
  VALUES (new.rowid, new.title, new.text);
END;
CREATE TRIGGER IF NOT EXISTS items_ad AFTER DELETE ON items BEGIN
  INSERT INTO items_fts(items_fts, rowid, title, text)
  VALUES ('delete', old.rowid, old.title, old.text);
END;
"""


def connect(path: str) -> sqlite3.Connection:
    con = sqlite3.connect(path, check_same_thread=False)
    con.execute("PRAGMA journal_mode=WAL;")
    con.executescript(SCHEMA)
    for col, decl in (("challenges", "INTEGER NOT NULL DEFAULT 0"),
                      ("note", "TEXT DEFAULT ''")):
        try:
            con.execute(f"ALTER TABLE tasks ADD COLUMN {col} {decl}")
        except sqlite3.OperationalError:
            pass  # column already present (pre-v0.3 database)
    try:
        con.executescript(FTS)
        con.execute("INSERT OR IGNORE INTO kv(k,v) VALUES('fts','1')")
    except sqlite3.OperationalError:
        con.execute("INSERT OR IGNORE INTO kv(k,v) VALUES('fts','0')")
    return con


def has_fts(con: sqlite3.Connection) -> bool:
    row = con.execute("SELECT v FROM kv WHERE k='fts'").fetchone()
    return bool(row and row[0] == '1')


def enqueue(con: sqlite3.Connection, rows: list[tuple[str, str, int, float]],
            commit: bool = True) -> int:
    """rows: (url, url_hash, depth, priority). Returns new row count."""
    now = time.time()
    cur = con.executemany(
        "INSERT OR IGNORE INTO tasks(url,url_hash,depth,priority,added_at)"
        " VALUES(?,?,?,?,?)",
        [(u, h, d, p, now) for (u, h, d, p) in rows],
    )
    if commit:
        con.commit()
    return cur.rowcount


def lease(con: sqlite3.Connection, limit: int, lease_sec: int = 300,
          commit: bool = True) -> list[tuple]:
    now = time.time()
    cur = con.execute(
        "SELECT id,url,depth,attempts,challenges FROM tasks"
        " WHERE status='queued'"
        " OR (status='leased' AND leased_at < ?) "
        "ORDER BY priority DESC, depth ASC LIMIT ?",
        (now - lease_sec, limit),
    )
    tasks = cur.fetchall()
    for (tid, _, _, _, _) in tasks:
        con.execute(
            "UPDATE tasks SET status='leased', leased_at=?, attempts=attempts+1"
            " WHERE id=?", (now, tid),
        )
    if commit:
        con.commit()
    cur = con.execute(
        "SELECT id,url,depth,attempts,challenges FROM tasks WHERE id IN (%s)"
        % ",".join("?" * len(tasks)), [t[0] for t in tasks],
    ) if tasks else []
    return cur.fetchall() if tasks else []


def mark(con: sqlite3.Connection, tid: int, status: str,
         commit: bool = True) -> None:
    con.execute("UPDATE tasks SET status=? WHERE id=?", (status, tid))
    if commit:
        con.commit()


def pending(con: sqlite3.Connection) -> int:
    row = con.execute(
        "SELECT COUNT(*) FROM tasks WHERE status IN ('queued','leased')"
    ).fetchone()
    return int(row[0])


def recover(con: sqlite3.Connection) -> int:
    """Crash recovery: stale 'leased' rows back to 'queued'."""
    cur = con.execute("UPDATE tasks SET status='queued' WHERE status='leased'")
    con.commit()
    return cur.rowcount


def store_item(con: sqlite3.Connection, url: str, title: str,
               text: str, meta: dict | None = None,
               commit: bool = True) -> None:
    con.execute(
        "INSERT OR REPLACE INTO items(url,title,text,meta,fetched_at)"
        " VALUES(?,?,?,?,?)",
        (url, title, text, json.dumps(meta or {}), time.time()),
    )
    if commit:
        con.commit()


def _fts_query(query: str) -> str:
    terms = re.findall(r"\w+", query.lower())
    return " OR ".join(terms)


def search_items(con: sqlite3.Connection, query: str, limit: int = 8) -> list[tuple]:
    match = _fts_query(query)
    if match and has_fts(con):
        try:
            return con.execute(
                "SELECT url,title,snippet(items_fts,1,'[',']','...',24) FROM items"
                " JOIN items_fts ON items.rowid=items_fts.rowid"
                " WHERE items_fts MATCH ? ORDER BY bm25(items_fts) LIMIT ?",
                (match, limit),
            ).fetchall()
        except sqlite3.OperationalError:
            pass
    terms = re.findall(r"\w+", query.lower()) or [query]
    cond = " AND ".join(["(title LIKE ? OR text LIKE ?)"] * len(terms))
    args: list = []
    for t in terms:
        args += [f"%{t}%", f"%{t}%"]
    return con.execute(
        f"SELECT url,title,substr(text,1,160) FROM items"
        f" WHERE {cond} LIMIT ?", (*args, limit),
    ).fetchall()
