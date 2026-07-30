"""Offline API test — /research returns a grounded, cited answer.

Injects a ResearchService wired with consistent fake providers (scripted LLM +
FakeEmbedder + the regulatory source), so the full HTTP → agent → citations path
is exercised without credits.
"""
from __future__ import annotations

from fastapi.testclient import TestClient

from noesis_kernel.providers.embeddings import FakeEmbedder
from noesis_kernel.providers.llm import LLMResult
from noesis_kernel.research.react import AgentStep, ClaimOut
from noesis_kernel.runtime.research import ResearchService

import noesis_vertical_regulatory as reg
from noesis_vertical_regulatory.source import RegulatoryRetrievalSource

from api.app import create_app


class _LLM:
    def __init__(self, steps): self._s = list(steps)
    async def complete(self, *, system, messages, response_format, max_tokens=2048, temperature=None):
        return LLMResult(parsed=self._s.pop(0), output_tokens=5)


def _service() -> ResearchService:
    emb = FakeEmbedder(dim=16)
    llm = _LLM([
        AgentStep(action="search", query="approved return on equity"),
        # "return on equity" is present in any block the query retrieves → deterministic
        AgentStep(action="answer", claims=[
            ClaimOut(text="the case concerns return on equity", atom_id="a1",
                     quote="return on equity")]),
    ])
    return ResearchService(
        llm=llm, embedder=emb,
        sources={"regulatory": RegulatoryRetrievalSource(tenant_id="acme", embedder=emb)},
        gating=reg.manifest.gating_policy,
        persona_prompt=reg.manifest.persona.system_prompt(),
    )


def test_health() -> None:
    client = TestClient(create_app(_service()))
    assert client.get("/health").json() == {"status": "ok"}


def test_research_returns_grounded_answer() -> None:
    client = TestClient(create_app(_service()))
    resp = client.post("/research", json={
        "question": "what return on equity was approved?",
        "tenant_id": "acme", "sources": ["regulatory"]})
    assert resp.status_code == 200
    data = resp.json()
    assert data["grounded"] is True
    assert data["rejected"] == 0
    assert len(data["claims"]) == 1
    assert data["claims"][0]["quote"] == "return on equity"


def test_tenant_isolation_via_api() -> None:
    # A different tenant sees no evidence → not grounded (no leak).
    client = TestClient(create_app(_service()))
    resp = client.post("/research", json={
        "question": "what return on equity was approved?",
        "tenant_id": "intruder", "sources": ["regulatory"]})
    assert resp.status_code == 200
    assert resp.json()["grounded"] is False
