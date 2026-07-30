"""Content-type-keyed parser registry — domain-free.

Kernel ships plain-text + a stdlib HTML text-extractor (zero extra deps). Heavier
parsers (PDF via docling, XBRL for the financial vertical) register the same
`Parser` Protocol — the pipeline dispatches by `content_type`, so a vertical adds
a format without kernel edits.
"""
from __future__ import annotations

from html.parser import HTMLParser as _StdHTMLParser

from noesis_kernel.contract.protocols import Parser


class ParserRegistry:
    def __init__(self) -> None:
        self._by_type: dict[str, Parser] = {}

    def register(self, parser: Parser) -> None:
        for ct in parser.content_types:
            self._by_type[ct] = parser

    def for_content_type(self, content_type: str) -> Parser:
        # exact, then prefix (e.g. "text/plain; charset=utf-8" → "text/plain")
        base = content_type.split(";", 1)[0].strip().lower()
        if base in self._by_type:
            return self._by_type[base]
        raise KeyError(f"no parser registered for content_type {content_type!r}")

    def supports(self, content_type: str) -> bool:
        return content_type.split(";", 1)[0].strip().lower() in self._by_type


class PlainTextParser:
    content_types = ("text/plain", "text/markdown")

    def parse(self, raw: bytes, *, content_type: str) -> str:
        return raw.decode("utf-8", errors="replace")


class _TextExtractor(_StdHTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self._parts: list[str] = []
        self._skip = 0

    def handle_starttag(self, tag, attrs):  # noqa: ANN001
        if tag in ("script", "style"):
            self._skip += 1

    def handle_endtag(self, tag):  # noqa: ANN001
        if tag in ("script", "style") and self._skip:
            self._skip -= 1

    def handle_data(self, data):  # noqa: ANN001
        if not self._skip and data.strip():
            self._parts.append(data.strip())


class HtmlParser:
    content_types = ("text/html", "application/xhtml+xml")

    def parse(self, raw: bytes, *, content_type: str) -> str:
        ex = _TextExtractor()
        ex.feed(raw.decode("utf-8", errors="replace"))
        return "\n\n".join(ex._parts)


def default_registry() -> ParserRegistry:
    reg = ParserRegistry()
    reg.register(PlainTextParser())
    reg.register(HtmlParser())
    return reg
