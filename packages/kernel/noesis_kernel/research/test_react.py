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


def test_loop_reformulation_broadens_recall() -> None:
    # The agent issues a reformulation; multi-query fusion pulls in a block the
    # original query alone would miss.
    src = InMemoryRetrievalSource()
    src.add(IndexedBlock(block_id="b1", document_id="d", tenant_id="A",
                         text="alpha discussion of the first topic here",
                         locator=Locator("block_span", "d", {"block_id": "b1"})))
    src.add(IndexedBlock(block_id="b2", document_id="d", tenant_id="A",
                         text="beta discussion of the second topic here",
                         locator=Locator("block_span", "d", {"block_id": "b2"})))
    llm = ScriptedLLM([
        AgentStep(action="search", query="alpha", queries=["beta"]),
        AgentStep(action="answer", claims=[
            ClaimOut(text="c1", atom_id="a1", quote="alpha discussion of the first topic"),
            ClaimOut(text="c2", atom_id="a2", quote="beta discussion of the second topic"),
        ]),
    ])
    res = _run(llm, src)
    assert res.atoms_gathered == 2          # both retrieved via reformulation
    assert res.grounded and len(res.verified_claims) == 2


class _GapGating:
    def gate_applies(self, q, plan): return True                # noqa: ANN001,E704
    def claim_in_scope(self, claim, hits): return bool(hits)     # noqa: ANN001,E704
    def coverage_gap(self, q, hits): return None if hits else "no evidence in corpus"  # noqa: ANN001,E704


def test_coverage_gap_signalled_when_corpus_empty() -> None:
    src = _source()                          # has tenant-A data only
    llm = ScriptedLLM([
        AgentStep(action="search", query="nonexistent zzz topic"),   # matches nothing
        AgentStep(action="answer", claims=[]),                       # honestly refuses
    ])
    res = asyncio.run(run_react(
        question="what about a missing topic?", llm=llm, embedder=FakeEmbedder(dim=8),
        source=src, tenant_id="A", budget=BudgetState(max_calls=10), gating=_GapGating()))
    assert res.coverage_gaps == ["no evidence in corpus"]
    assert not res.grounded                   # no claims → not grounded (honest)


def test_forced_answer_on_last_step() -> None:
    # An agent that always chooses "search" must still produce an answer on the
    # final step (forced), rather than silently returning nothing.
    src = _source()
    class _AlwaysSearch:
        def __init__(self): self.n = 0
        async def complete(self, *, system, messages, response_format, max_tokens=2048, temperature=None):
            self.n += 1
            # On the forced/last step the prompt says "MUST answer"; emit an answer then.
            if "MUST now" in messages[0]["content"]:
                return LLMResult(parsed=AgentStep(action="answer", claims=[
                    ClaimOut(text="v", atom_id="a1",
                             quote="the approved metric value was 9.8 percent")]), output_tokens=5)
            return LLMResult(parsed=AgentStep(action="search", query="term metric value"), output_tokens=5)
    res = asyncio.run(run_react(
        question="what was the metric value?", llm=_AlwaysSearch(), embedder=FakeEmbedder(dim=8),
        source=src, tenant_id="A", budget=BudgetState(max_calls=20), max_steps=3))
    assert res.stopped_reason == "answered"        # forced answer, not "max_steps"
    assert res.grounded and len(res.verified_claims) == 1


def test_forced_answer_can_honestly_refuse() -> None:
    # If forced to answer with no usable evidence, an empty-claims answer is fine
    # (honest refusal), still not a silent max_steps.
    src = _source()
    class _SearchThenEmpty:
        async def complete(self, *, system, messages, response_format, max_tokens=2048, temperature=None):
            if "MUST now" in messages[0]["content"]:
                return LLMResult(parsed=AgentStep(action="answer", claims=[]), output_tokens=5)
            return LLMResult(parsed=AgentStep(action="search", query="x"), output_tokens=5)
    res = asyncio.run(run_react(
        question="?", llm=_SearchThenEmpty(), embedder=FakeEmbedder(dim=8), source=src,
        tenant_id="A", budget=BudgetState(max_calls=20), max_steps=2))
    assert res.stopped_reason == "answered"
    assert not res.grounded and not res.verified_claims   # honest refusal


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


def test_composed_answer_grounded_in_findings():
    # After gathering verified findings, the agent composes a prose answer that
    # references them [n] — grounded by construction (composer sees only findings).
    src = _source()
    class _SearchAnswerCompose:
        def __init__(self): self.calls = 0
        async def complete(self, *, system, messages, response_format, max_tokens=2048, temperature=None):
            self.calls += 1
            content = messages[0]["content"]
            if "VERIFIED FINDINGS" in content:            # the compose step
                from noesis_kernel.research.react import ComposedAnswer
                return LLMResult(parsed=ComposedAnswer(
                    answer="The approved metric value was 9.8 percent [1]."), output_tokens=5)
            if "no evidence yet" in content or self.calls == 1:
                return LLMResult(parsed=AgentStep(action="search", query="term metric value"), output_tokens=5)
            return LLMResult(parsed=AgentStep(action="answer", claims=[
                ClaimOut(text="the metric value was 9.8 percent", atom_id="a1",
                         quote="the approved metric value was 9.8 percent")]), output_tokens=5)
    res = asyncio.run(run_react(
        question="what was the metric value?", llm=_SearchAnswerCompose(),
        embedder=FakeEmbedder(dim=8), source=src, tenant_id="A",
        budget=BudgetState(max_calls=20)))
    assert res.grounded and len(res.verified_claims) == 1
    assert res.composed_answer == "The approved metric value was 9.8 percent [1]."
    assert "[1]" in res.composed_answer                  # references the finding
