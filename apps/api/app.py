"""FastAPI app — POST /research over the multi-source agent.

Vertical-neutral: it activates ONE vertical at boot (NOESIS_ACTIVE_VERTICAL) and
serves its sources + gating + persona. Providers run in NOESIS_PROVIDER_MODE
(replay by default → offline/free). A ResearchService can be injected for tests.
"""
from __future__ import annotations

import asyncio
import json
import os
import re
import time
import uuid
from pathlib import Path

from fastapi import FastAPI, Header, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field

from noesis_kernel.providers.base import resolve_mode
from noesis_kernel.providers.cassette import CassetteMiss
from noesis_kernel.retrieval.postgres import PostgresRetrievalSource
from noesis_kernel.retrieval.web import WebRetrievalSource
from noesis_kernel.runtime.build import build_embedder, build_llm, build_web, load_active_vertical
from noesis_kernel.runtime.ingest import ingest_connector_to_postgres
from noesis_kernel.runtime.research import ResearchService

_WEB_DIR = Path(__file__).resolve().parent.parent / "web"

# ---- Resumable SSE runs -----------------------------------------------------
# Railway's edge closes long-lived SSE connections after ~30-60s in steady state
# regardless of keepalives (verified with the LLM-free /admin/stream-test probe:
# clean EOF after ~3 pings — every client, no deploy in flight, no app restart).
# The app can't prevent that, so streams are RESUMABLE instead: every streaming
# run buffers its events here under a run_id, and GET /stream/{run_id}?since=N
# replays the buffer from any cursor and follows live. The FE reconnects
# silently on any drop, so an edge cut becomes a sub-second blip instead of an
# error. The buffer is per-replica process memory: with numReplicas>1 a resume
# can land on a replica that never saw the run (404) — the FE retries (each
# attempt re-rolls the replica) and ultimately falls back to /sessions polling,
# which reads the cross-replica store.
_SSE_RUNS: dict[str, dict] = {}
_SSE_RUN_TTL = 30 * 60   # keep finished runs resumable this long


def _sse_run_new() -> dict:
    now = time.time()
    for k in [k for k, v in _SSE_RUNS.items() if now - v["ts"] > _SSE_RUN_TTL]:
        _SSE_RUNS.pop(k, None)
    run = {"id": uuid.uuid4().hex, "events": [], "done": False, "ts": now, "task": None}
    _SSE_RUNS[run["id"]] = run
    return run


def _sse_push(run: dict, ev: dict) -> None:
    run["events"].append(ev)
    run["ts"] = time.time()


def _sse_done(run: dict) -> None:
    run["done"] = True
    run["ts"] = time.time()


async def _sse_follow(run: dict, since: int = 0):
    """Yield the run's events from cursor `since` (each stamped with `_seq` so the client knows
    its resume cursor), following live with 15s pings until the run is done. The events list is
    append-only on a single event loop, so no locking is needed."""
    idx = max(0, int(since))
    last_beat = time.time()
    while True:
        events = run["events"]
        if idx < len(events):
            while idx < len(run["events"]):
                yield f"data: {json.dumps(dict(run['events'][idx], _seq=idx))}\n\n"
                idx += 1
            last_beat = time.time()
        elif run["done"]:
            return
        else:
            await asyncio.sleep(0.4)
            if time.time() - last_beat >= 15:
                yield ": ping\n\n"
                last_beat = time.time()


def structured_answers() -> bool:
    """Flag (default OFF, Rule 20): when ON, the active vertical's answer_format
    directive shapes the synthesized answer (markdown sections). OFF = flat prose,
    byte-identical to the pre-flag path."""
    return os.environ.get("NOESIS_STRUCTURED_ANSWERS", "").lower() in ("1", "true", "yes")


def clinical_synthesis() -> bool:
    """Flag (default OFF, Rule 20): when ON (and structured answers are ON), the medical vertical's
    SHARPER clinical-synthesis directive shapes the answer — scope-up-front, registry=protocol-not-
    efficacy, surrogate≠clinical endpoints, preserve specific figures, no citation stacking, no vague
    hype. Same adaptive section set — provenance unchanged. OFF → the base answer_format, byte-identical."""
    return os.environ.get("NOESIS_CLINICAL_SYNTHESIS", "").lower() in ("1", "true", "yes")


def vision_enabled() -> bool:
    """Flag (default OFF, Rule 20): when ON, uploaded image/PDF/DICOM attachments are
    described by the vision pre-step and used as CONTEXT for the grounded research. The
    description is never a verified claim. OFF → attachments are ignored."""
    return os.environ.get("NOESIS_VISION", "").lower() in ("1", "true", "yes")


def gap_healing_enabled() -> bool:
    """Flag (default OFF, Rule 20): when ON, an under-evidenced answer can surface a gap-fill
    plan (LLM-proposed connector ingest jobs) that the user queues, and a background processor
    ingests them into the corpus — self-healing. OFF → no gap plan, endpoints 404, no processor."""
    return os.environ.get("NOESIS_GAP_HEALING", "").lower() in ("1", "true", "yes")


def pulse_enabled() -> bool:
    """Flag (default OFF, Rule 20): Evidence Pulse P0 — the corpus-currency subsystem.
    ON: curator-declared lineage sweeps into the change-event ledger, approved events stamp
    superseded/retracted facets onto blocks, and retrieval + claim ranking demote superseded
    (exclude retracted) sources. OFF → no ledger, no stamps, no demotion — byte-identical."""
    return os.environ.get("NOESIS_PULSE", "").lower() in ("1", "true", "yes")


def stream_enabled() -> bool:
    """Flag (default OFF, Rule 20): when ON, /research/stream serves live SSE progress events
    (searching/found/verifying/composing → final). OFF → the endpoint 404s; /research unchanged."""
    return os.environ.get("NOESIS_STREAM", "").lower() in ("1", "true", "yes")


def country_scope_enabled() -> bool:
    """Flag (default OFF, Rule 20): when ON, a request may scope retrieval to a source country via
    `countries` (hard filter on the `source_country` facet). OFF → `countries` is ignored and NO facet
    is applied (byte-identical to today). MUST NOT be flipped on in prod until every block is tagged
    with source_country (else a scoped query returns empty — the legacy-null-excluded trap)."""
    return os.environ.get("NOESIS_COUNTRY_SCOPE", "").lower() in ("1", "true", "yes")


def country_boost_enabled() -> bool:
    """Flag (default OFF, Rule 20): when ON, a request's `countries` BOOSTS that region's evidence in
    ranking (region-specific findings surface) WITHOUT filtering out the global evidence base — the
    'relevant yet not limiting' path. Boost-only; no null-exclusion trap. OFF → `countries` drives no
    boost (byte-identical). Independent of NOESIS_COUNTRY_SCOPE (the hard filter)."""
    return os.environ.get("NOESIS_COUNTRY_BOOST", "").lower() in ("1", "true", "yes")


def _country_boost(countries: list[str] | None):
    """Selected countries → a boost set (e.g. {"IN"}) when the boost flag is on, else None (no-op)."""
    if not country_boost_enabled():
        return None
    valid = {c for c in (countries or []) if c in set(AVAILABLE_COUNTRIES)}
    return valid or None


def effort_scale_enabled() -> bool:
    """Flag (default OFF, Rule 20): when ON, a request's `effort` multiplier (1.0..2.5) scales how
    hard the research loop works (turns, results considered, context, citations, LLM budget) on a
    hard question. OFF → `effort` is forced to 1.0 and ignored (byte-identical to today). Effort only
    scales STRUCTURAL search — the provenance/grounding gates are never touched."""
    return os.environ.get("NOESIS_EFFORT_SCALE", "").lower() in ("1", "true", "yes")


# Effort slider stops echoed to /config when the flag is on (UI renders the control from this).
EFFORT_STOPS = [1.0, 1.25, 1.5, 1.75, 2.0, 2.25, 2.5]


def patient_mode_enabled() -> bool:
    """Flag (default OFF, Rule 20): when ON, a request may choose audience='patient' to get a
    patient-facing answer (same evidence + gates, a plain-language compose directive). OFF → audience
    is forced 'clinician' and the toggle/echo are hidden (byte-identical to today)."""
    return os.environ.get("NOESIS_PATIENT_MODE", "").lower() in ("1", "true", "yes")


def answer_charts_enabled() -> bool:
    """Flag (default OFF, Rule 20): when ON, append the vertical's chart guidance so compose may emit a
    grounded bar chart (each bar validated against its cited finding in code; ungrounded → dropped).
    Requires structured answers. OFF → the directive is unchanged and `charts` stays empty."""
    return os.environ.get("NOESIS_ANSWER_CHARTS", "").lower() in ("1", "true", "yes")


def refine_enabled() -> bool:
    """Flag (default OFF, Rule 20): when ON, a FRESH question (no history) is first sent to /refine,
    which proposes a few distinct sharper standalone questions to pick from (express refinement). The
    LLM returns [] when the question is already precise → the FE just answers it. OFF → no /refine
    step (byte-identical); follow-ups are never refined (the resolver handles those)."""
    return os.environ.get("NOESIS_REFINE", "").lower() in ("1", "true", "yes")


def answer_visuals_enabled() -> bool:
    """Flag (default OFF, Rule 20): when ON, append the vertical's visualization guidance to the
    compose directive so answers proactively use comparison tables / ranked options / pros-cons —
    strictly from the verified findings. Requires structured answers (tables render only then). OFF →
    the directive is unchanged (byte-identical)."""
    return os.environ.get("NOESIS_ANSWER_VISUALS", "").lower() in ("1", "true", "yes")


def ask_panel_enabled() -> bool:
    """Flag (default OFF, Rule 20 — ALPHA): when ON, a clinician can convene an AI specialist panel
    (`POST /panel/ask`) — each specialist runs its own grounded, lens-scoped research and the panel
    synthesizes their pooled verified findings. Costs N× a single answer; OFF → the endpoint 404s."""
    return os.environ.get("NOESIS_ASK_PANEL", "").lower() in ("1", "true", "yes")


def duel_enabled() -> bool:
    """Flag (default OFF, Rule 20): when ON, `engine="reasoned"` on /research[/stream] routes through
    the ALTERNATE reason-first engine (scaffold → coverage-steered retrieval → decision-gated compose)
    and the FE runs both engines on fresh questions as a blinded A/B with a which-is-better vote —
    clinician preference data that settles the retrieval-first vs reasoning-first question empirically.
    OFF → the engine param is ignored and no duel UI shows (byte-identical)."""
    return os.environ.get("NOESIS_DUEL", "").lower() in ("1", "true", "yes")


def reasoned_default_enabled() -> bool:
    """Flag (default OFF, live-toggleable): when ON, single answers (no explicit engine — i.e. whenever
    the A/B duel isn't running the question) DEFAULT to the REASONED engine: clinical scaffold →
    coverage-steered retrieval → decision-gated compose. Explicit engine="standard" (the duel's control
    arm) still runs standard, so duel votes keep their contrast. Costs +1 scaffold LLM call per fresh
    question. Grounding identical to the standard engine."""
    return os.environ.get("NOESIS_REASONED_DEFAULT", "").lower() in ("1", "true", "yes")


def integrative_enabled() -> bool:
    """Flag (default OFF, Rule 20): when ON, the per-question "include complementary & integrative
    approaches" opt-in appears (itself off by default per question). Double opt-in: this flag gates the
    feature; the user chooses per question. Grounding invariant unchanged — the section only shapes what
    is searched and how VERIFIED findings are presented; evidence-strength labels are required."""
    return os.environ.get("NOESIS_INTEGRATIVE", "").lower() in ("1", "true", "yes")


def accounts_enabled() -> bool:
    """Flag (default OFF, Rule 20 — adoption P0): when ON, users register a real account
    (`POST /auth/register`, free verified-clinician tier via structural NPI lookup) and every answer
    carries a feedback affordance (`POST /feedback`) keyed to the W1–W9 warrant taxonomy — the
    accumulating ground-truth signal. OFF → endpoints 404 and the FE keeps the localStorage-only
    identity gate (byte-identical)."""
    return os.environ.get("NOESIS_ACCOUNTS", "").lower() in ("1", "true", "yes")


def triage_enabled() -> bool:
    """Flag (default OFF, Rule 20): when ON, a "Guided" intake mode runs a short clarifying conversation
    (`POST /triage/step`) that converges on a crisp question and recommends a route (Quick Q&A vs
    Specialist Panel). One small LLM call per turn, hard-capped; it never answers or advises — only
    narrows + routes. OFF → the endpoint 404s and the FE shows only the two answer modes."""
    return os.environ.get("NOESIS_TRIAGE", "").lower() in ("1", "true", "yes")


# The clarifying-turn cap (structural convergence guarantee — code owns structure, the LLM owns meaning):
# after this many assistant questions, the next turn is FORCED to route. Keeps intake from interrogating.
TRIAGE_MAX_ASK = int(os.environ.get("NOESIS_TRIAGE_MAX_ASK", "2"))


def evidence_fitness_enabled() -> bool:
    """Flag (default OFF, Rule 20): when ON, the relevance-selection step additionally BOOSTS stronger
    evidence tiers (guideline/systematic-review > RCT > cohort > case report, via the medical authority
    pyramid) into the compose cap — so the answer rests on the best-tier evidence, not just the most
    similar text. Boost-only, provenance untouched. OFF → ranking is relevance-only (byte-identical)."""
    return os.environ.get("NOESIS_EVIDENCE_FITNESS", "").lower() in ("1", "true", "yes")


