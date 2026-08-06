"""Answer-focus: elliptical follow-ups are condensed (so retrieval + compose inherit the subject) and
compose gets the answer-scope instruction. Off / no-history → byte-identical no-op."""
from __future__ import annotations

import asyncio

from noesis_kernel.contract.dto import Locator
from noesis_kernel.providers.embeddings import FakeEmbedder
from noesis_kernel.providers.llm import LLMResult
from noesis_kernel.research.react import AgentStep, ClaimOut, ComposedAnswer
from noesis_kernel.retrieval.memory import IndexedBlock, InMemoryRetrievalSource
from noesis_kernel.runtime.research import ResearchService

_TEXT = "The approved metric value was 9.8 percent for the term period."
SCOPE_MARK = "Directly ANSWER the specific question"   # only present under answer_focus


class FocusLLM:
    def __init__(self, condensed="RESOLVED SUBJECT QUESTION"):
        self.condensed = condensed
        self.compose_user = None
        self.search_query = None
        self._loop = [
            AgentStep(action="search", query="metric value"),
            AgentStep(action="answer", claims=[
                ClaimOut(text="metric was 9.8 percent", atom_id="a1",
                         quote="the approved metric value was 9.8 percent")]),
        ]

    async def complete(self, *, system, messages, response_format, max_tokens=2048, temperature=None):
        name = getattr(response_format, "__name__", "")
        if name == "_Condensed":                       # the condenser pre-step
            return LLMResult(parsed=response_format(question=self.condensed), model="c")
        if response_format is ComposedAnswer:
            self.compose_user = messages[-1]["content"]
            return LLMResult(parsed=ComposedAnswer(answer="Value is 9.8 percent [1].",
                                                   directly_addresses=True), model="c")
        return LLMResult(parsed=self._loop.pop(0), output_tokens=5, model="c")


def _service(condensed="RESOLVED SUBJECT QUESTION"):
    src = InMemoryRetrievalSource()
    src.add(IndexedBlock(block_id="b1", document_id="d1", tenant_id="A", text=_TEXT,
                         locator=Locator("block_span", "d1", {"block_id": "b1"})))
    llm = FocusLLM(condensed)
    return ResearchService(llm=llm, embedder=FakeEmbedder(dim=8), sources={"corpus": src}), llm


HIST = [{"question": "What is first-line PCP prophylaxis?", "answer": "TMP-SMX is first-line."}]


def test_followup_condensed_and_reaches_compose():
    svc, llm = _service("What is the dose of TMP-SMX for PCP prophylaxis?")
    res = asyncio.run(svc.ask(question="What dose?", tenant_id="A", history=HIST, answer_focus=True))
    assert res.resolved_question == "What is the dose of TMP-SMX for PCP prophylaxis?"
    assert "What is the dose of TMP-SMX" in llm.compose_user        # compose sees the SUBJECT-bound question
    assert "What dose?" not in llm.compose_user


def test_answer_focus_adds_scoping_instruction():
    svc, llm = _service()
    asyncio.run(svc.ask(question="What dose?", tenant_id="A", history=HIST, answer_focus=True))
    assert SCOPE_MARK in llm.compose_user


def test_off_is_byte_identical_noop():
    svc, llm = _service("SHOULD NOT BE USED")
    res = asyncio.run(svc.ask(question="What dose?", tenant_id="A", history=HIST, answer_focus=False))
    assert res.resolved_question == ""                 # no condensation
    assert SCOPE_MARK not in llm.compose_user           # original compose instruction
    assert "What dose?" in llm.compose_user             # raw question used


def test_no_history_skips_condense():
    svc, llm = _service("SHOULD NOT BE USED")
    res = asyncio.run(svc.ask(question="What dose?", tenant_id="A", answer_focus=True))  # no history
    assert res.resolved_question == ""
    assert "What dose?" in llm.compose_user
    assert SCOPE_MARK in llm.compose_user               # compose-scope still applies single-turn


def test_verbatim_rewrite_is_not_flagged_as_resolved():
    svc, llm = _service("What dose?")                  # condenser returns it unchanged (self-contained)
    res = asyncio.run(svc.ask(question="What dose?", tenant_id="A", history=HIST, answer_focus=True))
    assert res.resolved_question == ""                 # unchanged → not surfaced as a rewrite
    assert "What dose?" in llm.compose_user
