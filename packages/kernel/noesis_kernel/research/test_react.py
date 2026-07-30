"""Offline tests for the ReAct research loop, driven by a scripted LLM."""
from __future__ import annotations

import asyncio

from noesis_kernel.contract.dto import Locator
from noesis_kernel.providers.embeddings import FakeEmbedder
from noesis_kernel.providers.llm import LLMResult
from noesis_kernel.research.budget import BudgetState
from noesis_kernel.research.react import AgentStep, ClaimOut, run_react
from noesis_kernel.retrieval.memory import IndexedBlock, InMemoryRetrievalSource


class ScriptedLLM:
    """Returns pre-scripted AgentStep objects in order (ignores the prompt)."""
    def __init__(self, steps):
        self._steps = list(steps)

    async def complete(self, *, system, messages, response_format, max_tokens=2048, temperature=None):
        return LLMResult(parsed=self._steps.pop(0), output_tokens=5, model="scripted")


_BLOCK_TEXT = "The approved metric value was 9.8 percent for the term period."


def _source(tenant="A") -> InMemoryRetrievalSource:
    src = InMemoryRetrievalSource()
    src.add(IndexedBlock(
        block_id="b1", document_id="d1", tenant_id=tenant, text=_BLOCK_TEXT,
        locator=Locator("block_span", "d1", {"block_id": "b1"}),
    ))
    return src


def _run(llm, source, *, tenant="A", budget=None, max_steps=8):
    return asyncio.run(run_react(
        question="what was the metric value?",
        llm=llm, embedder=FakeEmbedder(dim=8), source=source,
        tenant_id=tenant, budget=budget or BudgetState(max_calls=10), max_steps=max_steps,
    ))


def test_happy_path_grounded_answer() -> None:
    llm = ScriptedLLM([
        AgentStep(action="search", query="term metric value"),
        AgentStep(action="answer", claims=[
            ClaimOut(text="the metric value was 9.8 percent", atom_id="a1",
                     quote="the approved metric value was 9.8 percent"),
        ]),
    ])
    res = _run(llm, _source())
    assert res.atoms_gathered == 1
    assert res.stopped_reason == "answered"
    assert res.grounded
    assert len(res.verified_claims) == 1 and not res.rejected_claims


def test_fabricated_quote_rejected() -> None:
    llm = ScriptedLLM([
        AgentStep(action="search", query="term metric value"),
        AgentStep(action="answer", claims=[
            ClaimOut(text="value was 12.3", atom_id="a1", quote="the value was 12.3 percent"),
        ]),
    ])
    res = _run(llm, _source())
    assert not res.grounded
    assert res.rejected_claims[0].reason == "quote_not_grounded"


def test_unknown_atom_rejected() -> None:
    llm = ScriptedLLM([
        AgentStep(action="search", query="term metric value"),
        AgentStep(action="answer", claims=[
            ClaimOut(text="x", atom_id="a99", quote="whatever"),
        ]),
    ])
    res = _run(llm, _source())
    assert res.rejected_claims[0].reason == "unknown_atom"


def test_budget_stops_the_loop() -> None:
    llm = ScriptedLLM([
        AgentStep(action="search", query="term"),
        AgentStep(action="search", query="term again"),   # never reached
    ])
    res = _run(llm, _source(), budget=BudgetState(max_calls=1))
    assert res.stopped_reason == "budget"
    assert res.steps == 1 and not res.verified_claims


def test_tenant_isolation_end_to_end() -> None:
    # Source has only tenant-A data; a tenant-B run retrieves nothing, so a claim
    # citing a1 is rejected as unknown (B can never reach A's evidence).
    llm = ScriptedLLM([
        AgentStep(action="search", query="term metric value"),
        AgentStep(action="answer", claims=[
            ClaimOut(text="stolen", atom_id="a1", quote="the approved metric value was 9.8 percent"),
        ]),
    ])
    res = _run(llm, _source(tenant="A"), tenant="B")
    assert res.atoms_gathered == 0
    assert res.rejected_claims[0].reason == "unknown_atom"
