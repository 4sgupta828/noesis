"""Ask-Panel orchestrator — domain-free. Runs a set of vertical-supplied SPECIALISTS (each a lens over
the same corpus) as independent grounded `run_react` loops in parallel, then synthesizes their POOLED
verified findings into one coherent panel answer. Grounding is preserved end-to-end: each specialist's
claims are span-verified in its own loop, and the synthesis composes ONLY from those verified findings
(reusing the same no-new-facts guards as `run_react`) — the panel adds no fact no specialist established.

A "specialist" is duck-typed config: `.id`, `.specialty`, `.lens` (system prompt), `.focus` (retrieval
terms that steer WHICH evidence is retrieved — the real lens differentiation), `.source_keys`.
"""
from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field

from noesis_kernel.research.budget import BudgetState
from noesis_kernel.research.react import (
    ComposedAnswer, _refs_valid, _unsupported_prose_tokens, _validate_interpretation, run_react,
)

_log = logging.getLogger(__name__)

_SPECIALIST_MAX_STEPS = 4       # narrower than a full answer (each lens is scoped)
_SPECIALIST_MAX_CALLS = 12      # per-specialist budget ceiling (panel = N × this, hard-capped)
_PANEL_CONCURRENCY = 3
_SYNTH_MAX_TOKENS = 8000


@dataclass
class SpecialistTake:
    id: str
    specialty: str
    answer: str
    grounded: bool
    n_verified: int
    error: str = ""


@dataclass
class PanelResult:
    question: str
    takes: list = field(default_factory=list)          # SpecialistTake per specialist
    synthesis: str = ""                                 # the chair's coherent panel answer
    claims: list = field(default_factory=list)          # pooled verified findings (dicts) the panel cites
    interpretation: list = field(default_factory=list)  # synthesis reasoning read
    confidence: dict | None = None
    reasoning_purpose: str = ""
    reasoning_conclusion: str = ""
    n_specialists: int = 0


async def _emit(on_event, ev: dict) -> None:
    if on_event is not None:
        try:
            await on_event(ev)
        except Exception:   # noqa: BLE001
            pass


