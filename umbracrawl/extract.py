"""Stdlib page extractor: title, text, outlinks. v0.4 grows this."""
from __future__ import annotations

from html.parser import HTMLParser
from urllib.parse import urljoin


class _Doc(HTMLParser):
    def __init__(self, base: str) -> None:
        super().__init__()
        self.base = base
        self.title = ""
        self.desc = ""
        self._in_title = False
        self._skip = 0
        self.chunks: list[str] = []
        self.links: list[tuple[str, str]] = []
        self._cur: str | None = None
        self._cur_text = ""

    def handle_starttag(self, tag: str, attrs: list) -> None:
        a = dict(attrs)
        if tag == "title":
            self._in_title = True
        elif tag == "meta" and a.get("name", "").lower() == "description":
            self.desc = a.get("content", "")
        elif tag in ("script", "style", "nav", "footer"):
            self._skip += 1
        elif tag == "a" and "href" in a and self._skip == 0:
            self._cur = urljoin(self.base, a["href"])
            self._cur_text = ""

    def handle_endtag(self, tag: str) -> None:
        if tag == "title":
            self._in_title = False
        elif tag in ("script", "style", "nav", "footer") and self._skip:
            self._skip -= 1
        elif tag == "a" and self._cur is not None:
            self.links.append((self._cur, self._cur_text.strip()))
            self._cur = None
        elif tag in ("p", "h1", "h2", "h3", "h4", "li"):
            self.chunks.append("")

    def handle_data(self, data: str) -> None:
        if self._in_title:
            self.title += data
        elif self._skip:
            return
        else:
            s = data.strip()
            if s:
                if self._cur is not None:
                    self._cur_text += " " + s
                if not self.chunks:
                    self.chunks.append("")
                self.chunks[-1] += (" " + s)


def extract(url: str, html: str) -> dict:
    doc = _Doc(url)
    doc.feed(html)
    text = "\n".join(c.strip() for c in doc.chunks if c.strip())
    links = [(u, t) for (u, t) in doc.links
             if u.startswith(("http://", "https://"))]
    return {"url": url, "title": doc.title.strip(),
            "description": doc.desc.strip(), "text": text, "links": links}
