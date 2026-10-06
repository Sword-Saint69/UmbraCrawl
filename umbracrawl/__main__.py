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
    args = ap.parse_args(argv)
    query = prompt.to_query(" ".join(args.prompt))
    stats = run.research(query, args.db, args.workers)
    print(answer.compose(query, args.db))
    print(f"\n[crawled={stats['pages']} blocked={stats['blocked']}]",
          file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
