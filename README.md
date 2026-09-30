# UmbraCrawl (v0.1)

Local-first research crawler. You type `research a book`, it crawls the full
result frontier and answers from a local SQLite store. 4 workers, no page cap,
no servers.

## Use

```bash
python -m umbracrawl "research a book Dune by Frank Herbert"
python -m umbracrawl "research the author Octavia Butler" --db ~/.umbracrawl.db
```

Repeat queries answer from SQLite with zero network unless rows go stale.

## Layout (v0.1)

```
umbracrawl/
  storage/sqlite.py      tasks queue, items, FTS5
  scheduler/dedupe.py    URL normalize + hash
  scheduler/queue.py     priority + leasing
  scheduler/politeness.py per-host delay
  fetchers/http_impersonate.py  curl_cffi, chrome124 profile
  search.py              result-link harvest, no cap
  extract.py             stdlib title/text/link extractor
  cli/prompt.py run.py answer.py
```

## Versions

v0.1 foundation (this) -> v0.2 identity -> v0.3 escalation ->
v0.4 parse -> v0.5 harden -> v1.0 stable. See `docs/`.
