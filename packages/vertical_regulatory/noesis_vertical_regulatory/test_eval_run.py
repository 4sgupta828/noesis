"""Run the regulatory held-out gold through the agent + score it (offline).

Proves the eval gate works end to end: the agent's answers are scored by the
generic qa scorer against the vertical's gold. Uses scripted LLMs (the real
baseline is a `record` run — the budgeted-credit step).
"""
from __future__ import annotations

import asyncio

from noesis_kernel.eval.runner import run_qa_eval, summarize
from noesis_kernel.providers.embeddings import FakeEmbedder
from noesis_kernel.providers.llm import LLMResult
from noesis_kernel.research.react import AgentStep, ClaimOut
from noesis_kernel.runtime.research import ResearchService

import noesis_vertical_regulatory as reg
from noesis_vertical_regulatory.eval_gold import GOLD
from noesis_vertical_regulatory.source import RegulatoryRetrievalSource

_QUOTE = GOLD["grounded_value"]["supporting_quote"]


class _LLM:
    def __init__(self, steps): self._s = list(steps)
    async def complete(self, *, system, messages, response_format, max_tokens=2048, temperature=None):
        return LLMResult(parsed=self._s.pop(0), output_tokens=5)


def _service(llm) -> ResearchService:
    emb = FakeEmbedder(dim=16)
    return ResearchService(
        llm=llm, embedder=emb,
        sources={"regulatory": RegulatoryRetrievalSource(tenant_id="acme", embedder=emb)},
        gating=reg.manifest.gating_policy,
        persona_prompt=reg.manifest.persona.system_prompt())


def test_regulatory_gold_passes() -> None:
    # case 1 (value): search that ranks the Order block first, then a grounded answer
    # case 2 (refuse): a jurisdiction the corpus lacks → honest refusal
    llm = _LLM([
        AgentStep(action="search", query="commission return on equity"),
        AgentStep(action="answer", claims=[
            ClaimOut(text="the Commission approved 9.6 percent", atom_id="a1", quote=_QUOTE)]),
        AgentStep(action="search", query="return on equity in CA"),
        AgentStep(action="answer", claims=[]),        # honest refusal for CA
    ])
    scores = asyncio.run(run_qa_eval(_service(llm).ask, GOLD, tenant_id="acme",
                                     source_keys=["regulatory"]))
    s = summarize(scores)
    assert s["passed"] == s["total"], s
    assert scores["grounded_value"].fully_correct
    assert scores["coverage_gap_out_of_state"].fully_correct   # refused correctly


def test_hallucination_fails_the_eval() -> None:
    # The agent fabricates a value → span-check rejects it → answer not grounded →
    # the value case fails. The eval catches the regression.
    llm = _LLM([
        AgentStep(action="search", query="commission return on equity"),
        AgentStep(action="answer", claims=[
            ClaimOut(text="approved 12.5 percent", atom_id="a1",
                     quote="the commission approves a return on equity of 12.5 percent")]),
    ])
    scores = asyncio.run(run_qa_eval(
        _service(llm).ask, {"grounded_value": GOLD["grounded_value"]},
        tenant_id="acme", source_keys=["regulatory"]))
    assert not scores["grounded_value"].fully_correct
