"""Result-link harvest. No cap: every result URL joins the frontier."""
from __future__ import annotations

import re
from urllib.parse import quote_plus

from .fetchers.http_impersonate import fetch

_HREF = re.compile(r'class="result__a"[^>]*href="([^"]+)"')
_FALLBACK = re.compile(r'href="(https?://[^"]+)"')


def search_links(query: str, fetcher=fetch) -> list[str]:
    url = "https://html.duckduckgo.com/html/?q=" + quote_plus(query)
    try:
        res = fetcher(url)
    except Exception:
        return []
    if res.get("status") != 200:
        return []
    links = _HREF.findall(res.get("text", ""))
    if not links:
        links = [u for u in _FALLBACK.findall(res.get("text", ""))
                 if "duckduckgo.com" not in u][:20]
    seen, out = set(), []
    for u in links:
        if u not in seen:
            seen.add(u)
            out.append(u)
    return out
