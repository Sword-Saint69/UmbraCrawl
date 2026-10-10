---
name: umbracrawl-research
description: Local-first research crawl with UmbraCrawl. Use when the user wants to research a book, author, or topic and get an answer grounded in crawled pages stored in a local SQLite store.
---

# UmbraCrawl Research

Local-first crawler. A prompt fans out to a result frontier (4 workers, no page
cap), pages are fetched over impersonated HTTP with a browser fallback chain,
and the answer is composed from the local SQLite store. No servers.

## Run it

```bash
python -m umbracrawl "research a book Dune by Frank Herbert"
python -m umbracrawl "research the author Octavia Butler" --db ~/.umbracrawl.db
python -m umbracrawl "research a book Dune" --fresh   # re-crawl stored URLs
```

Full flags: `--db`, `--workers`, `--fresh`, `--max-pages`, `--max-depth`,
`--timeout`. `0` means uncapped/unlimited for pages, depth, and timeout.

```bash
python -m umbracrawl --help
```

## Rules

- Each run starts with a live search; page bodies come from SQLite when fresh.
- Repeat queries skip stored URLs unless stale or `--fresh` is passed.
- Fetch order per page: impersonated HTTP (chrome124) -> one HTTP retry ->
  Camoufox -> Patchright -> poison with reason noted.
- Store defaults to `~/.umbracrawl.db`. Override with `--db`, `UMBRACRAWL_DB`,
  or `UMBRACRAWL_PYTHON` for the interpreter.
- Quote the whole prompt. Keep prompts in the form `research a book X` or
  `research the author Y` so the planner routes correctly.
- Report what was crawled (sources, challenges) separately from the answer,
  and say when a page was walled rather than inventing its contents.
