"""Differential-first clinical-decision routing in the reasoned engine (ask_reasoned).

When a management question is DIAGNOSTIC (scaffold is_diagnostic=True) AND differential_answer_format is
wired, compose uses the DIFFERENTIAL format; otherwise (non-diagnostic, or format not wired = flag OFF)
it uses the reasoned format — byte-identical off path."""
from __future__ import annotations

import asyncio

from noesis_kernel.contract.dto import Locator
from noesis_kernel.providers.embeddings import FakeEmbedder
from noesis_kernel.providers.llm import LLMResult
from noesis_kernel.research.react import AgentStep, ClaimOut, ComposedAnswer
from noesis_kernel.retrieval.memory import IndexedBlock, InMemoryRetrievalSource
from noesis_kernel.runtime.research import ResearchService

_TEXT = "Acute coronary syndrome presents with central chest pressure and requires an ECG and troponin."
_SCAFFOLD_PROMPT = "SCAFFOLD"
_REASONED_FMT = "REASONED-DECISION-FORMAT-SENTINEL"
_DIFFERENTIAL_FMT = "DIFFERENTIAL-FIRST-FORMAT-SENTINEL"


class _LLM:
    """Scripted LLM: returns a _Scaffold with the given is_diagnostic, then runs search→answer→compose,
    capturing the full compose prompt (system+user) so the test can see which answer-format reached it."""

    def __init__(self, is_diagnostic: bool):
        self.is_diagnostic = is_diagnostic
        self.compose_blob = ""
        self._loop = [
            AgentStep(action="search", query="chest pain"),
            AgentStep(action="answer", claims=[
                ClaimOut(text="ACS needs an ECG and troponin", atom_id="a1",
                         quote="requires an ECG and troponin")]),
        ]

    async def complete(self, *, system, messages, response_format, max_tokens=2048, temperature=None):
        name = getattr(response_format, "__name__", "")
        if name == "_Scaffold":
            return LLMResult(parsed=response_format(
                kind="management", is_diagnostic=self.is_diagnostic,
                likely_causes=["ACS"], cant_miss=["aortic dissection"],
                key_decisions=["reperfusion?"], explicit_asks=["differential?"]), model="c")
        if response_format is ComposedAnswer:
            self.compose_blob = (system or "") + "\n" + (messages[-1]["content"] if messages else "")
            return LLMResult(parsed=ComposedAnswer(answer="ACS is most likely [1].",
                                                   directly_addresses=True), model="c")
        return LLMResult(parsed=self._loop.pop(0), output_tokens=5, model="c")


def _service(is_diagnostic: bool, differential_format: str | None):
    src = InMemoryRetrievalSource()
    src.add(IndexedBlock(block_id="b1", document_id="d1", tenant_id="A", text=_TEXT,
                         locator=Locator("block_span", "d1", {"block_id": "b1"})))
    llm = _LLM(is_diagnostic)
    svc = ResearchService(
        llm=llm, embedder=FakeEmbedder(dim=8), sources={"corpus": src},
        reasoned_scaffold_prompt=_SCAFFOLD_PROMPT, reasoned_answer_format=_REASONED_FMT,
        differential_answer_format=differential_format)
    return svc, llm


def test_diagnostic_question_uses_differential_format_when_wired():
    svc, llm = _service(is_diagnostic=True, differential_format=_DIFFERENTIAL_FMT)
    asyncio.run(svc.ask_reasoned(question="Chest pain — differential and workup?", tenant_id="A"))
    assert _DIFFERENTIAL_FMT in llm.compose_blob
    assert _REASONED_FMT not in llm.compose_blob


def test_nondiagnostic_management_uses_reasoned_format():
    svc, llm = _service(is_diagnostic=False, differential_format=_DIFFERENTIAL_FMT)
    asyncio.run(svc.ask_reasoned(question="How do I titrate this drug?", tenant_id="A"))
    assert _REASONED_FMT in llm.compose_blob
    assert _DIFFERENTIAL_FMT not in llm.compose_blob


def test_medical_scaffold_prompt_instructs_is_diagnostic():
    # Guard the real-LLM behavior gap the scripted tests can't catch: the REAL scaffold prompt must
    # actually TELL the model to classify is_diagnostic (else it defaults false and the differential
    # format never fires — the bug the held-out eval caught 2026-08-17).
    from noesis_vertical_medical.reasoned import REASONED_SCAFFOLD_PROMPT
    assert "is_diagnostic" in REASONED_SCAFFOLD_PROMPT
    assert "differential" in REASONED_SCAFFOLD_PROMPT.lower()


def test_flag_off_diagnostic_still_uses_reasoned_format():
    # differential_answer_format=None models the flag OFF (app wires None) → byte-identical reasoned path
    svc, llm = _service(is_diagnostic=True, differential_format=None)
    asyncio.run(svc.ask_reasoned(question="Chest pain — differential and workup?", tenant_id="A"))
    assert _REASONED_FMT in llm.compose_blob
    assert _DIFFERENTIAL_FMT not in llm.compose_blob
