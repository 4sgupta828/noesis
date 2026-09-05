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


# ---- answer-format panel (2026-09-04): routing by question shape, non-directive defaults --------------
_OVERVIEW_FMT = "OVERVIEW-EXPLAINER-FORMAT-SENTINEL"
_COVERAGE_ADDENDUM = "QUESTION-COVERAGE-ADDENDUM-SENTINEL"


class _KindLLM(_LLM):
    """Scripted scaffold with an explicit kind / confidence / explicit_asks (or a raised error)."""

    def __init__(self, kind: str, confidence: str = "high", raise_scaffold: bool = False, asks=()):
        super().__init__(is_diagnostic=False)
        self.kind, self.confidence, self.raise_scaffold, self.asks = kind, confidence, raise_scaffold, list(asks)

    async def complete(self, *, system, messages, response_format, max_tokens=2048, temperature=None):
        if getattr(response_format, "__name__", "") == "_Scaffold":
            if self.raise_scaffold:
                raise RuntimeError("classifier down")
            return LLMResult(parsed=response_format(kind=self.kind, confidence=self.confidence,
                                                    explicit_asks=self.asks), model="c")
        return await super().complete(system=system, messages=messages, response_format=response_format,
                                      max_tokens=max_tokens, temperature=temperature)


def _kind_service(llm):
    src = InMemoryRetrievalSource()
    src.add(IndexedBlock(block_id="b1", document_id="d1", tenant_id="A", text=_TEXT,
                         locator=Locator("block_span", "d1", {"block_id": "b1"})))
    return ResearchService(
        llm=llm, embedder=FakeEmbedder(dim=8), sources={"corpus": src},
        reasoned_scaffold_prompt=_SCAFFOLD_PROMPT, reasoned_answer_format=_REASONED_FMT,
        differential_answer_format=_DIFFERENTIAL_FMT,
        answer_formats={"overview": _OVERVIEW_FMT},
        reasoned_coverage_addendum=_COVERAGE_ADDENDUM)


def test_overview_kind_uses_the_explainer_format_never_the_plan():
    llm = _KindLLM("overview")
    asyncio.run(_kind_service(llm).ask_reasoned(question="What is a balanced diet?", tenant_id="A"))
    assert _OVERVIEW_FMT in llm.compose_blob
    assert _REASONED_FMT not in llm.compose_blob and _DIFFERENTIAL_FMT not in llm.compose_blob


def test_family_without_a_wired_format_falls_to_standard():
    llm = _KindLLM("comparison")          # vertical wired only "overview" here
    asyncio.run(_kind_service(llm).ask_reasoned(question="A vs B?", tenant_id="A"))
    assert _REASONED_FMT not in llm.compose_blob and _OVERVIEW_FMT not in llm.compose_blob


def test_low_confidence_management_falls_to_standard_not_the_plan():
    llm = _KindLLM("management", confidence="low")
    asyncio.run(_kind_service(llm).ask_reasoned(question="metformin and kidneys?", tenant_id="A"))
    assert _REASONED_FMT not in llm.compose_blob


def test_confident_management_still_gets_the_plan():
    llm = _KindLLM("management", confidence="high")
    asyncio.run(_kind_service(llm).ask_reasoned(question="metformin dose at eGFR 30-45?", tenant_id="A"))
    assert _REASONED_FMT in llm.compose_blob


def test_classifier_failure_falls_to_standard_when_routing():
    llm = _KindLLM("management", raise_scaffold=True)
    asyncio.run(_kind_service(llm).ask_reasoned(question="anything", tenant_id="A"))
    assert _REASONED_FMT not in llm.compose_blob


def test_forced_arm_keeps_the_plan_even_if_classifier_fails():
    llm = _KindLLM("management", raise_scaffold=True)
    asyncio.run(_kind_service(llm).ask_reasoned(question="anything", tenant_id="A", route=False))
    assert _REASONED_FMT in llm.compose_blob


def test_scaffold_default_kind_is_not_management():
    # an omitted `kind` must never mean "decision plan" — guard the Pydantic default itself
    import inspect
    from noesis_kernel.runtime import research as _r
    src = inspect.getsource(_r)
    assert '"overview", "comparison", "update"] = "lookup"' in src


def test_medical_directives_carry_the_panel_rules():
    from noesis_vertical_medical.reasoned import REASONED_ANSWER_FORMAT, REASONED_SCAFFOLD_PROMPT
    from noesis_vertical_medical.manifest import build_manifest
    MANIFEST = build_manifest()
    assert "even for" not in REASONED_ANSWER_FORMAT            # the line that forced plans on overviews
    assert "SCOPE" in REASONED_ANSWER_FORMAT
    for k in ("overview", "comparison", "update"):
        assert f'"{k}"' in REASONED_SCAFFOLD_PROMPT
        assert k in (MANIFEST.answer_formats or {})
        assert "Do now" in MANIFEST.answer_formats[k]          # each family names the plan as forbidden


def test_coverage_section_only_when_the_user_asked_several_subquestions():
    one = _KindLLM("management", asks=["dose at eGFR 30-45?"])
    asyncio.run(_kind_service(one).ask_reasoned(question="metformin dose at eGFR 30-45?", tenant_id="A"))
    assert _REASONED_FMT in one.compose_blob and _COVERAGE_ADDENDUM not in one.compose_blob
    two = _KindLLM("management", asks=["IV vs oral iron?", "when to transfuse?"])
    asyncio.run(_kind_service(two).ask_reasoned(question="IV vs oral iron, and when to transfuse?", tenant_id="A"))
    assert _REASONED_FMT in two.compose_blob and _COVERAGE_ADDENDUM in two.compose_blob


def test_reasoned_format_no_longer_carries_a_coverage_section():
    from noesis_vertical_medical.reasoned import REASONED_ANSWER_FORMAT, REASONED_COVERAGE_ADDENDUM
    assert "## Question coverage" not in REASONED_ANSWER_FORMAT
    assert "## Question coverage" in REASONED_COVERAGE_ADDENDUM
