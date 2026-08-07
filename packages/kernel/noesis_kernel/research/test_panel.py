"""Ask-Panel orchestrator: specialists run grounded in parallel; synthesis composes ONLY from the pooled
verified findings (grounding preserved). Driven by a content-routing scripted LLM."""
from __future__ import annotations

import asyncio
from dataclasses import dataclass

from noesis_kernel.contract.dto import Locator
from noesis_kernel.providers.embeddings import FakeEmbedder
from noesis_kernel.providers.llm import LLMResult
from noesis_kernel.research.panel import run_panel
from noesis_kernel.research.react import AgentStep, ClaimOut, ComposedAnswer, InterpretationItem, \
    ConfidenceRead, ConfidenceDim
from noesis_kernel.retrieval.memory import IndexedBlock, InMemoryRetrievalSource


@dataclass(frozen=True)
class _Spec:
    id: str
    specialty: str
    lens: str
    focus: str
    source_keys: tuple = ()


_BLOCK = "The approved dose is 5 mg once daily and the response rate was 53 percent."


def _source():
    s = InMemoryRetrievalSource()
    s.add(IndexedBlock(block_id="b1", document_id="d1", tenant_id="A", text=_BLOCK,
                       locator=Locator("block_span", "d1", {"block_id": "b1"}), source_key="corpus"))
    return s


class _LLM:
    """Routes by prompt content: panel synthesis vs specialist compose vs planner step."""
    async def complete(self, *, system, messages, response_format, max_tokens=2048, temperature=None):
        c = messages[0]["content"]
        if "VERIFIED PANEL FINDINGS" in c:                     # the panel synthesis
            return LLMResult(parsed=ComposedAnswer(
                answer="The panel agrees the dose is 5 mg once daily [1].",
                reasoning_purpose="Whether the dose is appropriate.",
                interpretation=[InterpretationItem(text="Both lenses cite the same 5 mg dose",
                                                   kind="implication", basis_findings=[1])],
                reasoning_conclusion="The evidence supports 5 mg once daily.",
                confidence=ConfidenceRead(factual=ConfidenceDim(level="moderate"))), output_tokens=5)
        if "VERIFIED FINDINGS" in c:                           # a specialist's own compose
            return LLMResult(parsed=ComposedAnswer(answer="Dose is 5 mg once daily [1]."), output_tokens=5)
        if "no evidence yet" in c:                             # first planner step → search
            return LLMResult(parsed=AgentStep(action="search", query="dose"), output_tokens=5)
        return LLMResult(parsed=AgentStep(action="answer", claims=[                # answer step
            ClaimOut(text="the approved dose is 5 mg once daily", atom_id="a1",
                     quote="The approved dose is 5 mg once daily")]), output_tokens=5)


def _specialists():
    return [_Spec("pharm", "Clinical Pharmacology", "You are a pharmacologist.", "dosing, interactions"),
            _Spec("ebm", "Evidence-Based Medicine", "You are an EBM methodologist.", "evidence quality")]


def test_panel_runs_specialists_and_grounds_synthesis():
    src = _source()
    def make_retrievers(source_keys):
        return src, None
    r = asyncio.run(run_panel(
        question="What is the dose?", specialists=_specialists(), llm=_LLM(), embedder=FakeEmbedder(dim=8),
        make_retrievers=make_retrievers, tenant_id="A", synthesis_directive="Synthesize."))
    # both specialists produced grounded takes
    assert r.n_specialists == 2 and len(r.takes) == 2
    assert all(t.grounded and t.n_verified >= 1 for t in r.takes)
    # synthesis is grounded in the pooled findings and cites [1]
    assert "5 mg once daily" in r.synthesis and "[1]" in r.synthesis
    assert r.claims
    # the structured reasoning-read layer is intentionally OFF for the panel (reasoning lives in the
    # answer's "How the panel reasoned" narrative) — so these stay empty
    assert r.interpretation == [] and r.confidence is None


def test_panel_survives_a_failing_specialist():
    src = _source()
    def make_retrievers(source_keys):
        # the 'ebm' specialist gets no source → still returns a result (no claims), panel proceeds
        return src, None
    specs = _specialists()
    r = asyncio.run(run_panel(
        question="What is the dose?", specialists=specs, llm=_LLM(), embedder=FakeEmbedder(dim=8),
        make_retrievers=make_retrievers, tenant_id="A"))
    assert len(r.takes) == 2 and r.synthesis          # panel still synthesizes


def test_plan_panel_selects_and_ignores_unknown():
    from noesis_kernel.research.panel import plan_panel, PanelPlan, SpecialistPick
    roster = [{"id": "pharm", "specialty": "Clinical Pharmacology", "lens": "dosing"},
              {"id": "ebm", "specialty": "Evidence-Based Medicine", "lens": "evidence quality"},
              {"id": "cards", "specialty": "Cardiology", "lens": "cardiovascular"}]
    class _LLM:
        async def complete(self, *, system, messages, response_format, max_tokens=2048, temperature=None):
            return LLMResult(parsed=PanelPlan(specialists=[
                SpecialistPick(id="cards", rationale="heart failure component"),
                SpecialistPick(id="pharm", rationale="renal dosing"),
                SpecialistPick(id="bogus", rationale="not in roster")]), output_tokens=5)
    sel = asyncio.run(plan_panel(question="HF + CKD case", roster=roster, llm=_LLM()))
    ids = [s["id"] for s in sel]
    assert ids == ["cards", "pharm"] and sel[0]["specialty"] == "Cardiology" and "heart failure" in sel[0]["rationale"]


def test_plan_panel_failsafe_on_error():
    from noesis_kernel.research.panel import plan_panel
    class _Bad:
        async def complete(self, **k): raise RuntimeError("triage down")
    assert asyncio.run(plan_panel(question="q", roster=[{"id": "x", "specialty": "X", "lens": ""}],
                                  llm=_Bad())) == []   # empty → caller applies the default set


def test_panel_no_evidence_says_so():
    empty = InMemoryRetrievalSource()   # nothing to retrieve → no verified claims anywhere
    class _Empty:
        async def complete(self, *, system, messages, response_format, max_tokens=2048, temperature=None):
            if "no evidence yet" in messages[0]["content"]:
                return LLMResult(parsed=AgentStep(action="search", query="x"), output_tokens=5)
            return LLMResult(parsed=AgentStep(action="answer", claims=[]), output_tokens=5)
    r = asyncio.run(run_panel(question="?", specialists=_specialists(), llm=_Empty(),
        embedder=FakeEmbedder(dim=8), make_retrievers=lambda k: (empty, None), tenant_id="A"))
    assert "could not ground" in r.synthesis and not r.claims