def diag_trace_enabled() -> bool:
    """Flag (default OFF, Rule 20): when ON, each research run captures a troubleshooting trace
    (per-turn steps, tool-call breakdown, the grounding funnel, retries, failures, budget, timing)
    surfaced in the Diagnostics box. Pure bookkeeping over data already in the loop — no extra LLM
    calls. OFF → no trace captured or surfaced (byte-identical)."""
    return os.environ.get("NOESIS_DIAG_TRACE", "").lower() in ("1", "true", "yes")


def reasoning_read_enabled() -> bool:
    """Flag (default OFF, Rule 20): when ON (and structured answers are ON), append the vertical's
    reasoning-read directive so compose emits a TYPED interpretation layer (tension/gap/assumption/
    implication/what-would-change) + a 3-dimension confidence read ON TOP of the grounded prose. Each
    item is validated in code — dangling refs and any fabricated number/dose/date/% are dropped — so
    grounding is never loosened. OFF → the directive is unchanged and no interpretation/confidence is
    surfaced (byte-identical)."""
    return os.environ.get("NOESIS_REASONING_READ", "").lower() in ("1", "true", "yes")


def answer_focus_enabled() -> bool:
    """Flag (default OFF, Rule 20): when ON, elliptical conversational follow-ups are condensed into a
    self-contained question (so retrieval + compose inherit the subject) AND compose ANSWERS the
    question / scopes to its subject instead of compiling every retrieved finding. Needs conversation
    context for the condense half; the compose-scope half also improves single-turn. OFF →
    byte-identical (no condense call, original compose instruction)."""
    return os.environ.get("NOESIS_ANSWER_FOCUS", "").lower() in ("1", "true", "yes")


def followup_clarify_enabled() -> bool:
    """Flag (default OFF, Rule 20): when ON (and answer-focus on, with history), a genuinely AMBIGUOUS
    follow-up returns a short CLARIFYING question instead of guessing/dumping (factra's CM pattern).
    OFF → the resolver never asks; it always returns a best-guess standalone question."""
    return os.environ.get("NOESIS_FOLLOWUP_CLARIFY", "").lower() in ("1", "true", "yes")


def _resolve_audience(audience: str | None) -> str:
    """The audience actually used: 'patient' only when the flag is on AND explicitly requested;
    everything else → 'clinician' (the default, byte-identical path)."""
    if patient_mode_enabled() and (audience or "").lower() == "patient":
        return "patient"
    return "clinician"


# Available source countries, echoed to /config when the flag is on (UI renders the toggle from this).
AVAILABLE_COUNTRIES = [{"code": "US", "label": "United States"}, {"code": "IN", "label": "India"}]


def _country_facets(countries: list[str] | None) -> dict:
    """Map a selected-country list → the hard retrieval facet, ALWAYS including 'global' so shared
    literature/trials are searched alongside the country's own sources. Off-flag or empty → {} (no
    filter, byte-identical). Only known country codes are honored (unknown → ignored)."""
    if not country_scope_enabled():
        return {}
    valid = {c["code"] for c in AVAILABLE_COUNTRIES}
    picked = tuple(c for c in (countries or []) if c in valid)
    if not picked:
        return {}
    return {"source_country": picked + ("global",)}


def conversation_enabled() -> bool:
    """Flag (default OFF, Rule 20): when ON, answers become a multi-turn thread — follow-up
    questions carry prior turns as context, the thread persists on one session, and suggested
    follow-ups are offered. OFF → single-answer behavior (each ask is a fresh session)."""
    return os.environ.get("NOESIS_CONVERSATION", "").lower() in ("1", "true", "yes")


class Attachment(BaseModel):
    data: str                              # base64-encoded file bytes
    media_type: str = ""                   # e.g. image/png, application/pdf, application/dicom
    name: str = ""


class ResearchIn(BaseModel):
    question: str
    tenant_id: str
    workspace_id: str | None = None
    sources: list[str] | None = None      # subset of source keys; None = all
    attachments: list[Attachment] | None = None   # images/PDF/DICOM → vision context
    user_name: str | None = None          # asker identity (captured at landing)
    user_email: str | None = None
    engine: str = ""                      # "" = auto (reasoned-default setting decides) · "standard" · "reasoned"
    integrative: bool = False             # per-question opt-in: complementary/integrative section (flag-gated)
    history: list[dict] | None = None     # prior turns [{question, answer}] → follow-up context
    session_id: str | None = None         # thread to append this turn to (conversation)
    countries: list[str] | None = None    # source-country scope (e.g. ["IN"]); None/[]=all (see flag)
    effort: float = Field(default=1.0, ge=1.0, le=2.5)   # effort multiplier; ignored unless flag on
    audience: str = "clinician"           # "clinician" (default) | "patient"; ignored unless flag on


class PanelIn(BaseModel):
    question: str                          # the clinician's issue / condition description
    tenant_id: str = "demo"
    workspace_id: str | None = None
    specialists: list[str] | None = None   # specialist ids to convene; None = the default panel
    sources: list[str] | None = None
    history: list[dict] | None = None      # prior panel turns [{question, answer, claims}] for a follow-up
    session_id: str | None = None          # the panel thread this turn continues (echoed back)
    rationales: dict | None = None         # {specialist_id: why-selected} from triage, shown per specialist
    attachments: list[Attachment] | None = None   # images/PDF/DICOM/pasted text → shared panel context


class SuggestIn(BaseModel):
    question: str
    answer: str = ""
    history: list[dict] | None = None


class RefineIn(BaseModel):
    question: str


class TriageIn(BaseModel):
    # The running intake transcript, oldest-first: [{role: "user"|"assistant", text}]. The FE holds it
    # (stateless server) and appends each turn. The last item is the user's latest message.
    transcript: list[dict] = []
    tenant_id: str = "demo"


class RegisterIn(BaseModel):
    name: str
    email: str
    profession: str = ""            # self-declared (Physician / NP-PA / Pharmacist / Student / …)
    country: str = ""
    npi: str = ""                   # optional (US) — structurally verified against the CMS registry
    disclaimer_ack: bool = False    # the attestation from the identity gate


class SettingIn(BaseModel):
    key: str
    value: str = ""     # "on" | "off" | "" (empty = follow the env default)


class FeedbackIn(BaseModel):
    session_id: str = ""
    turn_index: int = 0
    verdict: str                    # "up" | "down" | "flag"
    modes: list[str] = []           # W1–W9 codes (shared warrant taxonomy)
    claim_index: int | None = None  # 1-based finding a flag points at, when specific
    note: str = ""
    question: str = ""              # echo of the question for a self-contained feedback row


class ExplainIn(BaseModel):
    question: str
    answer: str
    session_id: str | None = None


class GapPlanIn(BaseModel):
    question: str
    answer: str = ""
    coverage_gaps: list[str] = []


class GapQueueIn(BaseModel):
    question: str = ""
    tenant_id: str = "demo"
    jobs: list[dict] = []                  # [{connector, query, limit, kind, rationale, quality}]


class CorpusIngestIn(BaseModel):
    """Bulk prod-direct ingest — the replacement for local download + push. Enqueues connector
    jobs into the corpus queue that the prod processor drains straight into the prod corpus."""
    conditions: list[str] = []             # each → a clinicaltrials + a europepmc job
    trials: int = 300                      # per-condition trial limit
    papers: int = 150                      # per-condition literature limit
    faers_drugs: list[str] = []            # each → a faers adverse-event job
    jobs: list[dict] = []                  # explicit passthrough {connector, query, limit, ...}
    source_country: str = ""               # stamp every block from this batch (e.g. "IN" for India sources)


class PulseEventIn(BaseModel):
    """Evidence Pulse admin action: approve (apply stamps) or retract (undo a mistake) an event."""
    event_id: str
    action: str          # approve | retract


class WatchIn(BaseModel):
    topic: str
    source: str = "manual"     # manual (free text → canonicalized) | suggested (already canonical)


class SeenIn(BaseModel):
    event_id: str


class TopicsIn(BaseModel):
    question: str = ""
    answer: str = ""


class PatientFlagIn(BaseModel):
    real_patient: bool = True


class Citation(BaseModel):
    text: str
    quote: str
    atom_id: str
    source: str = ""
    title: str = ""
    url: str | None = None           # canonical source page (opens in a new tab)
    document_id: str = ""


class ResearchOut(BaseModel):
    grounded: bool
    answer: str = ""                 # synthesized prose answer, grounded in findings
    claims: list[Citation]           # the verified findings (evidence for the answer)
    coverage_gaps: list[str]
    rejected: int
    source_stats: dict = {}          # source -> {retrieved, cited}
    degraded_sources: dict = {}      # sources that failed this request
    session_id: str | None = None    # saved Q&A id (for history + linking a video)
    stopped_reason: str = ""         # answered | budget | max_steps (observability)
    atoms_gathered: int = 0          # evidence blocks the agent saw (observability)
    retried_empty: bool = False      # the abstention-recovery re-ask fired (observability)
    visual_observation: str = ""     # labeled AI image description (context, NOT a finding)
    attachment_notes: list[str] = [] # anything skipped when reading attachments
    effort: float | None = None      # resolved effort multiplier (only set when the flag is on)
    audience: str | None = None      # resolved audience 'clinician'|'patient' (only set when flag on)
    resolved_question: str | None = None  # condensed follow-up question, if it differed (flag on only)
    clarification: str | None = None      # a clarifying question when the follow-up was ambiguous
    derived_from_prior: bool = False      # answer is a reshape of the previous answer (no new evidence)
    charts: list = []                     # validated grounded bar charts (empty unless the flag is on)
    interpretation: list = []             # validated reasoning-read factors (empty unless the flag is on)
    confidence: dict | None = None        # 3-dimension confidence read (None unless the flag is on)
    reasoning_purpose: str = ""           # the decision the reasoning serves (empty unless the flag is on)
    reasoning_conclusion: str = ""        # the informed judgment toward that purpose (flag on only)
    diagnostics: dict | None = None       # troubleshooting trace (None unless the diag-trace flag is on)