async def run_panel(*, question, specialists, llm, embedder, make_retrievers, tenant_id,
                    workspace_id=None, synthesis_directive="",
                    chair_system_prompt="You are an evidence-grounded clinical research panel chair.",
                    classify_evidence=None, evidence_ranker=None, evidence_fitness=False,
                    on_event=None) -> PanelResult:
    """`make_retrievers(source_keys) -> (corpus_source, aux_source)` lets each specialist scope its
    sources without this module knowing the source registry (domain-free seam)."""
    result = PanelResult(question=question, n_specialists=len(specialists))

    # 1) Each specialist runs its own grounded loop, IN PARALLEL (capped). The focus terms steer
    # retrieval (different embedded query → different atoms); the lens shapes planning/extraction.
    sem = asyncio.Semaphore(_PANEL_CONCURRENCY)

    async def _run(spec):
        async with sem:
            await _emit(on_event, {"type": "specialist_start", "id": spec.id, "specialty": spec.specialty})
            try:
                corpus, aux = make_retrievers(list(spec.source_keys) or None)
                spec_q = f"{question}\n\n[Panel focus — {spec.specialty}: {spec.focus}]"
                res = await run_react(
                    question=spec_q, llm=llm, embedder=embedder, source=corpus, aux_source=aux,
                    tenant_id=tenant_id, workspace_id=workspace_id,
                    budget=BudgetState(max_calls=_SPECIALIST_MAX_CALLS),
                    system_prompt=spec.lens, answer_format=None, reasoning_read=False,
                    max_steps=_SPECIALIST_MAX_STEPS, classify_evidence=classify_evidence,
                    evidence_ranker=evidence_ranker, evidence_fitness=evidence_fitness)
                await _emit(on_event, {"type": "specialist_done", "id": spec.id,
                                       "verified": len(res.verified_claims)})
                return spec, res, ""
            except Exception as e:   # noqa: BLE001 — one specialist failing must not sink the panel
                _log.warning("panel specialist %s failed: %r", spec.id, e)
                return spec, None, repr(e)[:200]

    ran = await asyncio.gather(*[_run(s) for s in specialists])

    # 2) Pool every specialist's span-verified findings into ONE numbered list (the only facts the
    # synthesis may use). Keep specialist attribution for the "perspectives" section.
    pooled = []                          # list of (specialty, VerifiedClaim)
    for spec, res, err in ran:
        take = SpecialistTake(id=spec.id, specialty=spec.specialty,
                              answer=(res.composed_answer if res else ""),
                              grounded=bool(res and res.grounded),
                              n_verified=len(res.verified_claims) if res else 0, error=err)
        result.takes.append(take)
        if res:
            for vc in res.verified_claims:
                pooled.append((spec.specialty, vc))

    if not pooled:
        result.synthesis = ("_The panel could not ground an answer — no specialist found verifiable "
                            "evidence for this question._")
        return result

    verified = [vc for _, vc in pooled]
    findings = "\n".join(
        f"[{i}] ({spec}) {vc.text}  (quote: \"{vc.quote}\" — {vc.source_key})"
        for i, (spec, vc) in enumerate(pooled, 1))

    # 3) Grounded synthesis: ONE compose over the pooled findings (reasoning read on for the panel view).
    reason_anchor = (
        "\n\nSEPARATELY, populate the STRUCTURED Reasoning Read fields for the PANEL: `reasoning_purpose` "
        "(the decision the panel is helping make), 2–5 `interpretation` factors (each resting on the "
        "finding numbers it uses via `basis_findings`, no number not in those findings), "
        "`reasoning_conclusion` (the panel's informed judgment), and the 3-dimension `confidence` read.")
    synth_user = (
        f"Question: {question}\n\nVERIFIED PANEL FINDINGS (from the specialists — the ONLY facts you may "
        f"use, each tagged with the specialist who found it):\n{findings}\n\n"
        "Synthesize these into ONE coherent panel answer. Reference each finding inline as [n]. Use ONLY "
        "the findings above — add no fact, figure, dose, or claim not present in them."
        + reason_anchor
        + (("\n\n" + synthesis_directive) if synthesis_directive else ""))

    async def _compose():
        comp = await llm.complete(system=chair_system_prompt,
                                  messages=[{"role": "user", "content": synth_user}],
                                  response_format=ComposedAnswer, max_tokens=_SYNTH_MAX_TOKENS)
        return comp.parsed

    parsed, text = None, ""
    for attempt in range(3):
        try:
            parsed = await _compose()
            text = (parsed.answer or "").strip()
            if text and _refs_valid(text, len(verified)):
                break
        except Exception as e:   # noqa: BLE001
            _log.warning("panel synthesis attempt %d failed: %r", attempt + 1, e)
    if not text:
        result.synthesis = ("_The panel gathered verified evidence (below) but could not compose a "
                            "synthesis just now. Please retry._")
        result.claims = [_vc_dict(vc) for vc in verified]
        return result

    result.synthesis = text
    result.claims = [_vc_dict(vc) for vc in verified]
    # Grounding guards over the pooled findings — identical discipline to run_react's compose.
    result.interpretation = _validate_interpretation(getattr(parsed, "interpretation", []) or [], verified)
    conf = getattr(parsed, "confidence", None)
    result.confidence = conf.model_dump() if conf is not None else None
    _all_tok = _pooled_tokens(verified)
    result.reasoning_purpose = _grounded(getattr(parsed, "reasoning_purpose", ""), _all_tok)
    result.reasoning_conclusion = _grounded(getattr(parsed, "reasoning_conclusion", ""), _all_tok)
    unsupported = _unsupported_prose_tokens(text, verified)
    if unsupported:
        _log.warning("panel synthesis prose introduced unsupported figures: %s", sorted(unsupported))
    return result


def _vc_dict(vc) -> dict:
    return {"text": vc.text, "quote": vc.quote, "atom_id": vc.atom_id, "source": vc.source_key,
            "title": vc.document_title, "document_id": vc.document_id,
            "evidence_kind": getattr(vc, "evidence_kind", "")}


def _pooled_tokens(verified) -> set:
    from noesis_kernel.research.react import extract_hard_tokens
    return extract_hard_tokens(" ".join((vc.text + " " + vc.quote) for vc in verified))


def _grounded(s: str, allowed_tokens: set) -> str:
    from noesis_kernel.research.react import extract_hard_tokens
    s = (s or "").strip()
    return s if (s and extract_hard_tokens(s).issubset(allowed_tokens)) else ""
