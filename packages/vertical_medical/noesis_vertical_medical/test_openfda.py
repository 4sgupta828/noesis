"""Offline test for the openFDA drug-label connector (injected fixture)."""
from __future__ import annotations

import asyncio

from noesis_vertical_medical.openfda import OpenFdaConnector, label_facets, label_markdown

_REC = {
    "set_id": "abc-123",
    "openfda": {"brand_name": ["Metfورمin"], "generic_name": ["METFORMIN HYDROCHLORIDE"],
                "route": ["ORAL"], "manufacturer_name": ["Acme Pharma"], "product_type": ["HUMAN PRESCRIPTION DRUG"]},
    "indications_and_usage": ["Indicated as an adjunct to diet and exercise to improve glycemic control in adults with type 2 diabetes."],
    "dosage_and_administration": ["Starting dose 500 mg orally twice daily with meals."],
    "warnings": ["Lactic acidosis is a rare but serious metabolic complication."],
}


def test_label_markdown_and_facets():
    md = label_markdown(_REC)
    assert md.startswith("# ") and "Indications and Usage" in md
    assert "type 2 diabetes" in md.lower()
    f = label_facets(_REC)
    assert f["generic"] == "metformin hydrochloride" and f["route"] == "oral"
    assert f["source_kind"] == "drug_label"


def test_connector_discovers_from_injected_records():
    conn = OpenFdaConnector(labels=[_REC])
    ents = asyncio.run(conn.discover_entities({}))
    assert ents[0].native_id == "abc-123"
    docs = asyncio.run(conn.list_documents(ents[0]))
    body = asyncio.run(conn.fetch_artifact(docs[0]))
    assert b"Dosage and Administration" in body
