"""Regulatory UI declaration — how the neutral app shell renders this vertical.

The vertical declares navigation, search facets, per-entity list/detail schemas,
and which renderer to use per citation/deliverable kind — all as DATA, so a new
domain gets a coherent, responsive UI with zero app edits. (The shell itself is
built clean in P4 per the locked UI principles: mobile-first, minimal, intuitive.)
"""
from __future__ import annotations


class _EntityView:
    def __init__(self, entity_type: str, columns: list[dict], sections: list[dict]):
        self.entity_type = entity_type
        self._columns = columns
        self._sections = sections

    def list_columns(self) -> list[dict]:
        return list(self._columns)

    def detail_sections(self) -> list[dict]:
        return list(self._sections)


class RegulatoryUI:
    def navigation(self) -> list[dict]:
        return [
            {"key": "cases", "label": "Cases", "entity_type": "case"},
            {"key": "research", "label": "Research", "view": "agent"},
        ]

    def search_facets(self) -> list[dict]:
        return [
            {"key": "jurisdiction", "label": "Jurisdiction", "control": "select"},
            {"key": "doc_family", "label": "Document type", "control": "multiselect"},
        ]

    def entity_views(self) -> list:
        return [
            _EntityView(
                "case",
                columns=[
                    {"key": "native_id", "label": "Docket", "kind": "text"},
                    {"key": "jurisdiction", "label": "State", "kind": "text"},
                    {"key": "title", "label": "Caption", "kind": "text"},
                ],
                sections=[
                    {"title": "Overview", "fields": ["native_id", "jurisdiction", "title"]},
                    {"title": "Filings", "fields": ["filings"]},
                ],
            ),
        ]

    def citation_renderers(self) -> dict[str, str]:
        # locator.kind → renderer id the shell knows how to draw
        return {"block_span": "pdf-quote", "url": "web-link"}

    def deliverable_renderers(self) -> dict[str, str]:
        return {"memo": "memo-doc", "comparison_table": "table-grid"}
