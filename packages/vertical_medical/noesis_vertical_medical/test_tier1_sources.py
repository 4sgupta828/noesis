"""Offline tests for the Tier-1 connectors (fixture-injected, no network) +
source tagging + source-utility stats. Free-API fixtures are bundled in data/."""
from __future__ import annotations

import asyncio
import json
from pathlib import Path

from noesis_kernel.providers.embeddings import FakeEmbedder
from noesis_kernel.providers.llm import LLMResult
from noesis_kernel.research.budget import BudgetState
from noesis_kernel.research.react import AgentStep, ClaimOut, run_react

import noesis_vertical_medical as med
from noesis_vertical_medical.cdc import CdcConnector
from noesis_vertical_medical.europepmc import EuropePmcConnector
from noesis_vertical_medical.faers import FaersConnector

_DATA = Path(__file__).resolve().parent / "data"
def _load(name): return json.loads((_DATA / name).read_text())


def _roundtrip(conn):
    ents = asyncio.run(conn.discover_entities({}))
    assert ents, "no entities from fixture"
    docs = asyncio.run(conn.list_documents(ents[0]))
    body = asyncio.run(conn.fetch_artifact(docs[0]))
    return ents[0], body


def test_europepmc_article_doc_and_source_tag():
    conn = EuropePmcConnector(articles=_load("europepmc_sample.json"))
    ent, body = _roundtrip(conn)
    assert ent.source_key == "europepmc"
    assert ent.facets.get("source_kind") == "article"
    assert b"Abstract" in body and body.startswith(b"#")


def test_faers_report_doc_and_source_tag():
    conn = FaersConnector(reports=_load("faers_sample.json"))
    ent, body = _roundtrip(conn)
    assert ent.source_key == "faers"
    assert ent.facets.get("source_kind") == "adverse_event"
    assert b"Adverse Event Report" in body


def test_cdc_doc_and_source_tag():
    conn = CdcConnector(datasets=_load("cdc_sample.json"))
    ent, body = _roundtrip(conn)
    assert ent.source_key == "cdc"
    assert ent.facets.get("source_kind") == "public_health"


def test_manifest_has_all_tier1_connectors():
    keys = set(med.manifest.connectors)
    assert {"clinicaltrials", "openfda", "europepmc", "faers", "dailymed", "cdc"} <= keys


class _LLM:
    def __init__(self, steps): self._s = list(steps)
    async def complete(self, *, system, messages, response_format, max_tokens=2048, temperature=None):
        return LLMResult(parsed=self._s.pop(0), output_tokens=5)


def test_source_stats_tracks_retrieved_vs_cited():
    # Two sources retrieved; only one produces a verified (cited) claim.
    from noesis_kernel.retrieval.memory import IndexedBlock, InMemoryRetrievalSource
    from noesis_kernel.contract.dto import Locator, RetrievalRequest
    from noesis_kernel.retrieval.multi import MultiSourceRetriever
    a = InMemoryRetrievalSource(); a.add(IndexedBlock(
        block_id="p1", document_id="d", tenant_id="t", source_key="europepmc",
        text="Metformin reduced cardiovascular events in the trial.",
        locator=Locator("block_span", "d", {"block_id": "p1"})))
    b = InMemoryRetrievalSource(); b.add(IndexedBlock(
        block_id="q1", document_id="e", tenant_id="t", source_key="faers",
        text="Nausea was a reported adverse event for metformin.",
        locator=Locator("block_span", "e", {"block_id": "q1"})))
    multi = MultiSourceRetriever({"europepmc": a, "faers": b})
    llm = _LLM([
        AgentStep(action="search", query="metformin cardiovascular events reported"),
        AgentStep(action="answer", claims=[
            ClaimOut(text="cv benefit", atom_id="a1",
                     quote="metformin reduced cardiovascular events in the trial")]),
    ])
    res = asyncio.run(run_react(question="metformin cardiovascular?", llm=llm,
                               embedder=FakeEmbedder(dim=16), source=multi,
                               tenant_id="t", budget=BudgetState(max_calls=10)))
    assert res.grounded
    # europepmc was cited; both were retrieved
    assert res.source_stats["europepmc"]["cited"] == 1
    assert res.source_stats["europepmc"]["retrieved"] >= 1
    assert res.source_stats.get("faers", {}).get("cited", 0) == 0


def test_source_urls_are_canonical():
    from noesis_vertical_medical.links import source_url
    assert source_url("clinicaltrials:NCT00841061").startswith("https://clinicaltrials.gov/study/NCT00841061")
    assert "dailymed.nlm.nih.gov" in source_url("openfda:abc-123")
    assert source_url("europepmc:MED:29494065").startswith("https://europepmc.org/article/MED/29494065")
    assert source_url("cdc:2efk-s9c2") == "https://data.cdc.gov/d/2efk-s9c2"
    assert source_url("faers:10003336") is None            # no clean per-report page
    # quote → text-fragment deep link
    u = source_url("clinicaltrials:NCT1", quote="the primary endpoint was met")
    assert "#:~:text=" in u

    from noesis_vertical_medical.ui import MedicalUI
    assert MedicalUI().source_url("clinicaltrials:NCT1", "x").startswith("https://clinicaltrials.gov/")
