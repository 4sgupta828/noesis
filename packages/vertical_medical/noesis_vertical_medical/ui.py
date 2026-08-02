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

    def coverage_plan(self):
        """Declared source inventory + condition roadmap (covered vs remaining) for the
        admin coverage page. Paired with live corpus counts by the admin endpoint."""
        from .coverage import coverage_plan
        return coverage_plan()

    def console(self):
        """Research-console copy for this vertical (heading + input placeholder +
        example prompts). Keeps domain wording out of the shared web shell."""
        return {
            "heading": "What does the evidence show?",
            "placeholder": "Ask a clinical research question…",
            # A picker of real, current questions the corpus can answer — the web shell shows a
            # random one as the intake prompt each load (kept here so wording stays domain-owned).
            "examples": [
                "What is the evidence for lecanemab in early Alzheimer disease, and how large is the benefit?",
                "How effective is tirzepatide for weight loss, and what are its main adverse effects?",
                "What do trials show for CAR-T therapy in relapsed or refractory multiple myeloma?",
                "How do SGLT2 inhibitors affect heart-failure and kidney outcomes?",
                "What is the cardiovascular benefit of semaglutide in patients with obesity?",
                "How do IL-23 inhibitors compare with IL-17 inhibitors for plaque psoriasis?",
                "What is the evidence for resmetirom in MASH (NASH), and which patients benefit?",
                "How effective are direct-acting antivirals for hepatitis C, and what are the cure rates?",
                "What treatments are being studied for glioblastoma, and have any improved survival?",
                "How does osimertinib perform in EGFR-mutated non-small-cell lung cancer?",
                "What is the evidence for pembrolizumab in advanced melanoma?",
                "Which biologics are studied for inflammatory bowel disease, and how effective are they?",
                "What do trials show for mavacamten in hypertrophic cardiomyopathy?",
                "How effective are antifibrotics like pirfenidone and nintedanib in pulmonary fibrosis?",
                "What is the evidence for bispecific antibodies in relapsed lymphoma?",
                "How well do JAK inhibitors work for rheumatoid arthritis, and what are the safety concerns?",
            ],
        }

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
