"""Chart guidance must ride on EVERY clinician compose directive.

The alternate engines pass `answer_format_override`, which REPLACES the base directive in the kernel
(runtime/research.py). Appending the chart guidance only to `answer_format` therefore left the
reasoned (Clinical Decision) engine — the prod default, and the engine behind the Case Board — with
no chart instructions at all, so `charts` came back empty however grounded the numbers were. These
tests pin the wiring so that regression cannot come back silently.
"""
from __future__ import annotations

import pytest

from api.app import build_default_service


def _svc(monkeypatch, *, charts: str = "1", clinical: str = "1"):
    monkeypatch.setenv("NOESIS_STRUCTURED_ANSWERS", "1")
    monkeypatch.setenv("NOESIS_DIFFERENTIAL_FORMAT", "1")
    monkeypatch.setenv("NOESIS_ANSWER_CHARTS", charts)
    monkeypatch.setenv("NOESIS_CLINICAL_CHARTS", clinical)
    monkeypatch.setenv("NOESIS_PROVIDER_MODE", "replay")
    return build_default_service()


def _clinician_directives(svc) -> dict[str, str]:
    out = {"answer_format": svc.answer_format,
           "reasoned_answer_format": svc.reasoned_answer_format,
           "differential_answer_format": svc.differential_answer_format,
           "understanding_answer_format": svc.understanding_answer_format}
    for kind, directive in (svc.answer_formats or {}).items():
        out[f"answer_formats[{kind}]"] = directive
    return {k: v for k, v in out.items() if v}


def test_every_clinician_directive_carries_the_chart_guidance(monkeypatch) -> None:
    svc = _svc(monkeypatch)
    directives = _clinician_directives(svc)
    # the families the router can select must all be present, or the assertion below is vacuous
    for expected in ("answer_format", "reasoned_answer_format", "differential_answer_format",
                     "answer_formats[overview]", "answer_formats[comparison]", "answer_formats[update]"):
        assert expected in directives, f"{expected} missing — chart coverage would be untested"
    for name, directive in directives.items():
        assert "CHARTS (`charts` field)" in directive, f"{name} has no chart guidance"
        assert 'kind:"icon_array"' in directive, f"{name} has no clinical-numeracy chart kinds"


def test_chart_guidance_is_absent_when_the_flag_is_off(monkeypatch) -> None:
    svc = _svc(monkeypatch, charts="0")
    for name, directive in _clinician_directives(svc).items():
        assert "CHARTS (`charts` field)" not in directive, f"{name} carries chart guidance with the flag off"


def test_clinical_kinds_are_independently_gated(monkeypatch) -> None:
    svc = _svc(monkeypatch, clinical="0")
    for name, directive in _clinician_directives(svc).items():
        assert "CHARTS (`charts` field)" in directive, f"{name} has no chart guidance"
        assert 'kind:"icon_array"' not in directive, f"{name} carries clinical kinds with that flag off"


def test_case_runs_persist_the_visual_layers() -> None:
    """The Case Board's generation payload must keep charts + the reasoning layer (they were dropped
    before 2026-09-07, so every stored case answer rendered as prose only)."""
    import inspect

    from api import app as app_mod
    src = inspect.getsource(app_mod)
    start = src.index("async def cases_generate")
    # the whole route body, not a fixed window — the function grows and a window silently stops
    # covering the payload it is meant to pin
    end = src.index("@app.get(\"/cases/status\")", start)
    body = src[start:end]
    for field in ('"charts"', '"interpretation"', '"confidence"', '"visuals"'):
        assert field in body, f"case run payload drops {field}"


def test_batch_model_override_does_not_change_the_default_service(monkeypatch) -> None:
    """A bulk backfill may run on a cheaper model; live answers must keep the prod model. The model
    NAME picks its provider (runtime/build._route_by_name), so no env switch is involved."""
    monkeypatch.setenv("NOESIS_PROVIDER_MODE", "replay")
    monkeypatch.delenv("NOESIS_LLM_PROVIDER", raising=False)
    monkeypatch.delenv("NOESIS_LLM_MODEL", raising=False)
    monkeypatch.setenv("DEEPSEEK_API_KEY", "test-key")

    default_svc = build_default_service()
    cheap_svc = build_default_service("deepseek-chat")
    assert default_svc.llm is not cheap_svc.llm

    from noesis_kernel.runtime.build import _route_by_name
    assert _route_by_name("deepseek-chat") == "deepseek"
    assert _route_by_name("claude-sonnet-5") == "anthropic"
    assert _route_by_name(None) is None


def test_case_generate_accepts_a_model_override() -> None:
    from api.app import CaseGenerateIn
    assert CaseGenerateIn().model == ""
    assert CaseGenerateIn(model="deepseek-chat").model == "deepseek-chat"
