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
import re
from dataclasses import dataclass, field

from pydantic import BaseModel

from noesis_kernel.research.atoms import identity_tag
from noesis_kernel.research.budget import BudgetState
from noesis_kernel.research.react import (
    ComposedAnswer, _refs_valid, _unsupported_prose_tokens, run_react, strip_control_tags,
)

_log = logging.getLogger(__name__)


# ---- Phase 1: auto-selection (triage) ------------------------------------------------------------

class SpecialistPick(BaseModel):
    id: str                 # a roster specialist id
    rationale: str          # one line: why THIS specialist matters for THIS case


class PanelPlan(BaseModel):
    specialists: list[SpecialistPick] = []


async def plan_panel(*, question, roster, llm) -> list[dict]:
    """Auto-select the specialists whose lens is most relevant to the case (an LLM triage — a semantic
    judgment, Rule 18). `roster` is a list of {id, specialty, lens}. Returns the selected picks (each
    {id, specialty, rationale}); always includes an integrator/EBM baseline if the model omits everything.
    Fail-safe: any error → a sensible default subset so the panel still convenes."""
    by_id = {r["id"]: r for r in roster}
    catalog = "\n".join(f"- {r['id']} — {r['specialty']}: {(r.get('lens') or '')[:180]}" for r in roster)
    system = ("You are the chair of a clinical case panel. COVERAGE FIRST: convene a lens for EVERY "
              "clinically important dimension THIS case raises — never leave a dimension uncovered. Each "
              "distinct organ system, condition, or safety axis the case spans needs a lens that covers it "
              "(e.g. a case spanning heart failure + kidney disease + diabetes needs the cardiac, renal, "
              "AND metabolic lenses — not just one). THEN MINIMAL: among panels that fully cover the case, "
              "pick the smallest — never add a lens the case does not touch, and don't use two lenses where "
              "one covers the dimension. Always include the evidence-quality lens for rigor. A focused "
              "single-issue case may need only 2; a multi-system case needs one lens per system.")
    user = (f"Case / question:\n{question}\n\nAvailable specialists:\n{catalog}\n\nReturn the specialists "
            "that TOGETHER fully cover this case with no redundancy — every important dimension covered, no "
            "padding. For EACH, a ONE-LINE rationale naming the specific dimension of THIS case it covers.")
    try:
        comp = await llm.complete(system=system, messages=[{"role": "user", "content": user}],
                                  response_format=PanelPlan, max_tokens=1200)
        picks = [p for p in (comp.parsed.specialists or []) if p.id in by_id]
    except Exception as e:   # noqa: BLE001 — triage must never block convening
        _log.warning("panel triage failed: %r", e)
        picks = []
    seen, out = set(), []
    for p in picks:
        if p.id in seen:
            continue
        seen.add(p.id)
        out.append({"id": p.id, "specialty": by_id[p.id]["specialty"], "rationale": p.rationale.strip()})
    return out

_REF_RE = re.compile(r"\[\d+\]")   # strip a specialist's OWN local [n] refs when feeding its prose to the chair
_SPECIALIST_MAX_STEPS = 4       # narrower than a full answer (each lens is scoped)
# Per-specialist budget ceiling (panel = N × this, hard-capped). Raised 12 → 16 (Evidence Contract
# stage 2 re-plan): the fallback grounder (+1) and, under the claim-congruence flag, the binding
# batches (+1–2) are now CHARGED — previously-unmetered spend a worst-case specialist run (4 steps
# + 3 extract-recoveries + 3 compose attempts = 10) could newly trip at 12. Same true spend.
_SPECIALIST_MAX_CALLS = 16
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
    claims: list = field(default_factory=list)   # this specialist's OWN verified findings (its [n] resolve here)
    rationale: str = ""                          # why this specialist was convened for THIS case (triage)


