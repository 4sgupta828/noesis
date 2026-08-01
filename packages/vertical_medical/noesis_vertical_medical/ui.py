"""Medical UI declaration — renders per-vertical with zero app edits."""
from __future__ import annotations


class _EntityView:
    def __init__(self, entity_type, columns, sections):
        self.entity_type = entity_type
        self._c, self._s = columns, sections
    def list_columns(self): return list(self._c)
    def detail_sections(self): return list(self._s)


from . import links as _links


class MedicalUI:
    def source_url(self, document_id, quote=None):
        return _links.source_url(document_id, quote)

    def navigation(self):
        return [
            {"key": "trials", "label": "Trials", "entity_type": "trial"},
            {"key": "research", "label": "Research", "view": "agent"},
        ]

    def search_facets(self):
        return [
            {"key": "condition", "label": "Condition", "control": "select"},
            {"key": "phase", "label": "Phase", "control": "multiselect"},
            {"key": "status", "label": "Status", "control": "select"},
            {"key": "intervention", "label": "Intervention", "control": "text"},
        ]

    def entity_views(self):
        return [_EntityView(
            "trial",
            columns=[
                {"key": "native_id", "label": "NCT", "kind": "text"},
                {"key": "condition", "label": "Condition", "kind": "text"},
                {"key": "phase", "label": "Phase", "kind": "text"},
                {"key": "status", "label": "Status", "kind": "badge"},
            ],
            sections=[
                {"title": "Overview", "fields": ["native_id", "condition", "phase", "status"]},
                {"title": "Summary", "fields": ["brief_summary"]},
            ],
        )]

    def citation_renderers(self):
        return {"block_span": "trial-quote", "url": "web-link"}

    def deliverable_renderers(self):
        return {"memo": "memo-doc", "comparison_table": "table-grid"}
