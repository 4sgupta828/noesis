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
            if "VERIFIED FINDINGS" in messages[0]["content"]:      # compose step honors its contract
                from noesis_kernel.research.react import ComposedAnswer
                return LLMResult(parsed=ComposedAnswer(answer="Metric value is 9.8 percent [1]."), output_tokens=5)
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


def test_extract_retry_recovers_empty_answer() -> None:
    # Rule 4 held-out case: the agent abstains (empty-claims answer) on its first
    # answer DESPITE having gathered relevant evidence; the recovery re-ask
    # (mode="extract") must extract the grounded claim rather than return nothing.
    src = _source()
    class _SearchEmptyThenExtract:
        async def complete(self, *, system, messages, response_format, max_tokens=2048, temperature=None):
            content = messages[0]["content"]
            if "VERIFIED FINDINGS" in content:                    # compose step
                from noesis_kernel.research.react import ComposedAnswer
                return LLMResult(parsed=ComposedAnswer(answer="Metric was 9.8 percent [1]."), output_tokens=5)
            if "empty answer is INVALID" in content:              # the extract retry
                return LLMResult(parsed=AgentStep(action="answer", claims=[
                    ClaimOut(text="the metric value was 9.8 percent", atom_id="a1",
                             quote="the approved metric value was 9.8 percent")]), output_tokens=5)
            if "no evidence yet" in content:                      # first step: gather
                return LLMResult(parsed=AgentStep(action="search", query="term metric value"), output_tokens=5)
            return LLMResult(parsed=AgentStep(action="answer", claims=[]), output_tokens=5)  # abstain
    res = asyncio.run(run_react(
        question="what was the metric value?", llm=_SearchEmptyThenExtract(),
        embedder=FakeEmbedder(dim=8), source=src, tenant_id="A",
        budget=BudgetState(max_calls=20)))
    assert res.retried_empty                                      # the recovery fired
    assert res.grounded and len(res.verified_claims) == 1         # and it recovered a claim


def test_no_retry_when_evidence_truly_absent() -> None:
    # The recovery must NOT fire (or loop) when the agent honestly refuses with no
    # evidence gathered — otherwise a genuine no-answer would burn extra calls.
    src = _source()
    class _AnswerEmptyNoSearch:
        async def complete(self, *, system, messages, response_format, max_tokens=2048, temperature=None):
            return LLMResult(parsed=AgentStep(action="answer", claims=[]), output_tokens=5)
    res = asyncio.run(run_react(
        question="?", llm=_AnswerEmptyNoSearch(), embedder=FakeEmbedder(dim=8),
        source=src, tenant_id="A", budget=BudgetState(max_calls=20)))
    assert not res.retried_empty and not res.grounded            # no atoms → no retry


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


def _compose_setup():
    """A source + a fake whose loop grounds ONE claim; compose behavior is injected per-test."""
    src = _source()
    def make(compose_fn):
        class _LLM:
            def __init__(self): self.compose_calls = 0
            async def complete(self, *, system, messages, response_format, max_tokens=2048, temperature=None):
                if "VERIFIED FINDINGS" in messages[0]["content"]:     # compose step
                    self.compose_calls += 1
                    return compose_fn(self.compose_calls)
                if "no evidence yet" in messages[0]["content"]:
                    return LLMResult(parsed=AgentStep(action="search", query="term metric value"), output_tokens=5)
                return LLMResult(parsed=AgentStep(action="answer", claims=[
                    ClaimOut(text="the metric value was 9.8 percent", atom_id="a1",
                             quote="the approved metric value was 9.8 percent")]), output_tokens=5)
        return _LLM()
    return src, make


