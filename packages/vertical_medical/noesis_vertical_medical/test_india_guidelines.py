"""IndiaGuidelinesConnector — offline (no network): discovery matches condition tags, documents carry
guideline-tier + source_country=IN facets, and fetch_artifact emits the curated summary bytes."""
from __future__ import annotations

import asyncio

from noesis_vertical_medical.india_guidelines import IndiaGuidelinesConnector, INDIA_GUIDELINES


def _run(c): return asyncio.run(c)


def test_discovery_matches_condition_tags():
    conn = IndiaGuidelinesConnector()
    ents = _run(conn.discover_entities({"query": "tuberculosis"}))
    ids = [e.native_id for e in ents]
    assert "ntep-tb" in ids
    # facets mark it guideline-tier + India
    ntep = next(e for e in ents if e.native_id == "ntep-tb")
    assert ntep.facets.get("pub_type") == "guideline" and ntep.facets.get("source_country") == "IN"


def test_empty_query_returns_whole_registry():
    conn = IndiaGuidelinesConnector()
    ents = _run(conn.discover_entities({"query": ""}))
    assert len(ents) == len(INDIA_GUIDELINES)


def test_list_and_fetch_curated_summary():
    conn = IndiaGuidelinesConnector()
    ent = next(e for e in _run(conn.discover_entities({"query": "dengue"})))  # noqa: RUF015
    docs = _run(conn.list_documents(ent))
    assert docs and docs[0].facets.get("source_country") == "IN"
    md = _run(conn.fetch_artifact(docs[0])).decode("utf-8")
    # the dengue safety facts (the eval's traps) are present in the curated summary
    assert "paracetamol" in md.lower() and "avoid nsaids" in md.lower()
    assert "guideline-tier" in md.lower()


def test_injected_document_overrides_text():
    conn = IndiaGuidelinesConnector(documents=[{"id": "ntep-tb", "text": "VERIFIED FULL TEXT."}])
    ent = next(e for e in _run(conn.discover_entities({"query": "tb"})) if e.native_id == "ntep-tb")
    md = _run(conn.fetch_artifact(_run(conn.list_documents(ent))[0])).decode("utf-8")
    assert "VERIFIED FULL TEXT." in md
