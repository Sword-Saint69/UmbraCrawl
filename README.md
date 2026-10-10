# UmbraCrawl (v1.0)

Local-first research crawler. You type `research a book`, it crawls the full
result frontier and answers from a local SQLite store. 4 workers, no page cap,
no servers. Stable release: 30 tests green, docs in `docs/`.

## Use

```bash
python -m umbracrawl "research a book Dune by Frank Herbert"
python -m umbracrawl "research the author Octavia Butler" --db ~/.umbracrawl.db
python -m umbracrawl "research a book Dune" --fresh   # re-crawl stored URLs
```

Each run starts with a live search; page bodies come from SQLite when fresh.
Repeat queries skip stored URLs unless stale or `--fresh` is given.

## How a page is fetched

1. HTTP with chrome124 impersonation, bound identity (session + proxy + profile).
2. On challenge: one HTTP retry, then the borrowed Camoufox browser slot.
3. Still walled, or no browser installed: task poisoned with its reason noted.

## Layout

```
umbracrawl/
  storage/sqlite.py      tasks queue (attempts, challenges, notes), items, FTS5
  scheduler/dedupe.py    URL normalize + hash
  scheduler/queue.py     priority + leasing
  scheduler/politeness.py per-host delay
  fetchers/http_impersonate.py  curl_cffi, challenge detector
  fetchers/router.py     http -> retry -> browser -> poison
  fetchers/camoufox_pool.py     borrowed Camoufox slot
  fetchers/patchright_pool.py   fallback patched-Chromium slot
  identity/sessions.py   cookie isolation, 2-strike retirement
  identity/proxies.py    sticky proxy, cooldown
  identity/fingerprints.py      one OS choice drives every field
  identity/leakcheck.py  4-check gate (webdriver, CDP, WebGL, header order)
  search.py              result-link harvest, no cap
  extract.py             stdlib title/text/link extractor
  parser/adaptive.py     multi-candidate field extraction
  parser/selectors.yml   book-research field specs
  parser/relearn.py      snapshots, drift diffs, win rates
  parser/markdown.py     HTML to Markdown
  observability/metrics.py  counters, JSONL log, alerts
  cli/prompt.py run.py answer.py
```

## Versions

v0.1 foundation, v0.2 identity, v0.3 escalation,
v0.4 parse, v0.5 harden, v1.0 stable (this). See `docs/` and `CHANGELOG.md`.