def test_compose_retries_transient_failure(monkeypatch):
    # REGRESSION (the 'grounded, N claims, empty answer' bug): a transient error on the compose call
    # must NOT drop the answer — it retries and recovers.
    import noesis_kernel.research.react as react
    monkeypatch.setattr(react, "_COMPOSE_BACKOFF_S", 0)     # no real sleeping in the test
    from noesis_kernel.research.react import ComposedAnswer
    src, make = _compose_setup()
    def compose_fn(call_n):
        if call_n == 1:
            raise RuntimeError("transient overload")          # first attempt fails…
        return LLMResult(parsed=ComposedAnswer(answer="Metric value is 9.8 percent [1]."), output_tokens=5)
    llm = make(compose_fn)
    res = asyncio.run(run_react(question="what was the metric value?", llm=llm,
        embedder=FakeEmbedder(dim=8), source=src, tenant_id="A", budget=BudgetState(max_calls=20)))
    assert res.grounded and len(res.verified_claims) == 1
    assert res.composed_answer == "Metric value is 9.8 percent [1]."   # recovered on retry
    assert res.compose_failed is False
    assert llm.compose_calls == 2                              # exactly one retry


def test_compose_failure_surfaces_note(monkeypatch):
    # If compose can NEVER complete, the failure is SURFACED (a note), not a silent blank — and the
    # verified evidence still stands (grounded, claims intact).
    import noesis_kernel.research.react as react
    monkeypatch.setattr(react, "_COMPOSE_BACKOFF_S", 0)
    src, make = _compose_setup()
    def compose_fn(call_n):
        raise RuntimeError("persistent outage")
    llm = make(compose_fn)
    res = asyncio.run(run_react(question="what was the metric value?", llm=llm,
        embedder=FakeEmbedder(dim=8), source=src, tenant_id="A", budget=BudgetState(max_calls=20)))
    assert res.grounded and len(res.verified_claims) == 1     # evidence survives the compose failure
    assert res.compose_failed is True
    assert res.composed_answer and res.composed_answer == react._COMPOSE_FAIL_NOTE   # not empty
    assert llm.compose_calls == react._COMPOSE_ATTEMPTS       # exhausted the retries


def test_rank_claims_by_relevance_keeps_the_most_relevant():
    # Evidence selection (#2): under the flag, compose gets the claims most RELEVANT to the question,
    # not the first-come ones. Deterministic FakeEmbedder encodes relevance in a 2-d vector.
    from noesis_kernel.research.react import _rank_claims_by_relevance, VerifiedClaim
    class _FE:
        def dim(self): return 2
        def embed(self, texts): return [[1.0, 0.0] if "relevant" in t else [0.0, 1.0] for t in texts]
    claims = [VerifiedClaim("off-topic A", "a1", "q"), VerifiedClaim("relevant B", "a2", "q"),
              VerifiedClaim("off-topic C", "a3", "q"), VerifiedClaim("relevant D", "a4", "q")]
    top2 = asyncio.run(_rank_claims_by_relevance("the relevant question", claims, _FE(), 2))
    assert [c.text for c in top2] == ["relevant B", "relevant D"]   # relevant win; stable among ties
    # already within cap → returned unchanged (no reorder)
    assert asyncio.run(_rank_claims_by_relevance("x", claims[:2], _FE(), 5)) == claims[:2]


def test_reasoning_read_flows_through_when_enabled(monkeypatch):
    # End-to-end: with reasoning_read=True, a compose that emits a GROUNDED interpretation item +
    # confidence surfaces both on the result (validated). The basis finding [1] is "9.8 percent".
    import noesis_kernel.research.react as react
    monkeypatch.setattr(react, "_COMPOSE_BACKOFF_S", 0)
    from noesis_kernel.research.react import (
        ComposedAnswer, InterpretationItem, ConfidenceRead, ConfidenceDim)
    src, make = _compose_setup()
    def compose_fn(call_n):
        return LLMResult(parsed=ComposedAnswer(
            answer="The approved metric value was 9.8 percent [1].",
            reasoning_purpose="Whether the metric value is reliable enough to act on.",
            interpretation=[
                InterpretationItem(text="Only one source reports this, limiting confidence",
                                   kind="gap", basis_findings=[1]),
                InterpretationItem(text="A value near 12 percent is possible",   # 12 not in finding → dropped
                                   kind="implication", basis_findings=[1])],
            reasoning_conclusion="The 9.8 percent figure is the only supported value, so it can be used cautiously.",
            confidence=ConfidenceRead(
                factual=ConfidenceDim(level="low", rationale="single source"),
                causal=ConfidenceDim(level="unknown", rationale=""),
                generalization=ConfidenceDim(level="low", rationale="one term period"))),
            output_tokens=5)
    llm = make(compose_fn)
    res = asyncio.run(run_react(question="what was the metric value?", llm=llm,
        embedder=FakeEmbedder(dim=8), source=src, tenant_id="A",
        budget=BudgetState(max_calls=20), reasoning_read=True))
    assert res.grounded
    # the fabricated-number item is dropped; the grounded gap item survives
    assert len(res.interpretation) == 1 and res.interpretation[0]["kind"] == "gap"
    assert res.confidence and res.confidence["factual"]["level"] == "low"
    # purpose (no numbers) passes; conclusion reuses only the grounded 9.8 → both survive
    assert res.reasoning_purpose.startswith("Whether the metric value")
    assert "9.8 percent" in res.reasoning_conclusion


