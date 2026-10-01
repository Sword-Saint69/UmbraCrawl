import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from umbracrawl.storage import sqlite as store


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
