"""Stdlib page extractor: title, text, outlinks."""
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
        self._main_depth = 0  # inside <main>/<article>: boilerplate cut
        self.chunks: list[str] = []
        self._chunk_main: list[bool] = []
        self.links: list[tuple[str, str]] = []
        self._cur: str | None = None
        self._cur_text = ""

    def handle_starttag(self, tag: str, attrs: list) -> None:
        a = dict(attrs)
        if tag == "title":
            self._in_title = True
        elif tag == "meta" and a.get("name", "").lower() == "description":
            self.desc = a.get("content", "")
        elif tag in ("main", "article"):
            self._main_depth += 1
        if tag in ("script", "style", "nav", "footer", "header", "aside"):
            self._skip += 1
        elif tag == "a" and "href" in a and self._skip == 0:
            self._cur = urljoin(self.base, a["href"])
            self._cur_text = ""

    def handle_endtag(self, tag: str) -> None:
        if tag == "title":
            self._in_title = False
        elif tag in ("main", "article") and self._main_depth:
            self._main_depth -= 1
        if tag in ("script", "style", "nav", "footer", "header",
                   "aside") and self._skip:
            self._skip -= 1
        elif tag == "a" and self._cur is not None:
            self.links.append((self._cur, self._cur_text.strip()))
            self._cur = None
        elif tag in ("p", "h1", "h2", "h3", "h4", "li") \
                and self._skip == 0:
            self.chunks.append("")
            self._chunk_main.append(self._main_depth > 0)

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
                    self._chunk_main.append(self._main_depth > 0)
                self.chunks[-1] += (" " + s)


def extract(url: str, html: str) -> dict:
    doc = _Doc(url)
    doc.feed(html)
    paired = [(c.strip(), m) for c, m in zip(doc.chunks, doc._chunk_main)]
    main = [c for (c, m) in paired if c and m]
    use = main if main else [c for (c, _) in paired if c]
    text = "\n".join(use)
    links = [(u, t) for (u, t) in doc.links
             if u.startswith(("http://", "https://"))]
    return {"url": url, "title": doc.title.strip(),
            "description": doc.desc.strip(), "text": text, "links": links}