def build_default_service() -> ResearchService:
    """Assemble the service from the active vertical + env providers.

    NOTE: the corpus source's embedding dimension must match the query embedder;
    in production the corpus is Postgres-backed with OpenAI embeddings (1536) and
    the query embedder matches. Deployment wiring finalizes this alignment.
    """
    manifest = load_active_vertical()
    mode = resolve_mode()
    embedder = build_embedder(mode=mode)
    dsn = os.environ.get("NOESIS_CORPUS_DSN")

    sources: dict = {}
    connectors: dict = {}
    corpus_key = ""
    if dsn:
        # Real pgvector corpus (empty until POST /ingest). One pg source, registered
        # under the vertical's corpus source key so gating/covers still align.
        covers = next((s.covers() for s in manifest.retrieval_sources.values()
                       if hasattr(s, "covers")), {})
        pg = PostgresRetrievalSource(dsn, dim=embedder.dim, table="rs_block", covers=covers,
                                     currency_demote=pulse_enabled())
        corpus_key = next(iter(manifest.retrieval_sources), "corpus")
        sources[corpus_key] = pg
        connectors = dict(manifest.connectors)
    else:
        sources = dict(manifest.retrieval_sources)      # fixture (in-memory) corpus
    sources["web"] = WebRetrievalSource(
        build_web(mode=mode, domains=getattr(manifest, "web_domains", ())),
        # venue-authority facets + the corpus embedder: web evidence gets graded and reranked
        # by the same machinery as corpus evidence (authority tiers, recency, query relevance)
        domain_facets=getattr(manifest, "web_domain_facets", None),
        embedder=embedder)

    persona = manifest.persona.system_prompt() if manifest.persona else \
        "You are an evidence-grounded research agent."
    # Flag-gated (Rule 20): only pass the vertical's answer-structure directive when ON.
    # OFF → None → the kernel's flat-prose compose path, byte-identical to pre-flag. When the
    # separate clinical-synthesis flag is ALSO on, swap in the sharper directive (A/B seam);
    # falls back to the base format if the vertical doesn't supply one.
    if structured_answers():
        answer_format = manifest.answer_format
        if clinical_synthesis():
            answer_format = getattr(manifest, "clinical_answer_format", None) or manifest.answer_format
    else:
        answer_format = None
    # Visualization guidance (flag): append to the CLINICIAN directive so answers use tables/rankings/
    # pros-cons from the verified findings. Only when structured answers are on (tables render then).
    if answer_format and answer_visuals_enabled() and getattr(manifest, "visual_guidance", None):
        answer_format = answer_format + "\n\n" + manifest.visual_guidance
    # Chart emission (flag): compose may populate a grounded bar chart, validated in the kernel.
    if answer_format and answer_charts_enabled() and getattr(manifest, "chart_guidance", None):
        answer_format = answer_format + "\n\n" + manifest.chart_guidance
    # Reasoning Read (flag): append the interpretation-layer directive so compose emits typed
    # interpretation + a confidence read (both validated in the kernel). Requires structured answers.
    if answer_format and reasoning_read_enabled() and getattr(manifest, "reasoning_format", None):
        answer_format = answer_format + "\n\n" + manifest.reasoning_format
    vision_prompt = manifest.vision_prompt if vision_enabled() else None
    gap_prompt = manifest.gap_prompt if gap_healing_enabled() else None
    suggest_prompt = manifest.suggest_prompt if conversation_enabled() else None
    refine_prompt = getattr(manifest, "refine_prompt", None) if refine_enabled() else None
    # Prompts are wired UNCONDITIONALLY so the live admin toggles (duel/triage) work without a
    # redeploy — an unused prompt is inert; gating happens at request time on the live flag.
    triage_prompt = getattr(manifest, "triage_prompt", None)
    reasoned_scaffold = getattr(manifest, "reasoned_scaffold_prompt", None)
    reasoned_format = getattr(manifest, "reasoned_answer_format", None)
    # Use the BEST model for EVERY research step (planning + claim extraction + compose). A cheaper
    # planner (haiku) paraphrased quotes → span-verification rejected them (grounding regression),
    # so planner_llm is left unset and run_react uses `llm` throughout. Optional explicit override.
    planner_model = os.environ.get("NOESIS_PLANNER_MODEL", "")   # empty → same strong model as compose
    planner_llm = build_llm(mode=mode, model=planner_model) if planner_model else None
    claims_first = os.environ.get("NOESIS_CLAIMS_FIRST", "").lower() in ("1", "true", "yes")
    # Evidence selection (flag, default OFF): raise the extractor's per-atom window so full-text
    # effect-size/CI sentences aren't truncated, AND keep the claims most RELEVANT to the question
    # for compose (not the first-come 30). Both are provenance-safe (span+entail gates unchanged).
    evidence_select = os.environ.get("NOESIS_EVIDENCE_SELECT", "").lower() in ("1", "true", "yes")
    atom_cap = int(os.environ.get("NOESIS_ATOM_CAP", "6000" if evidence_select else "1600"))
    # Patient directive (per-request by audience). Reasoning Read (flag): append the PATIENT-facing
    # reasoning directive so patient answers get the same purpose→factors→judgment→confidence arc in
    # plain language (same structured fields + code validation as the clinician path).
    patient_directive = manifest.patient_answer_format if patient_mode_enabled() else None
    if patient_directive and reasoning_read_enabled() and getattr(manifest, "patient_reasoning_format", None):
        patient_directive = patient_directive + "\n\n" + manifest.patient_reasoning_format
    return ResearchService(
        llm=build_llm(mode=mode), embedder=embedder, planner_llm=planner_llm,
        claims_first=claims_first, extraction_lenses=getattr(manifest, "extraction_lenses", ()),
        evidence_select=evidence_select, atom_cap=atom_cap,
        reasoning_read=reasoning_read_enabled(),
        collect_diagnostics=diag_trace_enabled(),
        classify_evidence=getattr(manifest, "evidence_classifier", None),
        evidence_fitness=evidence_fitness_enabled(),
        evidence_ranker=getattr(getattr(manifest, "authority_policy", None), "rank", None),
        panel_specialists=getattr(manifest, "panel_specialists", ()),
        panel_default_ids=getattr(manifest, "panel_default_ids", ()),
        panel_synthesis_directive=getattr(manifest, "panel_synthesis_directive", None),
        panel_examples=getattr(manifest, "panel_examples", ()),
        sources=sources, gating=manifest.gating_policy, persona_prompt=persona,
        answer_format=answer_format,
        # Patient directive resolved INDEPENDENTLY of structured_answers/clinical_synthesis — the
        # patient view selects it per-request by audience, so it must be available even when the
        # clinician structured-answer flags are off (else patient mode would silently no-op).
        patient_answer_format=patient_directive,
        vision_prompt=vision_prompt,
        layman_prompt=manifest.layman_prompt, gap_prompt=gap_prompt,
        suggest_prompt=suggest_prompt, refine_prompt=refine_prompt, triage_prompt=triage_prompt,
        reasoned_scaffold_prompt=reasoned_scaffold, reasoned_answer_format=reasoned_format,
        integrative_prompt=getattr(manifest, "integrative_prompt", None),
        integrative_query_hint=getattr(manifest, "integrative_query_hint", None),
        understanding_answer_format=getattr(manifest, "understanding_answer_format", None),
        understanding_query_hint=getattr(manifest, "understanding_query_hint", None),
        vertical_name=manifest.name, ui=manifest.ui,
        connectors=connectors, corpus_source_key=corpus_key,
    )


def _run_gap_processor(dsn: str, vertical: str) -> None:
    """Entry point for the DEDICATED ingest thread. Runs its own event loop so the heavy work
    (connector fetch + blocking OpenAI embed + index) never blocks the API's serving loop — this
    is what makes prod-direct ingestion, at bulk scale, safe to run inside the API process."""
    import asyncio as _a
    _a.run(_gap_processor_loop(dsn, vertical))


async def _gap_processor_loop(dsn: str, vertical: str) -> None:
    """One-at-a-time queue drain, on the ingest thread's own loop with its own pg pool + embedder +
    connectors. Atomic claim → replica-safe; a single job's error is recorded and the loop continues
    (Rule 13). Connectors open a fresh httpx client per call, so they are safe on this loop."""
    import asyncio
    from api.gap_queue import GapQueue
    from noesis_kernel.providers.base import resolve_mode
    from noesis_kernel.retrieval.postgres import PostgresRetrievalSource
    from noesis_kernel.runtime.build import build_embedder, load_active_vertical
    q = GapQueue(dsn, vertical=vertical)
    embedder = build_embedder(mode=resolve_mode())
    pg = PostgresRetrievalSource(dsn, dim=embedder.dim, table="rs_block")
    connectors = dict(load_active_vertical().connectors)
    # Evidence Pulse re-stamp hook: re-ingest overwrites block facets (erasing supersession/
    # retraction stamps) — after each completed job, re-derive stamps from the approved ledger.
    # THIS thread's own store/pool (the API loop's store must never be awaited from here).
    currency = None
    if pulse_enabled():
        from noesis_kernel.currency import CurrencyStore
        currency = CurrencyStore(dsn)
    while True:
        try:
            job = await q.claim_one()
        except Exception:
            await asyncio.sleep(10); continue
        if job is None:
            # WEEKLY retraction sweep, replica-safe via the DB clock (runs on the idle path so it
            # never delays a queued ingest; free — Europe PMC API only).
            if currency is not None:
                try:
                    import datetime as _dt
                    st = await currency.get_state("last_retraction_sweep") or {}
                    last = st.get("at", "")
                    due = (not last or (_dt.datetime.now(_dt.timezone.utc)
                           - _dt.datetime.fromisoformat(last)).days >= 7)
                    if due:
                        await currency.set_state("last_retraction_sweep",
                            {"at": _dt.datetime.now(_dt.timezone.utc).isoformat()})
                        from noesis_vertical_medical.retractions import retraction_lineage
                        doc_ids = await currency.list_document_ids(prefix="europepmc:")
                        await currency.sweep_declared(await retraction_lineage(doc_ids))
                except Exception:   # noqa: BLE001 — the admin scan remains the manual backstop
                    pass
            await asyncio.sleep(8); continue
        conn = connectors.get(job["connector"])
        if conn is None:
            await q.fail(job["id"], f"unknown connector {job['connector']}"); continue
        try:
            # a job may stamp a source_country on everything it ingests (country-specific sources)
            sc = job.get("source_country")
            n = await ingest_connector_to_postgres(
                conn, pg, tenant_id=job["tenant_id"], embedder=embedder,
                window={"query": job["query"], "limit": job["limit"]},
                facet_overrides={"source_country": sc} if sc else None)
            await q.complete(job["id"], n)
            if currency is not None:
                try:
                    await currency.apply_stamps()      # heal any stamps this ingest overwrote
                except Exception:   # noqa: BLE001 — best-effort; the admin scan is the backstop
                    pass
        except Exception as e:   # noqa: BLE001 — record + move on
            await q.fail(job["id"], str(e))