# Each specialist is ONE voice on the panel — a focused, structured, SCANNABLE take (its full evidence
# shows beneath it), not a full answer. The chair's executive summary is where it all comes together.
_SPECIALIST_ANSWER_FORMAT = (
    "You are ONE specialist on a panel — give a FOCUSED assessment from YOUR lens ONLY, not a full answer. "
    "Stay in your lane; don't cover other specialties' angles. Be concise and STRUCTURED so a clinician "
    "scans it fast:\n"
    "- 3–5 short bullet points, each a single clinically-relevant point from your lens (grounded, cite [n]).\n"
    "- End with one line: **Bottom line:** your lens's take in a sentence.\n"
    "Every factual sentence carries an inline [n] referencing your findings.")


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
                    workspace_id=None, synthesis_directive="", history_context="", attachment_context="",
                    rationales=None,
                    chair_system_prompt="You are an evidence-grounded clinical research panel chair.",
                    classify_evidence=None, evidence_ranker=None, evidence_fitness=False,
                    evidence_identity=False, claim_congruence=False, on_event=None) -> PanelResult:
    """`make_retrievers(source_keys) -> (corpus_source, aux_source)` lets each specialist scope its
    sources without this module knowing the source registry (domain-free seam). `history_context` is the
    prior conversation (context ONLY, never citable) so a follow-up turn reasons in context — same
    contract as run_react's history. `on_event` streams live progress: specialist_start/_done plus each
    specialist's own run_react trace wrapped as {type: specialist_trace, id, ev}."""
    result = PanelResult(question=question, n_specialists=len(specialists))

    # 1) Each specialist runs its own grounded loop, IN PARALLEL (capped). The focus terms steer
    # retrieval (different embedded query → different atoms); the lens shapes planning/extraction.
    sem = asyncio.Semaphore(_PANEL_CONCURRENCY)

    async def _run(spec):
        async with sem:
            await _emit(on_event, {"type": "specialist_start", "id": spec.id, "specialty": spec.specialty})
            # forward this specialist's OWN run_react trace, tagged so the UI routes it to its row
            async def _spec_emit(ev, _sid=spec.id):
                await _emit(on_event, {"type": "specialist_trace", "id": _sid, "ev": ev})
            try:
                corpus, aux = make_retrievers(list(spec.source_keys) or None)
                spec_q = f"{question}\n\n[Panel focus — {spec.specialty}: {spec.focus}]"
                res = await run_react(
                    question=spec_q, llm=llm, embedder=embedder, source=corpus, aux_source=aux,
                    tenant_id=tenant_id, workspace_id=workspace_id, history_context=history_context,
                    attachment_context=attachment_context,
                    budget=BudgetState(max_calls=_SPECIALIST_MAX_CALLS),
                    system_prompt=spec.lens, answer_format=_SPECIALIST_ANSWER_FORMAT, reasoning_read=False,
                    max_steps=_SPECIALIST_MAX_STEPS, classify_evidence=classify_evidence,
                    evidence_ranker=evidence_ranker, evidence_fitness=evidence_fitness,
                    evidence_identity=evidence_identity, claim_congruence=claim_congruence,
                    on_event=_spec_emit)
                await _emit(on_event, {"type": "specialist_done", "id": spec.id,
                                       "verified": len(res.verified_claims)})
                return spec, res, ""
            except Exception as e:   # noqa: BLE001 — one specialist failing must not sink the panel
                _log.warning("panel specialist %s failed: %r", spec.id, e)
                await _emit(on_event, {"type": "specialist_done", "id": spec.id, "verified": 0,
                                       "error": repr(e)[:120]})
                return spec, None, repr(e)[:200]

    ran = await asyncio.gather(*[_run(s) for s in specialists])

    # 2) Pool every specialist's span-verified findings into ONE numbered list (the only facts the
    # synthesis may use). Keep specialist attribution for the "perspectives" section.
    pooled = []                          # list of (specialty, VerifiedClaim)
    for spec, res, err in ran:
        take = SpecialistTake(id=spec.id, specialty=spec.specialty,
                              answer=(res.composed_answer if res else ""),
                              grounded=bool(res and res.grounded),
                              n_verified=len(res.verified_claims) if res else 0, error=err,
                              claims=([_vc_dict(vc) for vc in res.verified_claims] if res else []),
                              rationale=(rationales or {}).get(spec.id, ""))
        result.takes.append(take)
        if res:
            for vc in res.verified_claims:
                pooled.append((spec.specialty, vc))

    if not pooled:
        result.synthesis = ("_The panel could not ground an answer — no specialist found verifiable "
                            "evidence for this question._")
        return result

    verified = [vc for _, vc in pooled]

    def _finding_source(vc) -> str:
        """Synthesis's source field — the document-identity tag appended alongside source_key under
        the evidence-identity flag (Evidence Contract stage 1). OFF (or no title) → byte-identical."""
        if not evidence_identity:
            return vc.source_key
        tag = identity_tag(vc)
        return f"{vc.source_key} {tag}" if tag else vc.source_key

    def _finding_note(vc) -> str:
        """Stage-2 annotation (claim-congruence flag): a non-empty congruence_note from a
        specialist's binding judge renders as a short bracketed marker (generic wording — kernel
        litmus). OFF → "" (byte-identical findings line)."""
        if not claim_congruence:
            return ""
        note = getattr(vc, "congruence_note", "")
        return f" [{note.replace('_', '-')}]" if note else ""

    findings = "\n".join(
        f"[{i}] ({spec}) {vc.text}  (quote: \"{vc.quote}\" — {_finding_source(vc)}){_finding_note(vc)}"
        for i, (spec, vc) in enumerate(pooled, 1))

    # 3) Grounded synthesis: ONE compose over the pooled findings. The panel's reasoning lives in the
    # answer's "How the panel reasoned" section (the collective reasoning) — we do NOT also request the
    # structured reasoning-read layer here: it's redundant with that narrative and the model reliably
    # malforms it when asked for both (Rule 10 — stop patching, remove the redundancy).
    await _emit(on_event, {"type": "synthesizing", "findings": len(verified)})
    # prior conversation (context ONLY — never a citable finding), same contract as run_react's history
    conv = (history_context or "").strip()
    conv_ctx = (f"CONVERSATION SO FAR (prior questions and answers in this panel thread; context to "
                f"interpret the CURRENT question — NOT evidence, NEVER cite it as a finding):\n{conv}\n\n"
                if conv else "")
    # Each specialist's OWN reasoning (their take) — the raw material for the COLLECTIVE reasoning. The
    # overall reasoner reads HOW each lens reasoned; but this is CONTEXT, not citable (only the numbered
    # findings are). Local [n] refs stripped so they don't collide with the pooled numbering.
    def _assess(t):
        head = f"{t.specialty} (convened for: {t.rationale})" if t.rationale else t.specialty
        return f"{head}:\n{_REF_RE.sub('', t.answer).strip()}"
    assessments = "\n\n".join(_assess(t) for t in result.takes if t.answer)
    assess_ctx = (f"SPECIALIST ASSESSMENTS — how EACH lens reasoned about THIS case. Use this to build the "
                  f"panel's COLLECTIVE reasoning (where the lenses agree, where they weigh evidence "
                  f"differently and how you reconcile it). This is REASONING CONTEXT, NOT citable evidence — "
                  f"cite ONLY the numbered findings below:\n{assessments}\n\n" if assessments else "")
    # uploaded image/document context (frames the answer, never a citable finding)
    attach = (attachment_context or "").strip()
    attach_ctx = (f"ATTACHMENT CONTEXT (what the user uploaded — an image reading and/or document text; "
                  f"use it to interpret the case, but it is NOT a citable finding):\n{attach}\n\n" if attach else "")
    synth_user = (
        conv_ctx + attach_ctx + assess_ctx
        + f"Question: {question}\n\nVERIFIED PANEL FINDINGS (the ONLY facts you may cite, each tagged with "
        f"the specialist who found it):\n{findings}\n\n"
        "As the panel's OVERALL REASONER, integrate the specialist assessments and these findings into ONE "
        "collective answer. Reference each finding inline as [n]. Every FACTUAL statement must rest on a "
        "finding above — add no fact, figure, dose, or claim not present in them (the assessments guide the "
        "REASONING, never introduce a new fact)."
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
            text = strip_control_tags((parsed.answer or "").strip())
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
    # Reasoning lives in the answer's "How the panel reasoned" section (purpose, integration, conclusion,
    # and confidence-in-prose) — the structured reasoning-read layer is intentionally OFF for the panel.
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
