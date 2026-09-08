"""The source-level floor: material a vertical marks as NOT EVIDENCE can never reach an answer.

A per-request exclusion is a caller's promise to remember. `never_return` is the source's own floor,
so a caller that forgets — or a new code path nobody thought about — still cannot pull commentary
into a grounded answer. These tests read the generated SQL, so they need no database.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from noesis_kernel.retrieval.postgres import PostgresRetrievalSource

DSN = "postgresql://unused/unused"


@dataclass
class Req:
    tenant_id: str = "demo"
    workspace_id: str | None = None
    query: str = "metformin in ckd"
    k: int = 10
    facets: dict = field(default_factory=dict)
    exclude_facets: dict = field(default_factory=dict)


def _sql(src: PostgresRetrievalSource, req) -> tuple[str, list]:
    """The WHERE clause the source would run, built without touching a database."""
    return src._filter_sql(req)   # noqa: SLF001 — reading the generated SQL is the point


def test_a_never_return_facet_is_excluded_even_when_the_caller_excludes_nothing():
    src = PostgresRetrievalSource(DSN, never_return={"source_kind": ("transcript",)})
    sql, params = _sql(src, Req())
    assert "source_kind" in params
    assert "transcript" in [v for p in params if isinstance(p, list) for v in p]
    assert "NOT (facets ?" in sql


def test_the_floor_merges_with_a_callers_own_exclusion_rather_than_replacing_it():
    src = PostgresRetrievalSource(DSN, never_return={"source_kind": ("transcript",)})
    sql, params = _sql(src, Req(exclude_facets={"source_kind": "retracted"}))
    banned = [v for p in params if isinstance(p, list) for v in p]
    assert "transcript" in banned and "retracted" in banned


def test_without_a_floor_nothing_is_excluded():
    src = PostgresRetrievalSource(DSN)
    sql, params = _sql(src, Req())
    assert "NOT (facets ?" not in sql


def test_the_medical_vertical_declares_transcripts_non_evidence():
    from noesis_vertical_medical.manifest import build_manifest
    m = build_manifest()
    assert "transcript" in (m.non_evidence_facets or {}).get("source_kind", ())
