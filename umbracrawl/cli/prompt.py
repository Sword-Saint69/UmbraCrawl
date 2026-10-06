"""Turn `research a book ...` into a search query."""
from __future__ import annotations

import re

_LEAD = re.compile(r"^\s*research\s+(a\s+|an\s+|the\s+)?", re.IGNORECASE)


def to_query(prompt: str) -> str:
    q = _LEAD.sub("", prompt).strip()
    return q or prompt.strip()
