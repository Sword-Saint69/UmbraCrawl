"""python -m umbracrawl "research a book Dune" """
from __future__ import annotations

import argparse
import os
import sys

from .cli import answer, prompt, run


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="umbracrawl")
    ap.add_argument("prompt", nargs="+", help="e.g. research a book Dune")
    ap.add_argument("--db", default=os.path.expanduser("~/.umbracrawl.db"))
    ap.add_argument("--workers", type=int, default=run.WORKERS)
    ap.add_argument("--fresh", action="store_true",
                    help="re-crawl even if rows exist")
    ap.add_argument("--max-pages", type=int, default=0,
                    help="stop after N stored pages (0 = uncapped)")
    ap.add_argument("--max-depth", type=int, default=0,
                    help="follow outlinks to this depth (0 = uncapped)")
    ap.add_argument("--timeout", type=int, default=0,
                    help="stop after N seconds (0 = no limit)")
    args = ap.parse_args(argv)
    query = prompt.to_query(" ".join(args.prompt))
    stats = run.research(query, args.db, args.workers, fresh=args.fresh,
                         max_pages=args.max_pages, max_depth=args.max_depth,
                         timeout=args.timeout)
    print(answer.compose(query, args.db))
    print(f"\n[crawled={stats['pages']} blocked={stats['blocked']}]",
          file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
