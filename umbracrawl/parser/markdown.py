"""Stdlib HTML to Markdown for LLM-ready output."""
from __future__ import annotations

from html.parser import HTMLParser
from urllib.parse import urljoin


class _Md(HTMLParser):
    def __init__(self, base: str) -> None:
        super().__init__()
        self.base = base
        self.out: list[str] = []
        self._skip = 0
        self._link: str | None = None
        self._link_text = ""

    def _w(self, s: str) -> None:
        self.out.append(s)

    def handle_starttag(self, tag: str, attrs: list) -> None:
        if tag in ("script", "style", "nav", "footer", "header"):
            self._skip += 1
            return
        if self._skip:
            return
        if tag in ("h1", "h2", "h3"):
            self._w("\n" + "#" * int(tag[1]) + " ")
        elif tag == "p":
            self._w("\n\n")
        elif tag == "br":
            self._w("\n")
        elif tag == "li":
            self._w("\n- ")
        elif tag in ("code",):
            self._w("`")
        elif tag == "pre":
            self._w("\n```\n")
        elif tag == "a":
            href = dict(attrs).get("href", "")
            self._link = urljoin(self.base, href) if href else None
            self._link_text = ""

    def handle_endtag(self, tag: str) -> None:
        if tag in ("script", "style", "nav", "footer", "header"):
            if self._skip:
                self._skip -= 1
            return
        if self._skip:
            return
        if tag in ("h1", "h2", "h3", "p"):
            self._w("\n")
        elif tag == "code":
            self._w("`")
        elif tag == "pre":
            self._w("\n```\n")
        elif tag == "a":
            text = (self._link_text or "").strip()
            if self._link:
                self._w(f"[{text}]({self._link})")
            elif text:
                self._w(text)
            self._link = None

    def handle_data(self, data: str) -> None:
        if self._skip:
            return
        s = " ".join(data.split())
        if s:
            if self._link is not None:
                self._link_text += s + " "
            else:
                self._w(s + " ")


def to_markdown(url: str, html: str) -> str:
    doc = _Md(url)
    doc.feed(html)
    text = "".join(doc.out)
    lines = [ln.rstrip() for ln in text.splitlines()]
    return "\n".join(lines).strip() + "\n"
