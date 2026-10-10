import os
import sqlite3
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from umbracrawl.storage import sqlite as store

OLD_TASKS = """
CREATE TABLE tasks(
  id INTEGER PRIMARY KEY,
  url TEXT UNIQUE NOT NULL,
  url_hash TEXT UNIQUE NOT NULL,
  status TEXT NOT NULL DEFAULT 'queued',
  depth INTEGER NOT NULL DEFAULT 0,
  priority REAL NOT NULL DEFAULT 0,
  attempts INTEGER NOT NULL DEFAULT 0,
  added_at REAL NOT NULL,
  leased_at REAL
);
CREATE TABLE items(url TEXT PRIMARY KEY, title TEXT DEFAULT '',
  text TEXT DEFAULT '', meta TEXT DEFAULT '{}', fetched_at REAL NOT NULL);
CREATE TABLE kv(k TEXT PRIMARY KEY, v TEXT);
"""


def test_queue_lease_store(tmp_path):
    con = store.connect(str(tmp_path / "t.db"))
    assert store.enqueue(con, [("https://a.example/x", "h1", 0, 0.0)]) == 1
    assert store.enqueue(con, [("https://a.example/x", "h1", 0, 0.0)]) == 0
    tasks = store.lease(con, 4)
    assert len(tasks) == 1
    store.store_item(con, "https://a.example/x", "T", "hello world text", {})
    store.mark(con, tasks[0][0], "done")
    assert store.pending(con) == 0
    rows = store.search_items(con, "hello")
    assert rows and rows[0][0] == "https://a.example/x"
    con.close()


def test_migrate_adds_v03_columns(tmp_path):
    # a pre-v0.3 database (no challenges/note) opens and gains the columns
    db = str(tmp_path / "old.db")
    con = sqlite3.connect(db)
    con.executescript(OLD_TASKS)
    con.execute("INSERT INTO tasks(url,url_hash,added_at)"
                " VALUES('https://a.example/x','h1',1.0)")
    con.commit()
    con.close()
    c = store.connect(db)
    cols = [r[1] for r in c.execute("PRAGMA table_info(tasks)")]
    assert "challenges" in cols and "note" in cols
    row = c.execute("SELECT status,attempts,challenges,note"
                    " FROM tasks").fetchone()
    assert row == ("queued", 0, 0, "")
    c.close()