def test_reasoning_conclusion_with_fabricated_number_is_dropped(monkeypatch):
    # The purpose/conclusion frame is grounded too: a conclusion inventing a figure not in ANY finding
    # is dropped (fail-safe), while a clean purpose survives.
    import noesis_kernel.research.react as react
    monkeypatch.setattr(react, "_COMPOSE_BACKOFF_S", 0)
    from noesis_kernel.research.react import ComposedAnswer
    src, make = _compose_setup()
    def compose_fn(call_n):
        return LLMResult(parsed=ComposedAnswer(
            answer="The approved metric value was 9.8 percent [1].",
            reasoning_purpose="Whether the value can be trusted.",
            reasoning_conclusion="The true value is likely closer to 15 percent."),  # 15 in no finding
            output_tokens=5)
    llm = make(compose_fn)
    res = asyncio.run(run_react(question="what was the metric value?", llm=llm,
        embedder=FakeEmbedder(dim=8), source=src, tenant_id="A",
        budget=BudgetState(max_calls=20), reasoning_read=True))
    assert res.reasoning_purpose == "Whether the value can be trusted."   # clean → survives
    assert res.reasoning_conclusion == ""                                 # fabricated figure → dropped


def test_reasoning_read_off_is_noop(monkeypatch):
    # OFF path (default): even if the model volunteers interpretation/confidence, the result surfaces
    # NEITHER — byte-identical to the pre-flag answer (Rule 20).
    import noesis_kernel.research.react as react
    monkeypatch.setattr(react, "_COMPOSE_BACKOFF_S", 0)
    from noesis_kernel.research.react import (
        ComposedAnswer, InterpretationItem, ConfidenceRead, ConfidenceDim)
    src, make = _compose_setup()
    def compose_fn(call_n):
        return LLMResult(parsed=ComposedAnswer(
            answer="The approved metric value was 9.8 percent [1].",
            reasoning_purpose="a purpose", reasoning_conclusion="a conclusion",
            interpretation=[InterpretationItem(text="grounded gap", kind="gap", basis_findings=[1])],
            confidence=ConfidenceRead(factual=ConfidenceDim(level="high"))), output_tokens=5)
    llm = make(compose_fn)
    res = asyncio.run(run_react(question="what was the metric value?", llm=llm,
        embedder=FakeEmbedder(dim=8), source=src, tenant_id="A",
        budget=BudgetState(max_calls=20)))              # reasoning_read defaults False
    assert res.grounded
    assert res.interpretation == [] and res.confidence is None
    assert res.reasoning_purpose == "" and res.reasoning_conclusion == ""


def test_rank_claims_fail_safe_on_embed_error():
    # Any embedding failure must degrade to today's behavior (first `top`), never crash the answer.
    from noesis_kernel.research.react import _rank_claims_by_relevance, VerifiedClaim
    class _Bad:
        def dim(self): return 2
        def embed(self, texts): raise RuntimeError("embed down")
    claims = [VerifiedClaim(f"c{i}", f"a{i}", "q") for i in range(5)]
    got = asyncio.run(_rank_claims_by_relevance("x", claims, _Bad(), 2))
    assert got == claims[:2]
