"""Fetch router: cheap HTTP first, browser slot only on repeated challenge.

Driven by the per-task challenge count only. Transient failures have their
own attempts budget and never push a task toward the browser.
"""
from __future__ import annotations


def route(challenges: int) -> str:
    """Return 'http', 'browser', or 'poison'."""
    if challenges <= 1:
        return "http"  # first challenge: one cheap retry
    if challenges <= 3:
        return "browser"
    return "poison"