def create_app(service: ResearchService | None = None) -> FastAPI:
    app = FastAPI(title="Noesis Research", version="0")
    app.state.service = service   # lazily built on first request if None

    def _store():
        """Vertical-isolated research-session store (Postgres-backed). Built once when a
        corpus DSN is configured; None (no persistence) against the fixture corpus."""
        if getattr(app.state, "session_store", "unset") == "unset":
            dsn = os.environ.get("NOESIS_CORPUS_DSN")
            if dsn:
                from api.sessions import SessionStore
                app.state.session_store = SessionStore(dsn, vertical=load_active_vertical().name)
            else:
                app.state.session_store = None
        return app.state.session_store

    def _settings():
        """Live product-settings store (same DSN); None without a DSN → env-only flags."""
        if getattr(app.state, "setting_store", "unset") == "unset":
            dsn = os.environ.get("NOESIS_CORPUS_DSN")
            if dsn:
                from api.settings import SettingStore
                app.state.setting_store = SettingStore(dsn, vertical=load_active_vertical().name)
            else:
                app.state.setting_store = None
        return app.state.setting_store

    # Flags the admin panel can flip LIVE (DB override wins; empty → env default). Only flags whose
    # gating is fully REQUEST-time belong here — accounts_enabled stays env-only (it gates store
    # construction at boot). New product settings land in this dict going forward.
    _LIVE_FLAGS = {"duel_enabled": duel_enabled, "triage_enabled": triage_enabled,
                   "ask_panel_enabled": ask_panel_enabled, "integrative_enabled": integrative_enabled,
                   "reasoned_default_enabled": reasoned_default_enabled}

    async def _flag_live(key: str) -> bool:
        """Resolved value of a controlled flag: DB override → else env default. Fail-open to env."""
        env_fn = _LIVE_FLAGS[key]
        st = _settings()
        if st is None:
            return env_fn()
        try:
            from api.settings import SettingStore
            return SettingStore.resolve_flag(await st.get(key), env_fn())
        except Exception:   # noqa: BLE001 — settings must never break a request
            return env_fn()

    def _accounts():
        """Vertical-isolated account+feedback store (same DSN as sessions); None without a DSN."""
        if getattr(app.state, "account_store", "unset") == "unset":
            dsn = os.environ.get("NOESIS_CORPUS_DSN")
            if dsn and accounts_enabled():
                from api.accounts import AccountStore
                app.state.account_store = AccountStore(dsn, vertical=load_active_vertical().name)
            else:
                app.state.account_store = None
        return app.state.account_store

    async def _attach_video(session_id: str, **kw) -> None:
        store = _store()
        if store is not None:
            await store.attach_video(session_id, **kw)

    def _gap_queue():
        """Vertical-isolated corpus gap-fill queue (Postgres). None unless a corpus DSN is set
        AND gap-healing is enabled — so OFF is a true no-op."""
        if getattr(app.state, "gap_queue", "unset") == "unset":
            dsn = os.environ.get("NOESIS_CORPUS_DSN")
            if dsn and gap_healing_enabled():
                from api.gap_queue import GapQueue
                app.state.gap_queue = GapQueue(dsn, vertical=load_active_vertical().name)
            else:
                app.state.gap_queue = None
        return app.state.gap_queue

    def _currency():
        """Evidence Pulse ledger (Postgres). None unless a corpus DSN is set AND the pulse flag is
        on — so OFF is a true no-op (no table, no stamps, no demotion)."""
        if getattr(app.state, "currency", "unset") == "unset":
            dsn = os.environ.get("NOESIS_CORPUS_DSN")
            if dsn and pulse_enabled():
                from noesis_kernel.currency import CurrencyStore
                app.state.currency = CurrencyStore(dsn)
            else:
                app.state.currency = None
        return app.state.currency

    @app.on_event("startup")
    async def _start_gap_processor() -> None:
        """Launch the corpus-ingest processor in a DEDICATED daemon thread (own loop + pools), so
        prod-direct ingestion (gap-fill AND bulk batches) never blocks the API's serving loop.
        Replica-safe: each replica's thread claims jobs atomically, so N replicas share the drain."""
        dsn = os.environ.get("NOESIS_CORPUS_DSN")
        if gap_healing_enabled() and dsn and not getattr(app.state, "_gap_thread", None):
            import threading
            vertical = load_active_vertical().name
            t = threading.Thread(target=_run_gap_processor, args=(dsn, vertical),
                                 daemon=True, name="corpus-ingest")
            t.start()
            app.state._gap_thread = t

    # Answer-video add-on — separate, flag-gated router (default OFF). Kept fully out of
    # the research path: mounting it changes nothing about how answers are produced.
    from api.video import build_video_router, video_enabled
    if video_enabled():
        app.include_router(build_video_router(attach_video=_attach_video))

    @app.get("/health")
    def health() -> dict:
        return {"status": "ok"}

    @app.get("/config")
    async def config() -> dict:
        """The active vertical's declared UI + available sources (drives the shell).
        Panel/triage/duel flags resolve LIVE (admin-panel override → env default)."""
        if app.state.service is None:
            app.state.service = build_default_service()
        svc = app.state.service
        live_panel = await _flag_live("ask_panel_enabled")
        live_triage = await _flag_live("triage_enabled")
        live_duel = await _flag_live("duel_enabled")
        ui = getattr(svc, "ui", None)
        from api.video import video_enabled
        console = ui.console() if ui and hasattr(ui, "console") else {}
        return {
            "vertical": getattr(svc, "vertical_name", ""),
            "sources": list(svc.sources.keys()),
            "navigation": ui.navigation() if ui else [],
            "search_facets": ui.search_facets() if ui else [],
            "console": console,
            "video_enabled": video_enabled(),
            "structured_answers": structured_answers(),
            "clinical_synthesis": clinical_synthesis() and structured_answers(),
            "evidence_select": bool(getattr(svc, "evidence_select", False)),
            "vision_enabled": vision_enabled(),
            "layman_enabled": bool(getattr(svc, "layman_prompt", None)),
            "gap_healing_enabled": gap_healing_enabled() and bool(getattr(svc, "gap_prompt", None)),
            "conversation_enabled": conversation_enabled(),
            "suggest_enabled": conversation_enabled() and bool(getattr(svc, "suggest_prompt", None)),
            "stream_enabled": stream_enabled(),
            "country_scope_enabled": country_scope_enabled(),
            "countries": AVAILABLE_COUNTRIES if country_scope_enabled() else [],
            "effort_scale_enabled": effort_scale_enabled(),
            "effort_stops": EFFORT_STOPS if effort_scale_enabled() else [],
            "patient_mode_enabled": patient_mode_enabled(),
            "answer_focus_enabled": answer_focus_enabled(),
            "followup_clarify_enabled": followup_clarify_enabled(),
            "answer_visuals_enabled": answer_visuals_enabled(),
            "answer_charts_enabled": answer_charts_enabled(),
            "reasoning_read_enabled": reasoning_read_enabled() and structured_answers(),
            "diag_trace_enabled": diag_trace_enabled(),
            "evidence_fitness_enabled": evidence_fitness_enabled(),
            "ask_panel_enabled": live_panel,
            "panel_specialists": ([
                {"id": getattr(s, "id", ""), "specialty": getattr(s, "specialty", ""),
                 "focus": getattr(s, "focus", ""),   # the specialist's expertise, shown on the panel roster
                 "default": getattr(s, "id", "") in set(getattr(svc, "panel_default_ids", ()))}
                for s in getattr(svc, "panel_specialists", ())] if live_panel else []),
            "panel_examples": (list(getattr(svc, "panel_examples", ())) if live_panel else []),
            "refine_enabled": refine_enabled() and bool(getattr(svc, "refine_prompt", None)),
            "triage_enabled": live_triage and bool(getattr(svc, "triage_prompt", None)),
            "pulse_enabled": pulse_enabled() and bool(os.environ.get("NOESIS_CORPUS_DSN")),
            "accounts_enabled": accounts_enabled() and bool(os.environ.get("NOESIS_CORPUS_DSN")),
            "duel_enabled": live_duel and bool(getattr(svc, "reasoned_answer_format", None)),
            "integrative_enabled": (await _flag_live("integrative_enabled")) and bool(getattr(svc, "integrative_prompt", None)),
            "dynamic_engines_enabled": (await _flag_live("reasoned_default_enabled")) and bool(getattr(svc, "reasoned_answer_format", None)),
        }

    @app.post("/search")
    async def search(body: ResearchIn) -> dict:
        """Retrieval only (no LLM) — ranked evidence over the chosen sources.
        Always available (needs only the embedder), so the UI can show real
        evidence even when the answer model is unavailable."""
        if app.state.service is None:
            app.state.service = build_default_service()
        try:
            hits = await app.state.service.search(
                question=body.question, tenant_id=body.tenant_id,
                workspace_id=body.workspace_id, source_keys=body.sources, k=8)
        except Exception as e:
            raise HTTPException(status_code=502, detail=f"retrieval error: {e}") from e
        return {"evidence": [{
            "text": h.text[:600], "source": h.source_key or "corpus",
            "title": h.document_title, "score": round(h.score, 4),
        } for h in hits]}

    @app.post("/ingest")
    async def ingest(tenant_id: str = "demo") -> dict:
        """Populate the pg-backed corpus from the active vertical's connectors.
        No-op with a note if no NOESIS_CORPUS_DSN is configured (fixture corpus)."""
        if app.state.service is None:
            app.state.service = build_default_service()
        svc = app.state.service
        if not svc.connectors or not svc.corpus_source_key:
            return {"ingested": 0, "note": "no pg corpus configured — set NOESIS_CORPUS_DSN"}
        pg = svc.sources[svc.corpus_source_key]
        total = 0
        for conn in svc.connectors.values():
            total += await ingest_connector_to_postgres(
                conn, pg, tenant_id=tenant_id, embedder=svc.embedder)
        return {"ingested": total, "tenant_id": tenant_id}

    # The single-page app shell is a COMMITTED file that changes on every deploy. Serve it with
    # no-store so browsers always fetch the current build — otherwise a stale cached index.html keeps
    # running old front-end code and new features (flags/UI) never reach the user until a hard refresh.
    _NO_CACHE = {"Cache-Control": "no-cache, no-store, must-revalidate"}

    # PERF: the shell is ~220 KB and was shipped uncompressed on every load (~3 s). Pre-gzip the HTML
    # ONCE per process (files are baked into the image, immutable per deploy) and serve the compressed
    # bytes when the client accepts gzip. Deliberately NOT a blanket GZip middleware: compressing the
    # SSE streams would buffer keepalives and resurrect the edge-502 bug — only these two HTML routes.
    import gzip as _gzip
    _HTML_CACHE: dict[str, tuple[bytes, bytes]] = {}   # name -> (raw, gzipped)

    def _html_response(fname: str, accept_encoding: str):
        from fastapi.responses import Response
        if fname not in _HTML_CACHE:
            page = _WEB_DIR / fname
            raw = page.read_bytes() if page.exists() else b"<h1>Noesis</h1>"
            _HTML_CACHE[fname] = (raw, _gzip.compress(raw, 6))
        raw, gz = _HTML_CACHE[fname]
        if "gzip" in (accept_encoding or "").lower():
            return Response(gz, media_type="text/html",
                            headers={**_NO_CACHE, "Content-Encoding": "gzip", "Vary": "Accept-Encoding"})
        return Response(raw, media_type="text/html", headers=_NO_CACHE)

    @app.get("/", response_class=HTMLResponse)
    def index(accept_encoding: str = Header(default="")):
        return _html_response("index.html", accept_encoding)

    @app.get("/{name}.png")
    def web_png(name: str):
        """Serve a PNG asset from apps/web (logo, brand mark). Basename-only + .png
        guard → no path traversal; only files that exist in the web dir are served.
        Long-lived cache: the logos change ~never (and a stale logo is harmless)."""
        from fastapi.responses import FileResponse
        safe = os.path.basename(name) + ".png"
        f = _WEB_DIR / safe
        if not f.exists():
            raise HTTPException(status_code=404, detail="not found")
        return FileResponse(str(f), media_type="image/png",
                            headers={"Cache-Control": "public, max-age=604800"})

    @app.post("/research", response_model=ResearchOut)
    async def research(body: ResearchIn) -> ResearchOut:
        try:
            return await _do_research(body)
        except CassetteMiss as e:
            raise HTTPException(status_code=503, detail=(
                "No model available in replay mode. Set NOESIS_PROVIDER_MODE=live "
                "with ANTHROPIC_API_KEY + OPENAI_API_KEY to answer live, or record "
                "cassettes first.")) from e
        except Exception as e:   # provider errors (auth, credits, rate limit, timeout)
            raise HTTPException(status_code=502, detail=f"provider error: {e}") from e

    @app.post("/panel/plan")
    async def panel_plan(body: PanelIn) -> dict:
        """Phase 1 (Convene): auto-select the specialists for this case + return the full roster (each
        with its lens/expertise) so the UI can show the proposed panel and let the user adjust."""
        if not await _flag_live("ask_panel_enabled"):
            raise HTTPException(status_code=404, detail="ask panel not enabled")
        if app.state.service is None:
            app.state.service = build_default_service()
        try:
            return await app.state.service.plan_panel(question=body.question)
        except CassetteMiss as e:
            raise HTTPException(status_code=503, detail="No model available in replay mode.") from e
        except Exception as e:   # noqa: BLE001
            raise HTTPException(status_code=502, detail=f"provider error: {e}") from e

    def _with_urls(claims):
        """Attach the canonical source URL to each panel claim (same as the primary evidence panel) so
        the FE can render clickable links. claim dicts carry document_id + quote (from _vc_dict)."""
        ui = getattr(app.state.service, "ui", None)
        fn = getattr(ui, "source_url", None)
        out = []
        for c in (claims or []):
            u = None
            try:
                if fn and c.get("document_id"):
                    u = fn(c.get("document_id"), c.get("quote"))
            except Exception:   # noqa: BLE001
                u = None
            out.append({**c, "url": u})
        return out

    def _panel_payload(r, session_id=None) -> dict:
        return {
            "session_id": session_id,
            "question": r.question, "n_specialists": r.n_specialists,
            "takes": [{"id": t.id, "specialty": t.specialty, "answer": t.answer,
                       "grounded": t.grounded, "n_verified": t.n_verified, "error": t.error,
                       "rationale": getattr(t, "rationale", ""),
                       "claims": _with_urls(getattr(t, "claims", []))}
                      for t in r.takes],
            "synthesis": r.synthesis, "claims": _with_urls(r.claims),
            "interpretation": r.interpretation, "confidence": r.confidence,
            "reasoning_purpose": r.reasoning_purpose, "reasoning_conclusion": r.reasoning_conclusion,
        }

    def _panel_media(body):
        """Uploaded attachments → (images, documents, previews), gated by vision_enabled() — same as
        _do_research. Returns (None, None, []) when off or empty so the panel is byte-identical without vision."""
        if not (body.attachments and vision_enabled()):
            return None, None, []
        from api.media import attachments_to_media, session_previews
        images, docs, _notes = attachments_to_media([a.model_dump() for a in body.attachments])
        return images, docs, session_previews(images or [], docs or [])

    async def _persist_panel(body, r) -> str | None:
        """Best-effort persist of a panel turn as a SHAREABLE session (mirrors _do_research). A follow-up
        (session_id present) appends to the same thread; else a new row is created. kind='panel' so the
        reopen path renders the case conference. Never breaks the response."""
        store = _store()
        if store is None:
            return None
        payload = _panel_payload(r)
        pooled = payload["claims"]   # URL-enriched, so a reopened session keeps clickable links
        turn = {"kind": "panel", "question": r.question, "answer": r.synthesis,
                "grounded": bool(pooled), "claims": pooled, "takes": payload["takes"],
                "n_specialists": r.n_specialists, "interpretation": r.interpretation,
                "confidence": r.confidence, "reasoning_purpose": r.reasoning_purpose,
                "reasoning_conclusion": r.reasoning_conclusion}
        try:
            if body.session_id and await store.append_turn(body.session_id, turn):
                return body.session_id
            return await store.save(
                tenant_id=body.tenant_id, workspace_id=body.workspace_id,
                question=r.question, answer=r.synthesis, grounded=bool(pooled),
                claims=pooled, source_stats={}, coverage_gaps=[], rejected=0, sources=body.sources,
                interpretation=r.interpretation, confidence=r.confidence,
                reasoning_purpose=r.reasoning_purpose, reasoning_conclusion=r.reasoning_conclusion,
                kind="panel", extra={"takes": payload["takes"], "n_specialists": r.n_specialists})
        except Exception:   # noqa: BLE001 — persistence must never break the panel response
            return None

    @app.post("/panel/ask")
    async def panel_ask(body: PanelIn) -> dict:
        """Ask-Panel (Alpha): convene the selected AI specialists (or the default set) — each runs its
        own grounded, lens-scoped research — and return each specialist's take + the synthesized panel.
        NOTE: a full panel runs for several minutes; browsers should use /panel/ask/stream, which keeps
        the connection alive with SSE keepalives (a plain POST this long is cut by the edge proxy → 502)."""
        if not await _flag_live("ask_panel_enabled"):
            raise HTTPException(status_code=404, detail="ask panel not enabled")
        if app.state.service is None:
            app.state.service = build_default_service()
        images, docs, _prev = _panel_media(body)
        try:
            r = await app.state.service.ask_panel(
                question=body.question, tenant_id=body.tenant_id, workspace_id=body.workspace_id,
                specialist_ids=body.specialists or None, source_keys=body.sources, history=body.history,
                rationales=body.rationales, images=images, documents=docs)
        except CassetteMiss as e:
            raise HTTPException(status_code=503, detail="No model available in replay mode.") from e
        except Exception as e:   # noqa: BLE001
            raise HTTPException(status_code=502, detail=f"provider error: {e}") from e
        sid = await _persist_panel(body, r)
        return _panel_payload(r, session_id=sid or body.session_id)

    @app.post("/panel/ask/stream")
    async def panel_ask_stream(body: PanelIn):
        """Live SSE for a panel run: emits specialist_start / specialist_done progress as each lens runs,
        then a `final` event carrying the full panel payload. The keepalive `: ping` comments keep the
        edge proxy from cutting the (multi-minute) connection — the fix for the plain-POST 502."""
        if not await _flag_live("ask_panel_enabled"):
            raise HTTPException(status_code=404, detail="ask panel not enabled")
        if app.state.service is None:
            app.state.service = build_default_service()
        from fastapi.responses import StreamingResponse
        run = _sse_run_new()

        async def on_event(ev: dict) -> None:
            _sse_push(run, ev)

        images, docs, _prev = _panel_media(body)

        async def runner() -> None:
            # Runs to completion regardless of client connections — persists, and buffers every
            # event under the run_id so a cut connection resumes via GET /stream/{run_id}.
            try:
                r = await app.state.service.ask_panel(
                    question=body.question, tenant_id=body.tenant_id, workspace_id=body.workspace_id,
                    specialist_ids=body.specialists or None, source_keys=body.sources,
                    history=body.history, rationales=body.rationales,
                    images=images, documents=docs, on_event=on_event)
                sid = await _persist_panel(body, r)
                _sse_push(run, {"type": "final", "result": _panel_payload(r, session_id=sid or body.session_id)})
            except CassetteMiss:
                _sse_push(run, {"type": "error", "detail": "No model available in replay mode."})
            except Exception as e:   # noqa: BLE001
                _sse_push(run, {"type": "error", "detail": f"provider error: {e}"})
            finally:
                _sse_done(run)

        run["task"] = asyncio.create_task(runner())

        async def gen():
            yield ": open\n\n"                            # flush headers immediately
            yield f"data: {json.dumps({'type': 'run', 'run_id': run['id']})}\n\n"
            async for chunk in _sse_follow(run, 0):
                yield chunk

        return StreamingResponse(gen(), media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no", "Connection": "keep-alive"})

    async def _do_research(body: ResearchIn, on_event=None) -> ResearchOut:
        """Shared research core: attachments → ask (optional live on_event) → persist → ResearchOut.
        Raises CassetteMiss / provider errors for the caller to handle."""
        if app.state.service is None:
            app.state.service = build_default_service()
        images, docs, attach_notes, previews = None, None, [], []
        if body.attachments and vision_enabled():
            from api.media import attachments_to_media, session_previews
            images, docs, attach_notes = attachments_to_media(
                [a.model_dump() for a in body.attachments])
            previews = session_previews(images or [], docs or [])
        history = body.history if conversation_enabled() else None
        # Effort is HONORED only when the flag is on; otherwise forced to 1.0 (byte-identical no-op).
        effort = body.effort if effort_scale_enabled() else 1.0
        # Audience is HONORED only when the flag is on; otherwise forced 'clinician' (byte-identical).
        audience = _resolve_audience(body.audience)
        if on_event is not None and effort > 1.0:
            await on_event({"type": "effort", "effort": effort})
        if on_event is not None and audience == "patient":
            await on_event({"type": "audience", "audience": audience})
        # Answer-focus: condense elliptical follow-ups + answer-scope compose (needs the flag; the
        # condense half additionally needs conversation history, which `history` above already gates).
        focus = answer_focus_enabled()
        # A/B duel arm: engine="reasoned" routes through the alternate scaffold+decision-gated engine.
        # Flag off (or unknown engine) → plain ask, param ignored (byte-identical, Rule 20).
        # Engine resolution — explicit values (duel arms + interlock hop chips) force a pipeline;
        # UNSET + dynamic-selection on → the scaffold call routes per question kind.
        import functools as _ft
        _eng = (body.engine or "").strip()
        _dyn = await _flag_live("reasoned_default_enabled")
        if _eng == "standard":
            _ask = app.state.service.ask
        elif _eng == "understanding" and _dyn:
            _ask = _ft.partial(app.state.service.ask_reasoned, route=False, force_kind="understanding")
        elif _eng == "reasoned" and (_dyn or await _flag_live("duel_enabled")):
            _ask = _ft.partial(app.state.service.ask_reasoned, route=False)
        elif not _eng and _dyn:
            _ask = app.state.service.ask_reasoned          # auto: the question picks the engine
        else:
            _ask = app.state.service.ask
        # per-question integrative opt-in (double opt-in: live flag AND body.integrative). Steers the
        # search (question hint) + appends the section directive; persisted question stays the original.
        _q, _extra = body.question, None
        if body.integrative and await _flag_live("integrative_enabled"):
            svc_ = app.state.service
            _extra = getattr(svc_, "integrative_prompt", None)
            hint = getattr(svc_, "integrative_query_hint", None)
            if hint:
                _q = body.question + "\n\n[" + hint + "]"
        res = await _ask(
            question=_q, tenant_id=body.tenant_id,
            workspace_id=body.workspace_id, source_keys=body.sources,
            images=images, documents=docs, history=history, on_event=on_event,
            facets=_country_facets(body.countries), country_boost=_country_boost(body.countries),
            effort=effort, audience=audience,
            answer_focus=focus, clarify=followup_clarify_enabled(), extra_directive=_extra)
        # Ambiguous follow-up → return the clarifying question; no research ran, nothing to persist.
        if getattr(res, "clarification", ""):
            return ResearchOut(grounded=False, answer="", claims=[], coverage_gaps=[], rejected=0,
                               clarification=res.clarification)
        ui = getattr(app.state.service, "ui", None)
        def _url(c):
            fn = getattr(ui, "source_url", None)
            try:
                return fn(c.document_id, c.quote) if fn and c.document_id else None
            except Exception:
                return None
        claims = [Citation(text=c.text, quote=c.quote, atom_id=c.atom_id,
                           source=c.source_key, title=c.document_title,
                           url=_url(c), document_id=c.document_id)
                  for c in res.verified_claims]
        # Persist the Q&A (best-effort). Conversation follow-up (session_id + flag) APPENDS a turn.
        session_id = None
        store = _store()
        claim_dicts = [c.model_dump() for c in claims]
        if store is not None:
            turn = {"question": body.question, "answer": res.composed_answer,
                    "grounded": res.grounded, "claims": claim_dicts,
                    "source_stats": res.source_stats, "coverage_gaps": res.coverage_gaps,
                    "rejected": len(res.rejected_claims),
                    "visual_observation": res.visual_observation, "attachments": previews}
            if effort_scale_enabled():
                turn["effort"] = res.effort    # per-turn badge on the session (JSONB, no migration)
            if patient_mode_enabled():
                turn["audience"] = audience    # per-turn audience tag (only under the flag)
            if answer_charts_enabled() and getattr(res, "charts", None):
                turn["charts"] = res.charts    # persist grounded charts so a reopened session shows them
            if reasoning_read_enabled():
                if getattr(res, "interpretation", None):
                    turn["interpretation"] = res.interpretation   # persist the reasoning layer (JSONB)
                if getattr(res, "confidence", None):
                    turn["confidence"] = res.confidence
                if getattr(res, "reasoning_purpose", ""):
                    turn["reasoning_purpose"] = res.reasoning_purpose
                if getattr(res, "reasoning_conclusion", ""):
                    turn["reasoning_conclusion"] = res.reasoning_conclusion
            if diag_trace_enabled() and getattr(res, "diagnostics", None):
                turn["diagnostics"] = res.diagnostics   # persist the trace for later troubleshooting
            try:
                # Audience-guarded append: only continue a thread whose audience MATCHES this turn's
                # (mid-thread toggle → mismatch → save a fresh session instead of corrupting the thread).
                if conversation_enabled() and body.session_id and \
                        await store.append_turn(body.session_id, turn, audience=audience):
                    session_id = body.session_id
                else:
                    session_id = await store.save(
                        tenant_id=body.tenant_id, workspace_id=body.workspace_id,
                        question=body.question, answer=res.composed_answer,
                        grounded=res.grounded, claims=claim_dicts,
                        source_stats=res.source_stats, coverage_gaps=res.coverage_gaps,
                        rejected=len(res.rejected_claims), sources=body.sources,
                        user_name=body.user_name, user_email=body.user_email,
                        visual_observation=res.visual_observation, attachments=previews,
                        audience=audience,
                        charts=(res.charts if answer_charts_enabled() else None),
                        interpretation=(getattr(res, "interpretation", None) if reasoning_read_enabled() else None),
                        confidence=(getattr(res, "confidence", None) if reasoning_read_enabled() else None),
                        reasoning_purpose=(getattr(res, "reasoning_purpose", "") if reasoning_read_enabled() else ""),
                        reasoning_conclusion=(getattr(res, "reasoning_conclusion", "") if reasoning_read_enabled() else ""),
                        diagnostics=(getattr(res, "diagnostics", None) if diag_trace_enabled() else None))
            except Exception:
                session_id = None
        return ResearchOut(
            grounded=res.grounded, answer=res.composed_answer, claims=claims,
            coverage_gaps=res.coverage_gaps, rejected=len(res.rejected_claims),
            source_stats=res.source_stats, session_id=session_id,
            stopped_reason=res.stopped_reason, atoms_gathered=res.atoms_gathered,
            retried_empty=res.retried_empty, visual_observation=res.visual_observation,
            attachment_notes=attach_notes,
            effort=res.effort if effort_scale_enabled() else None,
            audience=audience if patient_mode_enabled() else None,
            resolved_question=(res.resolved_question or None) if answer_focus_enabled() else None,
            derived_from_prior=bool(getattr(res, "derived_from_prior", False)),
            charts=(getattr(res, "charts", []) or []) if answer_charts_enabled() else [],
            interpretation=(getattr(res, "interpretation", []) or []) if reasoning_read_enabled() else [],
            confidence=(getattr(res, "confidence", None) if reasoning_read_enabled() else None),
            reasoning_purpose=(getattr(res, "reasoning_purpose", "") if reasoning_read_enabled() else ""),
            reasoning_conclusion=(getattr(res, "reasoning_conclusion", "") if reasoning_read_enabled() else ""),
            diagnostics=(getattr(res, "diagnostics", None) if diag_trace_enabled() else None),
        )

    @app.post("/research/stream")
    async def research_stream(body: ResearchIn):
        """Live SSE progress for a research request: emits step/search/found/verifying/composing
        events as the ReAct loop runs, then a `final` event carrying the full ResearchOut. Progress
        events are read-only (never unverified claims); persistence + the final payload happen once
        at the end, exactly like /research."""
        if not stream_enabled():
            raise HTTPException(status_code=404, detail="streaming not enabled")
        from fastapi.responses import StreamingResponse
        run = _sse_run_new()

        async def on_event(ev: dict) -> None:
            _sse_push(run, ev)

        async def runner() -> None:
            # Runs to completion regardless of client connections — the session PERSISTS server-side,
            # and every event lands in the run buffer for any number of (re)connecting readers.
            try:
                out = await _do_research(body, on_event=on_event)
                _sse_push(run, {"type": "final", "result": out.model_dump()})
            except CassetteMiss:
                _sse_push(run, {"type": "error", "detail": "No model available in replay mode."})
            except Exception as e:   # noqa: BLE001
                _sse_push(run, {"type": "error", "detail": f"provider error: {e}"})
            finally:
                _sse_done(run)

        run["task"] = asyncio.create_task(runner())

        async def gen():
            yield ": open\n\n"                            # flush headers immediately
            yield f"data: {json.dumps({'type': 'run', 'run_id': run['id']})}\n\n"
            async for chunk in _sse_follow(run, 0):
                yield chunk

        return StreamingResponse(gen(), media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no", "Connection": "keep-alive"})

    @app.get("/stream/{run_id}")
    async def stream_resume(run_id: str, since: int = 0):
        """Resume a live or recently-finished streaming run (research, panel, or stream-test) from
        event cursor `since` — the FE's silent-reconnect path for when the edge cuts an SSE
        connection mid-run. 404 = this replica never saw the run (or it expired); the FE retries
        (re-rolling the replica) and falls back to /sessions polling."""
        run = _SSE_RUNS.get(run_id)
        if run is None:
            raise HTTPException(status_code=404, detail="unknown run")
        from fastapi.responses import StreamingResponse

        async def gen():
            yield ": open\n\n"
            async for chunk in _sse_follow(run, since):
                yield chunk

        return StreamingResponse(gen(), media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no", "Connection": "keep-alive"})

    @app.post("/explain")
    async def explain(body: ExplainIn) -> dict:
        """On-demand plain-language re-explanation of a grounded answer (same doctor →
        patient). Saved on the session when a session_id is given."""
        if app.state.service is None:
            app.state.service = build_default_service()
        svc = app.state.service
        if not getattr(svc, "layman_prompt", None):
            raise HTTPException(status_code=404, detail="plain-language explanation not available")
        try:
            text = await svc.explain(question=body.question, answer=body.answer)
        except CassetteMiss as e:
            raise HTTPException(status_code=503, detail="No model available in replay mode.") from e
        except Exception as e:
            raise HTTPException(status_code=502, detail=f"provider error: {e}") from e
        if body.session_id and text:
            store = _store()
            if store is not None:
                try:
                    await store.save_layman(body.session_id, text)
                except Exception:
                    pass
        return {"explanation": text}

    @app.post("/suggest")
    async def suggest(body: SuggestIn) -> dict:
        """On-demand suggested follow-up questions for deeper discovery (conversation feature).
        Called after an answer renders, so it never adds latency to the answer itself."""
        if not conversation_enabled():
            raise HTTPException(status_code=404, detail="suggestions not enabled")
        if app.state.service is None:
            app.state.service = build_default_service()
        svc = app.state.service
        if not getattr(svc, "suggest_prompt", None):
            raise HTTPException(status_code=404, detail="suggestions not available for this vertical")
        hist = ""
        if body.history:
            hist = "\n\n".join(
                f"Q: {(t.get('question') or '').strip()}" for t in body.history if t.get("question"))
        try:
            qs = await svc.suggest(question=body.question, answer=body.answer, history=hist)
        except CassetteMiss as e:
            raise HTTPException(status_code=503, detail="No model available in replay mode.") from e
        except Exception as e:
            raise HTTPException(status_code=502, detail=f"provider error: {e}") from e
        return {"suggestions": qs}

    @app.post("/refine")
    async def refine(body: RefineIn) -> dict:
        """Pre-answer question refinement: propose a few distinct sharper standalone questions to pick
        from. Returns {"refinements": []} when the question is already precise (so the FE just answers
        it), when the flag/vertical is off, or on any provider error — never a dead-end."""
        if not refine_enabled():
            return {"refinements": []}
        if app.state.service is None:
            app.state.service = build_default_service()
        svc = app.state.service
        if not getattr(svc, "refine_prompt", None):
            return {"refinements": []}
        try:
            opts = await svc.refine(question=body.question)
        except CassetteMiss:
            return {"refinements": []}     # replay mode → no refinement, answer the original
        except Exception:                  # provider error → fail open (answer the original)
            return {"refinements": []}
        return {"refinements": opts}

    @app.post("/triage/step")
    async def triage_step(body: TriageIn) -> dict:
        """Guided-intake / triage: one clarifying turn. Given the running transcript, return either the
        next clarifying question (status="ask") or a crisp refined question + recommended route
        (status="qa"|"panel", via `recommended_mode`) when ready. Stateless — the FE holds the transcript.
        404 when the flag/vertical is off. Never answers the medical question; only narrows + routes.

        Convergence is code-guaranteed: once the assistant has already asked TRIAGE_MAX_ASK questions,
        this turn is FORCED to route (the LLM still owns whether/what to ask below that cap — Rule 18)."""
        if not await _flag_live("triage_enabled"):
            raise HTTPException(status_code=404, detail="triage mode is not enabled")
        if app.state.service is None:
            app.state.service = build_default_service()
        svc = app.state.service
        if not getattr(svc, "triage_prompt", None):
            raise HTTPException(status_code=404, detail="triage mode is not enabled")
        transcript = [t for t in (body.transcript or []) if isinstance(t, dict) and (t.get("text") or "").strip()]
        if not transcript:
            raise HTTPException(status_code=400, detail="transcript is empty")
        asked = sum(1 for t in transcript if (t.get("role") or "") == "assistant")
        force_ready = asked >= TRIAGE_MAX_ASK
        try:
            return await svc.triage(transcript=transcript, force_ready=force_ready)
        except CassetteMiss:
            # replay mode → route the last user message straight to Q&A (never dead-end)
            last = next((t["text"] for t in reversed(transcript) if t.get("role") == "user"), "")
            return {"status": "ready", "recommended_mode": "qa", "refined_question": last,
                    "understood_problem": last, "message": "Searching that now.", "safety": "ok"}
        except Exception as e:   # noqa: BLE001 — never dead-end the user
            raise HTTPException(status_code=502, detail=f"triage error: {e}") from e

    @app.post("/corpus/gap-plan")
    async def corpus_gap_plan(body: GapPlanIn) -> dict:
        """On-demand: what to ADD to the corpus so an under-evidenced question could be answered.
        LLM-proposed ingest jobs (over this deployment's connectors) + gold-source recommendations.
        Read-only — proposes; it does not queue or ingest anything."""
        if not gap_healing_enabled():
            raise HTTPException(status_code=404, detail="gap healing not enabled")
        if app.state.service is None:
            app.state.service = build_default_service()
        svc = app.state.service
        try:
            plan = await svc.plan_gaps(
                question=body.question, answer=body.answer, coverage_gaps=body.coverage_gaps)
        except CassetteMiss as e:
            raise HTTPException(status_code=503, detail="No model available in replay mode.") from e
        except Exception as e:
            raise HTTPException(status_code=502, detail=f"provider error: {e}") from e
        if plan is None:
            raise HTTPException(status_code=404, detail="gap healing not available for this vertical")
        return {
            "summary": plan.summary,
            "jobs": [j.model_dump() for j in plan.jobs],
            "recommendations": [r.model_dump() for r in plan.recommendations],
            "connectors": list(svc.connectors.keys()),
        }

    @app.post("/corpus/queue")
    async def corpus_queue_add(body: GapQueueIn) -> dict:
        """Queue user-approved gap-fill jobs. Validates every job against the real connector set
        and caps the limit (code owns structure) before persisting for the background processor."""
        if not gap_healing_enabled():
            raise HTTPException(status_code=404, detail="gap healing not enabled")
        q = _gap_queue()
        if q is None:
            raise HTTPException(status_code=404, detail="no corpus queue configured")
        if app.state.service is None:
            app.state.service = build_default_service()
        allowed = set(app.state.service.connectors.keys())
        clean = []
        for j in body.jobs or []:
            c = (j.get("connector") or "").strip()
            query = (j.get("query") or "").strip()
            if c not in allowed or not query:
                continue
            clean.append({
                "connector": c, "query": query,
                "limit": max(1, min(int(j.get("limit") or 200), 400)),
                "kind": (j.get("kind") or "")[:80],
                "rationale": (j.get("rationale") or "")[:400],
                "quality": (j.get("quality") or "")[:120],
            })
        if not clean:
            raise HTTPException(status_code=400, detail="no valid jobs (unknown connector or empty query)")
        try:
            ids = await q.enqueue(tenant_id=body.tenant_id, question=body.question, jobs=clean)
        except Exception as e:
            raise HTTPException(status_code=502, detail=f"queue error: {e}") from e
        return {"queued": len(ids), "ids": ids}

    @app.get("/corpus/queue")
    async def corpus_queue_status(limit: int = 50) -> dict:
        """Gap-fill queue status (pending/running/done/failed + blocks added) — self-healing progress."""
        q = _gap_queue()
        if q is None:
            return {"enabled": gap_healing_enabled(), "jobs": [], "summary": {}}
        try:
            return {"enabled": True, "jobs": await q.list(limit=min(limit, 200)),
                    "summary": await q.summary()}
        except Exception as e:
            raise HTTPException(status_code=502, detail=f"queue error: {e}") from e

    @app.post("/admin/corpus/ingest")
    async def admin_corpus_ingest(body: CorpusIngestIn, x_admin_token: str = Header(default="")) -> dict:
        """Bulk prod-direct ingest — replaces 'download locally + push to prod'. Expands conditions
        into clinicaltrials + europepmc jobs (and FAERS drugs into adverse-event jobs), validates
        against the real connector set, and enqueues them for the prod processor. Guarded by
        NOESIS_ADMIN_TOKEN when set (this endpoint spends credits + mutates the corpus)."""
        if not gap_healing_enabled():
            raise HTTPException(status_code=404, detail="corpus ingestion not enabled")
        want = os.environ.get("NOESIS_ADMIN_TOKEN", "")
        if want and x_admin_token != want:
            raise HTTPException(status_code=401, detail="admin token required")
        q = _gap_queue()
        if q is None:
            raise HTTPException(status_code=404, detail="no corpus queue configured")
        if app.state.service is None:
            app.state.service = build_default_service()
        allowed = set(app.state.service.connectors.keys())
        cap = lambda n, d: max(1, min(int(n or d), 400))
        jobs: list[dict] = []
        for cond in body.conditions:
            c = (cond or "").strip()
            if not c:
                continue
            if "clinicaltrials" in allowed:
                jobs.append({"connector": "clinicaltrials", "query": c, "limit": cap(body.trials, 300),
                             "kind": "trials", "quality": "batch"})
            if "europepmc" in allowed:
                jobs.append({"connector": "europepmc", "query": c, "limit": cap(body.papers, 150),
                             "kind": "literature", "quality": "batch"})
        for drug in body.faers_drugs:
            d = (drug or "").strip()
            if d and "faers" in allowed:
                jobs.append({"connector": "faers", "query": d, "limit": 200,
                             "kind": "adverse events", "quality": "batch"})
        for j in body.jobs or []:
            c = (j.get("connector") or "").strip()
            query = (j.get("query") or "").strip()
            if c in allowed and query:
                jobs.append({"connector": c, "query": query, "limit": cap(j.get("limit"), 200),
                             "kind": (j.get("kind") or "")[:80], "quality": (j.get("quality") or "")[:120]})
        if not jobs:
            raise HTTPException(status_code=400, detail="no valid jobs (unknown connector or empty inputs)")
        # a batch-level source_country stamps every job's blocks (per-job override wins if given)
        sc = (body.source_country or "").strip()
        if sc:
            for jb in jobs:
                jb.setdefault("source_country", sc)
        try:
            ids = await q.enqueue(tenant_id="demo", question="admin bulk ingest", jobs=jobs)
        except Exception as e:
            raise HTTPException(status_code=502, detail=f"queue error: {e}") from e
        return {"queued": len(ids), "jobs": len(jobs)}

    # ---- Evidence Pulse P0 admin surface (spec A4/A5): scan · list · approve/retract -----------
    def _pulse_admin_gate(x_admin_token: str):
        cur = _currency()
        if cur is None:
            raise HTTPException(status_code=404, detail="pulse not enabled")
        want = os.environ.get("NOESIS_ADMIN_TOKEN", "")
        if want and x_admin_token != want:
            raise HTTPException(status_code=401, detail="admin token required")
        return cur

    @app.post("/admin/pulse/scan")
    async def admin_pulse_scan(x_admin_token: str = Header(default="")) -> dict:
        """Sweep curator-declared lineage into the ledger (declared = high-confidence → approved,
        A4) and (re-)apply all approved stamps. Idempotent — this is ALSO the manual re-stamp job
        to run after any re-ingest (facet overwrite erases stamps; the ledger restores them)."""
        cur = _pulse_admin_gate(x_admin_token)
        manifest = load_active_vertical()
        try:
            return await cur.sweep_declared(list(getattr(manifest, "lineage", ()) or ()))
        except Exception as e:   # noqa: BLE001
            raise HTTPException(status_code=502, detail=f"pulse scan failed: {e}") from e

    @app.post("/admin/pulse/retraction-scan")
    async def admin_pulse_retraction_scan(x_admin_token: str = Header(default="")) -> dict:
        """Start a BACKGROUND sweep of the corpus's Europe PMC holdings against publisher-declared
        retractions (P1's first real detector — structural, zero-LLM). Backgrounded because ~25
        batched API calls outlive the edge's request window (a synchronous scan gets its response
        cut). Poll GET /admin/pulse/retraction-scan for the result; retracted papers get
        auto-approved `retracted` events (publisher fact = high confidence, A4) and their blocks
        are excluded from grounding."""
        cur = _pulse_admin_gate(x_admin_token)
        state = await cur.get_state("retraction_scan")
        if state and state.get("status") == "running":
            return {"status": "already_running", "started_at": state.get("started_at")}
        import datetime as _dt
        await cur.set_state("retraction_scan", {"status": "running",
                            "started_at": _dt.datetime.utcnow().isoformat() + "Z"})

        async def _run():
            from noesis_vertical_medical.retractions import retraction_lineage
            try:
                doc_ids = await cur.list_document_ids(prefix="europepmc:")
                relations = await retraction_lineage(doc_ids)
                result = await cur.sweep_declared(relations)
                await cur.set_state("retraction_scan", {"status": "done",
                                    "checked": len(doc_ids),
                                    "retracted_found": len(relations), **result,
                                    "finished_at": _dt.datetime.utcnow().isoformat() + "Z"})
            except Exception as e:   # noqa: BLE001
                await cur.set_state("retraction_scan", {"status": "failed", "error": str(e)[:300]})

        app.state.pulse_scan_task = asyncio.create_task(_run())   # ref kept → not GC'd
        return {"status": "started"}

    @app.get("/admin/pulse/retraction-scan")
    async def admin_pulse_retraction_status(x_admin_token: str = Header(default="")) -> dict:
        """Status/result of the latest retraction sweep — DB-backed (replica-safe)."""
        cur = _pulse_admin_gate(x_admin_token)
        return (await cur.get_state("retraction_scan")) or {"status": "never_run"}

    @app.post("/admin/pulse/detect")
    async def admin_pulse_detect(x_admin_token: str = Header(default="")) -> dict:
        """SHADOW-MODE supersession detection (spec 3.2, approval-gated per A4): structural
        candidate pairs (same issuer + overlapping subjects + different years, versioned-document
        tier) → LLM judge → SHADOW events only. Nothing stamps or notifies until a human approves
        via /admin/pulse/event. Background task; status in /admin/pulse/detect (GET)."""
        cur = _pulse_admin_gate(x_admin_token)
        prompt = getattr(load_active_vertical(), "supersession_judge_prompt", None)
        if not prompt:
            raise HTTPException(status_code=404, detail="no supersession judge for this vertical")
        state = await cur.get_state("detect_scan")
        if state and state.get("status") == "running":
            return {"status": "already_running", "started_at": state.get("started_at")}
        import datetime as _dt
        await cur.set_state("detect_scan", {"status": "running",
                            "started_at": _dt.datetime.utcnow().isoformat() + "Z"})
        if app.state.service is None:
            app.state.service = build_default_service()
        svc = app.state.service

        async def _run():
            from noesis_kernel.currency.candidates import edition_candidates
            try:
                docs = await cur.list_documents_meta(
                    facet_key="pub_type", facet_values=("guideline", "practice guideline"))
                decided = {(e["old_document_id"], e["new_document_id"])
                           for e in await cur.list_events(limit=500)}
                pairs = edition_candidates(docs, exclude_pairs=decided)
                registry = await _topic_registry(cur)

                class _Verdict(BaseModel):
                    supersedes: bool = False
                    materiality: str = "minor"
                    subjects: list[str] = []
                shadowed = 0
                for old, new in pairs:
                    comp = await svc.llm.complete(
                        system=prompt + _registry_block(registry),
                        messages=[{"role": "user", "content":
                                   f"OLDER: {old['title']} (issuer {old['issuer']}, {old['year']}; "
                                   f"subjects: {', '.join(old['conditions'][:8])})\n"
                                   f"NEWER: {new['title']} (issuer {new['issuer']}, {new['year']}; "
                                   f"subjects: {', '.join(new['conditions'][:8])})"}],
                        response_format=_Verdict, max_tokens=200)
                    v = comp.parsed
                    if v.supersedes:
                        subs = await cur.ensure_topics([s for s in (v.subjects or []) if s][:5])
                        await cur.record(relation="superseded_by",
                                         old_document_id=old["document_id"],
                                         new_document_id=new["document_id"],
                                         subjects=subs,
                                         materiality=("major" if v.materiality == "major" else "minor"),
                                         confidence="judge", status="shadow")
                        shadowed += 1
                await cur.set_state("detect_scan", {"status": "done", "candidates": len(pairs),
                                    "shadow_events": shadowed,
                                    "finished_at": _dt.datetime.utcnow().isoformat() + "Z"})
            except Exception as e:   # noqa: BLE001
                await cur.set_state("detect_scan", {"status": "failed", "error": str(e)[:300]})

        app.state.pulse_detect_task = asyncio.create_task(_run())
        return {"status": "started"}

    @app.get("/admin/pulse/detect")
    async def admin_pulse_detect_status(x_admin_token: str = Header(default="")) -> dict:
        cur = _pulse_admin_gate(x_admin_token)
        return (await cur.get_state("detect_scan")) or {"status": "never_run"}

    @app.get("/pulse/recent")
    async def pulse_recent(limit: int = 20) -> dict:
        """PUBLIC what-changed feed (spec C3): recent approved change events — the visible proof
        the corpus stays current. No auth; approved events only; audit metadata redacted."""
        cur = _currency()
        if cur is None:
            raise HTTPException(status_code=404, detail="pulse not enabled")
        try:
            events = await cur.list_events(status="approved", limit=min(limit, 50))
        except Exception as e:   # noqa: BLE001
            raise HTTPException(status_code=502, detail=f"pulse feed failed: {e}") from e
        return {"events": [{k: e[k] for k in
                            ("relation", "old_document_id", "new_document_id", "subjects",
                             "materiality", "brief_md", "created_at")} for e in events]}

    @app.get("/admin/pulse/events")
    async def admin_pulse_events(status: str | None = None, limit: int = 100,
                                 x_admin_token: str = Header(default="")) -> dict:
        """The auditable change ledger — every relation, its status, and when it was recorded."""
        cur = _pulse_admin_gate(x_admin_token)
        try:
            return {"events": await cur.list_events(status=status, limit=limit)}
        except Exception as e:   # noqa: BLE001
            raise HTTPException(status_code=502, detail=f"pulse list failed: {e}") from e

    @app.post("/admin/pulse/event")
    async def admin_pulse_event(body: PulseEventIn, x_admin_token: str = Header(default="")) -> dict:
        """Approve (stamps applied) or retract (stamps removed, event kept for audit) one event —
        the panel-required one-click reversal path for a wrong supersession."""
        cur = _pulse_admin_gate(x_admin_token)
        status = {"approve": "approved", "retract": "retracted_event"}.get(body.action)
        if status is None:
            raise HTTPException(status_code=400, detail="action must be approve|retract")
        try:
            ok = await cur.set_status(body.event_id, status)
        except Exception as e:   # noqa: BLE001
            raise HTTPException(status_code=502, detail=f"pulse action failed: {e}") from e
        if not ok:
            raise HTTPException(status_code=404, detail="unknown event")
        return {"event_id": body.event_id, "status": status}

    @app.post("/auth/register")
    async def auth_register(body: RegisterIn) -> dict:
        """Adoption P0: register (or re-register) a user for the free verified-clinician tier.
        Upsert-on-email; returns the bearer token ONCE (the FE stores it and sends it with feedback).
        NPI (optional, US) is verified structurally against the public CMS registry. 404 when off."""
        if not accounts_enabled():
            raise HTTPException(status_code=404, detail="accounts are not enabled")
        store = _accounts()
        if store is None:
            raise HTTPException(status_code=503, detail="no account store configured (NOESIS_CORPUS_DSN)")
        if not re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", body.email or ""):
            raise HTTPException(status_code=400, detail="invalid email")
        if len((body.name or "").strip()) < 2:
            raise HTTPException(status_code=400, detail="name required")
        npi_ok = False
        if body.npi.strip():
            from api.accounts import verify_npi
            npi_ok = await verify_npi(body.npi)
        try:
            user, token = await store.register(
                email=body.email, name=body.name, profession=body.profession[:80],
                country=body.country[:40], npi=body.npi.strip()[:16], npi_verified=npi_ok,
                disclaimer_ack=body.disclaimer_ack)
        except Exception as e:
            raise HTTPException(status_code=502, detail=f"registration failed: {e}") from e
        return {"user": user, "token": token}

    @app.post("/feedback")
    async def post_feedback(body: FeedbackIn, x_noesis_token: str = Header(default="")) -> dict:
        """Per-answer user feedback keyed to the W1–W9 warrant taxonomy (the same codes the eval and
        auditor use — one contract, three uses). Requires a registered token so feedback is
        attributable; modes are whitelisted structurally. 404 when accounts are off."""
        if not accounts_enabled():
            raise HTTPException(status_code=404, detail="accounts are not enabled")
        store = _accounts()
        if store is None:
            raise HTTPException(status_code=503, detail="no account store configured")
        user = await store.user_by_token(x_noesis_token)
        if user is None:
            raise HTTPException(status_code=401, detail="register to give feedback")
        if body.verdict not in ("up", "down", "flag"):
            raise HTTPException(status_code=400, detail="verdict must be up|down|flag")
        # W1–W9 = warrant taxonomy; U1 (unclear/ambiguous) + U2 (misunderstood question) = UX root causes
        modes = [m for m in body.modes if m in ({f"W{i}" for i in range(1, 10)} | {"U1", "U2"})]
        try:
            fid = await store.add_feedback(
                user=user, session_id=body.session_id, turn_index=max(0, body.turn_index),
                verdict=body.verdict, modes=modes, claim_index=body.claim_index,
                note=body.note, question=body.question)
        except Exception as e:
            raise HTTPException(status_code=502, detail=f"feedback failed: {e}") from e
        return {"ok": True, "id": fid}

    def _admin_ui_pw() -> str:
        # UI panel password (user-chosen; default per request). ALPHA-grade gate for non-destructive
        # product toggles only — change via NOESIS_ADMIN_UI_PASSWORD; never gate data access with this.
        return os.environ.get("NOESIS_ADMIN_UI_PASSWORD", "1111")

    async def _settings_payload() -> dict:
        st = _settings()
        over = {}
        if st is not None:
            try:
                over = await st.all(fresh=True)
            except Exception:   # noqa: BLE001
                over = {}
        from api.settings import SettingStore
        return {"store": st is not None, "settings": {
            k: {"override": over.get(k, ""), "env_default": fn(),
                "resolved": SettingStore.resolve_flag(over.get(k, ""), fn())}
            for k, fn in _LIVE_FLAGS.items()}}

    # ---- Evidence Pulse P1 user surface: watches + inbox ---------------------------------------
    async def _pulse_user(x_noesis_token: str):
        cur = _currency()
        if cur is None:
            raise HTTPException(status_code=404, detail="pulse not enabled")
        store = _accounts()
        if store is None:
            raise HTTPException(status_code=503, detail="no account store configured")
        user = await store.user_by_token(x_noesis_token)
        if user is None:
            raise HTTPException(status_code=401, detail="sign in to use watches")
        return cur, user

    @app.post("/pulse/watch")
    async def pulse_watch_add(body: WatchIn, x_noesis_token: str = Header(default="")) -> dict:
        """Watch a topic. FREE-TEXT topics are canonicalized against the stable registry first
        ("afib" → "atrial fibrillation") so watches actually match event subjects; topics chosen
        from the suggested chips are already canonical and skip the call. Fails open to raw text."""
        cur, user = await _pulse_user(x_noesis_token)
        topic = (body.topic or "").strip()
        if body.source == "manual" and topic:
            canon_prompt = getattr(load_active_vertical(), "watch_canonize_prompt", None)
            if canon_prompt:
                try:
                    if app.state.service is None:
                        app.state.service = build_default_service()

                    class _Canon(BaseModel):
                        topic: str = ""
                    registry = await _topic_registry(cur)
                    comp = await app.state.service.llm.complete(
                        system=canon_prompt + _registry_block(registry),
                        messages=[{"role": "user", "content": topic[:200]}],
                        response_format=_Canon, max_tokens=60)
                    canon = (comp.parsed.topic or "").strip()
                    if canon:
                        topic = (await cur.ensure_topics([canon]))[0]
                except Exception:   # noqa: BLE001 — canonicalization is an enhancer; raw text stands
                    pass
        try:
            await cur.add_watch(user_id=user["id"], topic=topic, source=body.source or "manual")
            return {"watches": await cur.list_watches(user_id=user["id"]), "stored_as": topic}
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e)) from e
        except Exception as e:   # noqa: BLE001
            raise HTTPException(status_code=502, detail=f"watch failed: {e}") from e

    @app.delete("/pulse/watch")
    async def pulse_watch_remove(topic: str, x_noesis_token: str = Header(default="")) -> dict:
        cur, user = await _pulse_user(x_noesis_token)
        try:
            await cur.remove_watch(user_id=user["id"], topic=topic)
            return {"watches": await cur.list_watches(user_id=user["id"])}
        except Exception as e:   # noqa: BLE001
            raise HTTPException(status_code=502, detail=f"unwatch failed: {e}") from e

    @app.get("/pulse/inbox")
    async def pulse_inbox(days: int = 30, x_noesis_token: str = Header(default="")) -> dict:
        """The Pulse hub payload: PER-TOPIC rollups answering (1) anything unseen? and (2) how much
        moved in the rolling window — plus the watch list. Detail loads via /pulse/topic-activity."""
        cur, user = await _pulse_user(x_noesis_token)
        try:
            return {"watches": await cur.list_watches(user_id=user["id"]),
                    "days": min(max(days, 1), 365),
                    "summary": await cur.inbox_summary(user_id=user["id"], days=min(max(days, 1), 365))}
        except Exception as e:   # noqa: BLE001
            raise HTTPException(status_code=502, detail=f"inbox failed: {e}") from e

    @app.get("/pulse/topic-activity")
    async def pulse_topic_activity(topic: str, days: int = 30,
                                   x_noesis_token: str = Header(default="")) -> dict:
        """One topic's movement in the rolling window — TOPIC-AS-QUERY composition (generic to any
        vertical): relational change events matching the topic (structural containment) + NEW
        corpus sources relevant to it (the existing retrieval engine finds relevance; the corpus
        time axis supplies first_seen). One query embedding; zero LLM calls."""
        cur, user = await _pulse_user(x_noesis_token)
        days = min(max(days, 1), 365)
        if app.state.service is None:
            app.state.service = build_default_service()
        svc = app.state.service
        try:
            events = await cur.events_for_topic(topic, days=days)
            new_docs = []
            try:
                corpus_key = getattr(svc, "corpus_source_key", "") or None
                hits = await svc.search(question=topic, tenant_id="demo",
                                        source_keys=[corpus_key] if corpus_key else None, k=40)
                doc_ids = list({h.document_id for h in hits if getattr(h, "document_id", "")})
                new_docs = await cur.docs_first_seen(doc_ids, days=days)
            except Exception as e:   # noqa: BLE001 — activity degrades to events-only
                __import__("logging").getLogger("api.pulse").warning("topic activity search failed: %r", e)
            return {"topic": topic, "days": days, "events": events, "new_documents": new_docs}
        except Exception as e:   # noqa: BLE001
            raise HTTPException(status_code=502, detail=f"topic activity failed: {e}") from e

    async def _topic_registry(cur):
        """The canonical topic registry, seeded once from the vertical's covered-condition names —
        the STABILITY substrate: LLM calls prefer exact reuse, so repeated runs converge."""
        topics = await cur.list_topics()
        if not topics:
            seed = list(getattr(load_active_vertical(), "watch_topic_seed", ()) or ())
            if seed:
                await cur.ensure_topics(seed, source="seed")
                topics = await cur.list_topics()
        return topics

    def _registry_block(topics: list[str]) -> str:
        return ("\n\nEXISTING CANONICAL TOPICS (prefer exact verbatim reuse):\n"
                + "\n".join(f"- {t}" for t in topics[:400])) if topics else ""

    @app.post("/pulse/topics")
    async def pulse_topics(body: TopicsIn, x_noesis_token: str = Header(default="")) -> dict:
        """Suggest 2-5 WATCHABLE topics for a Q&A (LLM-owned judgment, Rule 18 — durable subjects,
        never patient specifics), converged onto the canonical registry: existing entries are
        reused verbatim; a genuinely novel subject is minted ONCE and becomes the stable form.
        User-initiated (the watch picker), token-gated, one small call."""
        cur, user = await _pulse_user(x_noesis_token)
        if app.state.service is None:
            app.state.service = build_default_service()
        svc = app.state.service
        prompt = getattr(load_active_vertical(), "watch_topic_prompt", None)
        if not prompt:
            return {"topics": []}

        class _Topics(BaseModel):
            topics: list[str] = []
        try:
            registry = await _topic_registry(cur)
            comp = await svc.llm.complete(
                system=prompt + _registry_block(registry),
                messages=[{"role": "user", "content":
                           f"QUESTION:\n{(body.question or '')[:2000]}\n\nANSWER:\n{(body.answer or '')[:4000]}"}],
                response_format=_Topics, max_tokens=300)
            raw = [t.strip() for t in (comp.parsed.topics or []) if t and t.strip()][:5]
            return {"topics": await cur.ensure_topics(raw)}   # registry canonical form wins
        except Exception as e:   # noqa: BLE001 — picker degrades to free-text
            _log = __import__("logging").getLogger("api.pulse")
            _log.warning("watch-topic suggestion failed: %r", e)
            return {"topics": []}

    @app.get("/pulse/watch-suggestions")
    async def pulse_watch_suggestions(x_noesis_token: str = Header(default="")) -> dict:
        """Cross-session watch suggestions: the recurring durable subjects in THIS user's question
        history (LLM judgment against the canonical registry; already-watched excluded). One small
        call, fired when the Pulse panel opens; degrades to an empty list on any failure."""
        cur, user = await _pulse_user(x_noesis_token)
        prompt = getattr(load_active_vertical(), "watch_suggest_prompt", None)
        store = _store()
        if not prompt or store is None or not user.get("email"):
            return {"suggestions": []}
        if app.state.service is None:
            app.state.service = build_default_service()

        class _Sug(BaseModel):
            topics: list[str] = []
        try:
            rows = await store.list(tenant_id="demo", q=user["email"], limit=40)
            questions = [r.get("question", "") for r in rows if r.get("question")][:40]
            if not questions:
                return {"suggestions": []}
            watched = [w["topic"] for w in await cur.list_watches(user_id=user["id"])]
            registry = await _topic_registry(cur)
            body_txt = ("QUESTION HISTORY (most recent first):\n"
                        + "\n".join(f"- {q[:200]}" for q in questions)
                        + ("\n\nALREADY WATCHED (never re-suggest):\n"
                           + "\n".join(f"- {w}" for w in watched) if watched else ""))
            comp = await app.state.service.llm.complete(
                system=prompt + _registry_block(registry),
                messages=[{"role": "user", "content": body_txt}],
                response_format=_Sug, max_tokens=300)
            raw = [t.strip() for t in (comp.parsed.topics or []) if t and t.strip()][:5]
            watched_lc = {w.lower() for w in watched}
            canon = await cur.ensure_topics(raw)
            return {"suggestions": [t for t in canon if t.lower() not in watched_lc]}
        except Exception as e:   # noqa: BLE001
            __import__("logging").getLogger("api.pulse").warning("watch suggestions failed: %r", e)
            return {"suggestions": []}

    @app.post("/pulse/seen")
    async def pulse_seen(body: SeenIn, x_noesis_token: str = Header(default="")) -> dict:
        cur, user = await _pulse_user(x_noesis_token)
        try:
            await cur.mark_seen(user_id=user["id"], event_id=body.event_id)
        except Exception as e:   # noqa: BLE001
            raise HTTPException(status_code=502, detail=f"seen failed: {e}") from e
        return {"ok": True}

    @app.get("/admin/settings")
    async def admin_settings_get(x_admin_password: str = Header(default="")) -> dict:
        """Live product settings (admin panel): per-flag override / env default / resolved value."""
        if x_admin_password != _admin_ui_pw():
            raise HTTPException(status_code=401, detail="bad admin password")
        return await _settings_payload()

    @app.post("/admin/settings")
    async def admin_settings_set(body: SettingIn, x_admin_password: str = Header(default="")) -> dict:
        """Flip a controlled flag live (no redeploy): value 'on' | 'off' | '' (follow env)."""
        if x_admin_password != _admin_ui_pw():
            raise HTTPException(status_code=401, detail="bad admin password")
        if body.key not in _LIVE_FLAGS:
            raise HTTPException(status_code=400, detail=f"unknown setting (known: {sorted(_LIVE_FLAGS)})")
        if body.value not in ("on", "off", ""):
            raise HTTPException(status_code=400, detail="value must be 'on', 'off', or '' (follow env)")
        st = _settings()
        if st is None:
            raise HTTPException(status_code=503, detail="no settings store (NOESIS_CORPUS_DSN unset)")
        try:
            await st.set(body.key, body.value)
        except Exception as e:   # noqa: BLE001
            raise HTTPException(status_code=502, detail=f"settings store error: {e}") from e
        return await _settings_payload()

    @app.get("/admin/stream-test")
    async def admin_stream_test(minutes: int = 7, x_admin_password: str = Header(default="")):
        """LLM-free SSE endurance test: pings every 15s + a tick each minute for `minutes`. Lets us
        measure exactly if/when the edge cuts an actively-pinging stream (diagnosing mid-answer drops)
        without spending a single model call."""
        if x_admin_password != _admin_ui_pw():
            raise HTTPException(status_code=401, detail="bad admin password")
        from fastapi.responses import StreamingResponse
        run = _sse_run_new()

        async def runner() -> None:
            # Registry-backed like the real runs, so resume (GET /stream/{run_id}) is testable
            # end-to-end without a model call: let the edge cut this stream, then resume it.
            total = max(1, min(minutes, 20)) * 60
            for sec in range(0, total, 15):
                await asyncio.sleep(15)
                if (sec + 15) % 60 == 0:
                    _sse_push(run, {"type": "tick", "minute": (sec + 15) // 60})
            _sse_push(run, {"type": "done"})
            _sse_done(run)

        run["task"] = asyncio.create_task(runner())

        async def gen():
            yield ": open\n\n"
            yield f"data: {json.dumps({'type': 'run', 'run_id': run['id']})}\n\n"
            async for chunk in _sse_follow(run, 0):
                yield chunk

        return StreamingResponse(gen(), media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no", "Connection": "keep-alive"})

    @app.get("/admin/feedback")
    async def admin_feedback(limit: int = 25, x_admin_token: str = Header(default="")) -> dict:
        """The accumulating feedback signal, aggregated (totals · by verdict · by W-mode · by day ·
        recent rows · user counts) — how we watch what's building up over time. Same admin-token gate
        as corpus ingest."""
        if not accounts_enabled():
            raise HTTPException(status_code=404, detail="accounts are not enabled")
        want = os.environ.get("NOESIS_ADMIN_TOKEN", "")
        if want and x_admin_token != want:
            raise HTTPException(status_code=401, detail="bad admin token")
        store = _accounts()
        if store is None:
            raise HTTPException(status_code=503, detail="no account store configured")
        try:
            return await store.feedback_summary(limit=min(limit, 100))
        except Exception as e:
            raise HTTPException(status_code=502, detail=f"feedback summary failed: {e}") from e

    @app.get("/sessions")
    async def list_sessions(tenant_id: str = "demo", limit: int = 100, q: str = "",
                            audience: str = "", kind: str = "") -> dict:
        """Recent saved Q&A for this vertical + tenant (history), optional search `q`, an optional
        `kind` filter ('panel'|'research') for the Past-Sessions tabs, and — when the patient-mode
        flag is on — an optional audience filter ('clinician'|'patient')."""
        store = _store()
        if store is None:
            return {"sessions": []}
        aud = audience if (patient_mode_enabled() and audience in ("clinician", "patient")) else None
        knd = kind if kind in ("panel", "research") else None
        try:
            return {"sessions": await store.list(tenant_id=tenant_id, limit=min(limit, 300),
                                                 q=q or None, audience=aud, kind=knd)}
        except Exception as e:
            raise HTTPException(status_code=502, detail=f"session store error: {e}") from e

    @app.get("/videos")
    async def list_videos(tenant_id: str = "demo", limit: int = 200) -> dict:
        """All briefing videos across sessions (for the video catalogue)."""
        store = _store()
        if store is None:
            return {"videos": []}
        try:
            vids = await store.list_videos(tenant_id=tenant_id, limit=min(limit, 300))
            # hide videos whose file is gone (local + R2 both missing)
            from api.video import video_exists
            vids = await asyncio.to_thread(
                lambda: [v for v in vids if video_exists(v["video_filename"])])
            return {"videos": vids}
        except Exception as e:
            raise HTTPException(status_code=502, detail=f"session store error: {e}") from e

    @app.get("/sessions/{session_id}")
    async def get_session(session_id: str) -> dict:
        """Full saved Q&A (answer, claims, and any linked video)."""
        store = _store()
        if store is None:
            raise HTTPException(status_code=404, detail="no session store")
        row = await store.get(session_id)
        if row is None:
            raise HTTPException(status_code=404, detail="session not found")
        return row

    @app.delete("/sessions/{session_id}")
    async def delete_session(session_id: str) -> dict:
        """Soft-delete a session (hidden from list/get; row retained)."""
        store = _store()
        if store is None:
            raise HTTPException(status_code=404, detail="no session store")
        if not await store.soft_delete(session_id):
            raise HTTPException(status_code=404, detail="session not found")
        return {"deleted": True}

    @app.post("/sessions/{session_id}/patient-flag")
    async def session_patient_flag(session_id: str, body: PatientFlagIn) -> dict:
        """Mark/unmark a session as a REAL-WORLD PATIENT case (orange ◉ in the session list)."""
        store = _store()
        if store is None:
            raise HTTPException(status_code=404, detail="no session store")
        if not await store.set_real_patient(session_id, body.real_patient):
            raise HTTPException(status_code=404, detail="session not found")
        return {"id": session_id, "real_patient": body.real_patient}

    @app.get("/admin/coverage")
    async def admin_coverage() -> dict:
        """Live corpus coverage: what's ingested (per source/kind + per-download runs) and
        the declared roadmap (covered vs remaining conditions) from the active vertical."""
        if app.state.service is None:
            app.state.service = build_default_service()
        svc = app.state.service
        ui = getattr(svc, "ui", None)
        plan = ui.coverage_plan() if ui and hasattr(ui, "coverage_plan") else {}
        live: dict = {"by_source": {}, "by_kind": {}, "by_country": {}, "total_blocks": 0,
                      "total_docs": 0, "runs": []}
        dsn = os.environ.get("NOESIS_CORPUS_DSN")
        if dsn:
            import json
            import asyncpg
            conn = await asyncpg.connect(dsn)
            try:
                for r in await conn.fetch(
                    "SELECT source_key, count(*) blocks, count(DISTINCT document_id) docs "
                    "FROM rs_block GROUP BY source_key"):
                    live["by_source"][r["source_key"] or "?"] = {"blocks": r["blocks"], "docs": r["docs"]}
                for r in await conn.fetch(
                    "SELECT facets->>'source_kind' kind, count(*) blocks FROM rs_block GROUP BY 1"):
                    if r["kind"]:
                        live["by_kind"][r["kind"]] = r["blocks"]
                for r in await conn.fetch(
                    "SELECT facets->>'source_country' country, count(*) blocks FROM rs_block GROUP BY 1"):
                    live["by_country"][r["country"] or "?"] = r["blocks"]
                live["total_blocks"] = await conn.fetchval("SELECT count(*) FROM rs_block") or 0
                live["total_docs"] = await conn.fetchval("SELECT count(DISTINCT document_id) FROM rs_block") or 0
                if await conn.fetchval("SELECT to_regclass('rs_ingest_run')"):
                    for r in await conn.fetch(
                        "SELECT condition, by_source, total_blocks, created_at FROM rs_ingest_run "
                        "ORDER BY created_at DESC LIMIT 200"):
                        bs = r["by_source"]
                        live["runs"].append({
                            "condition": r["condition"],
                            "by_source": json.loads(bs) if isinstance(bs, str) else (bs or {}),
                            "total_blocks": r["total_blocks"],
                            "created_at": r["created_at"].isoformat() if r["created_at"] else None,
                        })
            except Exception as e:  # noqa: BLE001
                live["error"] = str(e)
            finally:
                await conn.close()
        return {"vertical": getattr(svc, "vertical_name", ""), "plan": plan, "live": live}

    @app.get("/admin", response_class=HTMLResponse)
    def admin_page(accept_encoding: str = Header(default="")):
        return _html_response("admin.html", accept_encoding)

    return app
