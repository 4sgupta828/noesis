"""The plugin thesis on a SECOND, genuinely different domain: the medical manifest
passes conformance and drives the kernel ReAct loop to a grounded answer over real
ClinicalTrials.gov data — with ZERO kernel edits."""
from __future__ import annotations

import asyncio

from noesis_kernel.conformance.runner import run_conformance
from noesis_kernel.contract.dto import RetrievalRequest
from noesis_kernel.providers.embeddings import FakeEmbedder
from noesis_kernel.providers.llm import LLMResult
from noesis_kernel.research.budget import BudgetState
from noesis_kernel.research.react import AgentStep, ClaimOut, run_react

import noesis_vertical_medical as med
from noesis_vertical_medical import trial_doc
from noesis_vertical_medical.connector import ClinicalTrialsConnector
from noesis_vertical_medical.fixtures import sample_studies
from noesis_vertical_medical.source import MedicalRetrievalSource


class _LLM:
    def __init__(self, steps): self._s = list(steps)
    async def complete(self, *, system, messages, response_format, max_tokens=2048, temperature=None):
        return LLMResult(parsed=self._s.pop(0), output_tokens=5)


def test_manifest_conformant_through_p4() -> None:
    assert run_conformance(med.manifest, phase="P4").ok, run_conformance(med.manifest, phase="P4").summary()


def test_entry_point_manifest() -> None:
    assert med.manifest.name == "medical"
    assert "clinicaltrials" in med.manifest.retrieval_sources


def test_trial_doc_assembly_and_facets() -> None:
    s = sample_studies()[0]
    md = trial_doc.to_markdown(s)
    assert "Iron Deficiency" in md and md.startswith("#")
    f = trial_doc.facets(s)
    assert f["condition"] == "iron deficiency"
    assert f["study_type"] == "interventional"
    assert f["status"] == "completed"


def test_connector_discovers_from_fixture() -> None:
    conn = ClinicalTrialsConnector(studies=sample_studies())
    ents = asyncio.run(conn.discover_entities({}))
    assert ents and ents[0].native_id.startswith("NCT")
    docs = asyncio.run(conn.list_documents(ents[0]))
    body = asyncio.run(conn.fetch_artifact(docs[0]))
    assert b"Conditions" in body


def test_search_narrows_by_condition() -> None:
    emb = FakeEmbedder(dim=16)
    src = MedicalRetrievalSource(tenant_id="demo", embedder=emb)
    hits = asyncio.run(src.search(RetrievalRequest(query="iron deficiency infants",
                                                   tenant_id="demo")))
    assert hits and hits[0].facets.get("condition") == "iron deficiency"


def test_medical_run_react_grounded_answer() -> None:
    emb = FakeEmbedder(dim=16)
    src = MedicalRetrievalSource(tenant_id="demo", embedder=emb)
    llm = _LLM([
        AgentStep(action="search", query="iron deficiency condition"),
        AgentStep(action="answer", claims=[
            ClaimOut(text="the trial studies iron deficiency", atom_id="a1",
                     quote="Iron Deficiency")]),
    ])
    res = asyncio.run(run_react(
        question="what condition does the trial study?", llm=llm, embedder=emb, source=src,
        tenant_id="demo", budget=BudgetState(max_calls=10),
        gating=med.manifest.gating_policy, system_prompt=med.manifest.persona.system_prompt()))
    assert res.grounded and res.verified_claims[0].quote == "Iron Deficiency"


def test_authority_evidence_hierarchy() -> None:
    a = med.manifest.authority_policy
    assert a.outranks("systematic_review", "rct")
    assert a.outranks("rct", "cohort")
    assert a.outranks("cohort", "case_report")
    assert a.is_controlling("guideline") and not a.is_controlling("rct")
