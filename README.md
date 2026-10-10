# UmbraCrawl (v1.0)

Local-first research crawler. You type `research a book`, it crawls the full
result frontier and answers from a local SQLite store. 4 workers, no page cap,
no servers. Stable release: 55 tests green, docs in `docs/`.

<p align="center">
  <video src="docs/brag.mp4" poster="docs/brag.jpg" width="720" controls muted playsinline></video>
</p>
<p align="center"><sub>20-second launch reel — typed prompt, frontier crawl, browser escalation chain, cited answer from the local store. Made with the <a href="https://github.com/latent-spaces/brag">/brag</a> skill.</sub></p>

## Install

From the repo root:

```bash
python3 -m venv ~/.local/share/umbracrawl/venv
~/.local/share/umbracrawl/venv/bin/pip install -e .
```

Pulls `curl_cffi`, `lxml`, `pyyaml`, and `cssselect`. The browser slots import
lazily, so nothing needs a browser binary to install or to crawl over HTTP.
Run it with the venv interpreter:

```bash
~/.local/share/umbracrawl/venv/bin/python -m umbracrawl --help
# or, after `source ~/.local/share/umbracrawl/venv/bin/activate`:
python -m umbracrawl "research a book Dune by Frank Herbert"
```

Tests (adds the pytest dev extra):

```bash
~/.local/share/umbracrawl/venv/bin/pip install -e ".[dev]"
~/.local/share/umbracrawl/venv/bin/python -m pytest tests/ -q
```

## Use

```bash
python -m umbracrawl "research a book Dune by Frank Herbert"
python -m umbracrawl "research the author Octavia Butler" --db ~/.umbracrawl.db
python -m umbracrawl "research a book Dune" --fresh   # re-crawl stored URLs
```

Each run starts with a live search; page bodies come from SQLite when fresh.
Repeat queries skip stored URLs unless stale or `--fresh` is given.

## Use from OpenCode

Registered globally as the `umbracrawl_research` tool via
`~/.config/opencode/plugin/umbracrawl/index.js` (its path listed in the
`plugins` array of `~/.config/opencode/opencode.json`; the plugin resolves
`@opencode-ai/plugin` from `~/.config/opencode/node_modules`). The tool runs
this same CLI against `~/.umbracrawl.db` and takes optional `fresh`, `db`,
`max_pages`, `max_depth`, and `timeout` arguments. The crawler itself is
installed editable at `~/.local/share/umbracrawl/venv` (override the
interpreter with `UMBRACRAWL_PYTHON` and the store with `UMBRACRAWL_DB`).

## How a page is fetched

1. HTTP with chrome124 impersonation, bound identity (session + proxy + profile).
2. On challenge: one HTTP retry, then the borrowed browser chain (Camoufox,
   then Patchright), each tried in order.
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
