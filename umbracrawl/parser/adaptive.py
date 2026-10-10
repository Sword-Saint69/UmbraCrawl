"""Adaptive multi-candidate field extraction over lxml trees.

Each field lists CSS/XPath candidates in preference order. The winner is
the first candidate with non-empty text, re-ranked by historical win rate
so proven selectors float up and drifted ones sink.
"""
from __future__ import annotations

from lxml import html as _lhtml


def _texts(tree, sel: dict) -> str:
    try:
        if "css" in sel:
            els = tree.cssselect(sel["css"])
            return " ".join(e.text_content().strip() for e in els).strip()
        if "xpath" in sel:
            out = tree.xpath(sel["xpath"])
            bits = [o.strip() if isinstance(o, str) else
                    o.text_content().strip() for o in out]
            return " ".join(b for b in bits if b).strip()
    except Exception:
        return ""
    return ""


def _score(text: str, wins: int, tries: int) -> float:
    if not text:
        return 0.0
    prior = (wins / tries) if tries else 0.5
    density = min(len(text), 300) / 300.0
    return 0.5 * density + 0.5 * prior


def extract_fields(page_html: str, specs: dict,
                   stats: dict | None = None,
                   record=None) -> dict:
    """specs: {field: [{css|xpath: ...}, ...]}. Returns
    {field: {'value','selector','score'} or None}.

    record(field, selector, hit) — optional callback invoked once per
    candidate so the caller can feed live win rates back into a later run.
    """
    stats = stats or {}
    try:
        tree = _lhtml.fromstring(page_html)
    except Exception:
        return {f: None for f in specs}
    out = {}
    for field, sels in specs.items():
        best, best_sel, best_score = "", None, 0.0
        for sel in sels:
            text = _texts(tree, sel)
            sel_key = sel.get("css", sel.get("xpath", ""))
            key = f"{field}|{sel_key}"
            w, t = stats.get(key, (0, 0))
            s = _score(text, w, t)
            if record is not None:
                record(field, sel_key, bool(text))
            if text and (best_sel is None or s > best_score):
                best, best_sel, best_score = text, sel, s
        out[field] = ({"value": best, "selector": best_sel,
                       "score": round(best_score, 3)} if best_sel else None)
    return out


def recall(fields: dict) -> float:
    got = sum(1 for v in fields.values() if v)
    return got / len(fields) if fields else 1.0
