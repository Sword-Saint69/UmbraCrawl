"""Fetch router: cheap HTTP first, browser slot only on repeated challenge."""
from __future__ import annotations

HTTP_TRIES = 2


def route(challenges: int, http_attempts: int) -> str:
    """Return 'http', 'browser', or 'poison'."""
    if challenges <= 0:
        return "http"
    if http_attempts < HTTP_TRIES:
        return "http"
    if challenges <= HTTP_TRIES + 1:
        return "browser"
    return "poison"
