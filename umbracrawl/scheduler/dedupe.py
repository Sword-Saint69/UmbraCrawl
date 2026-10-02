"""URL normalize + hash. Same URL in any coat gets one queue row."""
from __future__ import annotations

import hashlib
from urllib.parse import urlparse, urlunparse, parse_qsl, urlencode


def normalize(url: str) -> str:
    p = urlparse(url.strip())
    host = p.hostname.lower() if p.hostname else ""
    if (p.scheme == "http" and p.port == 80) or \
       (p.scheme == "https" and p.port == 443):
        netloc = host
    elif p.port:
        netloc = f"{host}:{p.port}"
    else:
        netloc = host
    query = urlencode(sorted(parse_qsl(p.query, keep_blank_values=True)))
    path = p.path or "/"
    return urlunparse((p.scheme.lower(), netloc, path, "", query, ""))


def url_hash(url: str) -> str:
    return hashlib.sha1(normalize(url).encode()).hexdigest()
