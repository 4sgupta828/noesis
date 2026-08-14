"""Offline API test — /research returns a grounded, cited answer.

Injects a ResearchService wired with consistent fake providers (scripted LLM +
FakeEmbedder + the kernel's domain-neutral in-memory source), so the full
HTTP → agent → citations path is exercised without credits or a vertical package.
"""
from __future__ import annotations

from fastapi.testclient import TestClient

from noesis_kernel.contract.dto import Locator
from noesis_kernel.providers.embeddings import FakeEmbedder
from noesis_kernel.providers.llm import LLMResult
from noesis_kernel.research.react import AgentStep, ClaimOut
from noesis_kernel.retrieval.memory import IndexedBlock, InMemoryRetrievalSource
from noesis_kernel.runtime.research import ResearchService

from api.app import create_app


class _LLM:
    def __init__(self, steps): self._s = list(steps)
    async def complete(self, *, system, messages, response_format, max_tokens=2048, temperature=None):
        return LLMResult(parsed=self._s.pop(0), output_tokens=5)


def _source() -> InMemoryRetrievalSource:
    src = InMemoryRetrievalSource()
    src.add(IndexedBlock(
        block_id="b1", document_id="d1", tenant_id="acme",
        text="Metformin is recommended as first-line therapy for type 2 diabetes.",
        locator=Locator("block_span", "d1", {"block_id": "b1"}), source_key="corpus"))
    return src


def _service() -> ResearchService:
    emb = FakeEmbedder(dim=16)
    llm = _LLM([
        AgentStep(action="search", query="first-line therapy type 2 diabetes"),
        AgentStep(action="answer", claims=[
            ClaimOut(text="metformin is first-line for type 2 diabetes", atom_id="a1",
                     quote="first-line therapy for type 2 diabetes")]),
    ])
    return ResearchService(llm=llm, embedder=emb, sources={"corpus": _source()})


def test_health() -> None:
    client = TestClient(create_app(_service()))
    assert client.get("/health").json() == {"status": "ok"}


def test_research_returns_grounded_answer() -> None:
    client = TestClient(create_app(_service()))
    resp = client.post("/research", json={
        "question": "what is first-line therapy for type 2 diabetes?",
        "tenant_id": "acme", "sources": ["corpus"]})
    assert resp.status_code == 200
    data = resp.json()
    assert data["grounded"] is True
    assert data["rejected"] == 0
    assert len(data["claims"]) == 1
    assert data["claims"][0]["quote"] == "first-line therapy for type 2 diabetes"


def test_tenant_isolation_via_api() -> None:
    # A different tenant sees no evidence → not grounded (no leak).
    client = TestClient(create_app(_service()))
    resp = client.post("/research", json={
        "question": "what is first-line therapy for type 2 diabetes?",
        "tenant_id": "intruder", "sources": ["corpus"]})
    assert resp.status_code == 200
    assert resp.json()["grounded"] is False


def test_evidence_identity_flag_reads_env(monkeypatch) -> None:
    # Evidence Contract stage 1: the flag is wired from NOESIS_EVIDENCE_IDENTITY (default OFF).
    from api.app import evidence_identity_enabled
    monkeypatch.delenv("NOESIS_EVIDENCE_IDENTITY", raising=False)
    assert evidence_identity_enabled() is False
    monkeypatch.setenv("NOESIS_EVIDENCE_IDENTITY", "1")
    assert evidence_identity_enabled() is True
    monkeypatch.setenv("NOESIS_EVIDENCE_IDENTITY", "false")
    assert evidence_identity_enabled() is False


def test_claim_congruence_flag_reads_env(monkeypatch) -> None:
    # Evidence Contract stage 2: the flag is wired from NOESIS_CLAIM_CONGRUENCE (default OFF).
    from api.app import claim_congruence_enabled
    monkeypatch.delenv("NOESIS_CLAIM_CONGRUENCE", raising=False)
    assert claim_congruence_enabled() is False
    monkeypatch.setenv("NOESIS_CLAIM_CONGRUENCE", "1")
    assert claim_congruence_enabled() is True
    monkeypatch.setenv("NOESIS_CLAIM_CONGRUENCE", "false")
    assert claim_congruence_enabled() is False


def test_question_contract_mode_reads_env(monkeypatch) -> None:
    # Evidence Contract stage 3: NOESIS_QUESTION_CONTRACT is a MODE string (mirrors
    # NOESIS_GRAPH_EXPAND): "" off (default), "shadow", "steer"; anything else → off.
    from api.app import question_contract_mode
    monkeypatch.delenv("NOESIS_QUESTION_CONTRACT", raising=False)
    assert question_contract_mode() == ""
    monkeypatch.setenv("NOESIS_QUESTION_CONTRACT", "shadow")
    assert question_contract_mode() == "shadow"
    monkeypatch.setenv("NOESIS_QUESTION_CONTRACT", "STEER")
    assert question_contract_mode() == "steer"
    monkeypatch.setenv("NOESIS_QUESTION_CONTRACT", "1")     # bare truthy is NOT a mode
    assert question_contract_mode() == ""


def test_answer_mode_routing_flag_reads_env(monkeypatch) -> None:
    # Evidence Contract stage 4: the flag is wired from NOESIS_ANSWER_MODE_ROUTING (default OFF).
    from api.app import answer_mode_routing_enabled
    monkeypatch.delenv("NOESIS_ANSWER_MODE_ROUTING", raising=False)
    assert answer_mode_routing_enabled() is False
    monkeypatch.setenv("NOESIS_ANSWER_MODE_ROUTING", "1")
    assert answer_mode_routing_enabled() is True
    monkeypatch.setenv("NOESIS_ANSWER_MODE_ROUTING", "no")
    assert answer_mode_routing_enabled() is False
