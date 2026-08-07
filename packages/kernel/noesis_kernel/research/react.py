"""Generic ReAct research loop — domain-free mechanics.

search → observe → … → answer, bounded by the cost governor, with the provenance
hard gate applied to every emitted claim: a claim survives only if its verbatim
`quote` exists at its cited atom's locator (else it's rejected — no fabrication).

The LLM decides each step via a structured `AgentStep` (the kernel's LLM port is
structured-output, so no bespoke tool-use protocol is needed). Domain vocabulary,
the system prompt, and richer gating (the 10th-seam policy) come from the vertical
in P3; here the mechanics are proven offline with a scripted FakeLLM.
"""
from __future__ import annotations

import logging
import re
import time
from dataclasses import dataclass, field
from typing import Literal

_log = logging.getLogger(__name__)

# Compose is the user-facing DELIVERABLE (the prose answer), not discretionary enrichment — a
# transient LLM blip on that one call must not silently drop the answer while the verified evidence
# survives (the 'grounded, N claims, empty answer' bug). Retry a few times, then surface a note.
_COMPOSE_ATTEMPTS = 3
_COMPOSE_BACKOFF_S = 1.5          # base backoff between compose retries (tests patch to 0)
# Compose is the user-facing prose answer synthesizing up to ~60 findings (effort-scaled) with inline
# [n] citations — it needs far more room than a planner step. At the 2048 default the emit tool-call
# gets TRUNCATED mid-answer → the partial dict fails ComposedAnswer validation on EVERY retry (the
# deterministic 'couldn't be generated' bug). Only actually-generated tokens are billed, so a high
# ceiling adds no cost, only headroom.
_COMPOSE_MAX_TOKENS = 8000
# The ReAct step (AgentStep) emits an `action` plus, on the answer step, a list of claims (each with
# text + atom_id + a verbatim quote). On a broad, evidence-rich question the agent can emit MANY claims
# in one step, and at the 2048 default the emit tool-call TRUNCATES mid-JSON → a hard provider error
# surfaces as a 502 ("Couldn't reach the research service"). Give the step ample room — only
# actually-generated tokens are billed, so a high ceiling is headroom, not cost.
_PLANNER_MAX_TOKENS = 8000
_COMPOSE_FAIL_NOTE = (
    "_The written answer couldn't be generated just now, but the evidence below was retrieved and "
    "verified against its sources. Please retry the question._")

# Compose sees only the verified findings, capped for cost + scannability. Default selection is
# first-come (retrieval/extraction order). Under the evidence-select flag we collect MORE candidates
# and keep the ones most RELEVANT to the question — so compose gets the BEST findings, not the first.
_COMPOSE_CLAIM_CAP = 30       # max verified findings sent to compose
_EXTRACT_COLLECT = 80         # under evidence-select, gather up to this many before ranking down

from pydantic import BaseModel, Field

from noesis_kernel.contract.dto import RetrievalRequest
from noesis_kernel.contract.protocols import GatingPolicy, RetrievalSource
from noesis_kernel.providers.embeddings import Embedder
from noesis_kernel.providers.llm import LLMClient
from noesis_kernel.research.atoms import AtomStore
from noesis_kernel.research.budget import BudgetExceeded, BudgetState
from noesis_kernel.research.provenance import BlockSpanVerifier
from noesis_kernel.retrieval.dispatch import multi_query_retrieve


# ---- the LLM's structured step + emitted claims --------------------------

class ClaimOut(BaseModel):
    text: str            # the claim
    atom_id: str         # the atom it cites
    quote: str           # a verbatim span from that atom supporting the claim


class AgentStep(BaseModel):
    action: Literal["search", "answer"]
    query: str | None = None
    queries: list[str] = []     # optional reformulations → multi-query fusion (recall)
    claims: list[ClaimOut] = []


class ChartBar(BaseModel):
    """One datum of a chart. `value` is plotted; `value_str` is that figure EXACTLY as it appears in the
    cited finding (used to VERIFY it's grounded); `finding` is the 1-based finding index. `series` groups
    bars for a grouped chart (e.g. "Efficacy" vs "Adverse events"). `low`/`high` (+ their *_str) are the
    optional confidence-interval / range bounds for an INTERVAL (forest-plot) chart — each also grounded."""
    label: str
    value: float
    value_str: str = ""
    finding: int = 0
    series: str = ""
    low: float | None = None
    low_str: str = ""
    high: float | None = None
    high_str: str = ""


class ChartSpec(BaseModel):
    """A chart built ONLY from verified findings. Kinds: 'bar' (one value per option), 'grouped_bar'
    (2+ series per option — e.g. benefit vs risk), 'interval' (point estimate + CI/range per option, a
    forest plot). EVERY plotted number (value, and low/high when present) must appear verbatim in its
    cited finding, or the whole chart is dropped. Meant for patterns hard to read from prose/tables."""
    kind: str = "bar"            # "bar" | "grouped_bar" | "interval"
    title: str = ""
    unit: str = ""
    bars: list[ChartBar] = []


# ---- Reasoning Read: the interpretation layer (factra "Executive Read" discipline) -----------
# The answer already exposes span-verified FACTS. The Reasoning Read adds a SEPARATE, typed layer of
# INTERPRETATION on top — tensions, gaps, assumptions, implications, what-would-change-the-answer —
# each resting on specific findings and containing NO number/date/dose not already in those findings.
# It is validated in code (dangling-ref + no-new-facts drops), exactly like `charts`, so a fabricated
# inference can never ship. Populated only when the reasoning-read flag drives the compose directive.

# Closed set of interpretation kinds (Literal enforces it at parse; the guard re-checks defensively).
InterpretationKind = Literal["tension", "gap", "assumption", "implication", "what_would_change_this"]


class InterpretationItem(BaseModel):
    """ONE labeled piece of interpretation resting on specific verified findings. `kind` is drawn from a
    closed set; `basis_findings` are the 1-based finding indices it rests on (dangling refs are dropped);
    `text` may contain NO hard token (number/%/date/$/dose) absent from its basis findings (no-new-facts)."""
    text: str
    kind: InterpretationKind = "implication"
    basis_findings: list[int] = []


class ConfidenceDim(BaseModel):
    """One confidence dimension: a coarse LLM-owned band + a one-line rationale grounded in the evidence's
    character (e.g. how many/what tier of studies, whether it's causal vs associational)."""
    level: Literal["high", "moderate", "low", "unknown"] = "unknown"
    rationale: str = ""


class ConfidenceRead(BaseModel):
    """Three orthogonal confidence dimensions (feedback #14): FACTUAL (are the reported facts solid?),
    CAUSAL (does the evidence support a causal reading or only association?), GENERALIZATION (does it
    transfer beyond the studied population/setting?). Each is qualitative — it adds NO new fact."""
    factual: ConfidenceDim = ConfidenceDim()
    causal: ConfidenceDim = ConfidenceDim()
    generalization: ConfidenceDim = ConfidenceDim()


class ComposedAnswer(BaseModel):
    """A synthesized prose answer built ONLY from the verified findings, with
    inline [n] references to them so every statement stays traceable."""
    answer: str
    # Honesty signal (LLM-owned): does the evidence DIRECTLY address the asked question, or is it
    # only analogue/tangential? When false, `gap_note` names what direct evidence is missing — the
    # kernel surfaces it as a coverage gap so a "grounded-on-analogues" answer still flags the gap.
    directly_addresses: bool = True
    gap_note: str = ""
    # Optional bar charts (only when the answer-charts flag drives the directive to emit them). Each is
    # VALIDATED against the verified findings before it reaches the UI — an ungrounded bar drops the chart.
    charts: list[ChartSpec] = []
    # Reasoning Read (only when the reasoning-read flag drives the directive). Both are VALIDATED /
    # surfaced in the kernel; empty/None when the directive doesn't ask → byte-identical OFF path.
    interpretation: list[InterpretationItem] = Field(
        default=[], description="Typed interpretation of the evidence (tension/gap/assumption/"
        "implication/what_would_change_this) — populate when the directive asks for a Reasoning Read.")
    confidence: ConfidenceRead | None = Field(
        default=None, description="Three-dimension confidence read (factual/causal/generalization) — "
        "populate when the directive asks for a Reasoning Read.")
    # The Reasoning Read's FRAME: a purpose (the decision/outcome the reasoning serves, from the
    # question) and a conclusion (the informed judgment toward that purpose). These turn the typed
    # `interpretation` items from disconnected observations into a purpose-driven analysis that
    # CONVERGES on a decision. Both are grounded (no hard token absent from the findings).
    reasoning_purpose: str = Field(
        default="", description="ONE sentence naming the decision or outcome the reasoning serves, "
        "framed from the question (the north star the interpretation factors are organized around). "
        "Populate only for a Reasoning Read; adds no new fact.")
    reasoning_conclusion: str = Field(
        default="", description="The informed judgment TOWARD the purpose: given the factors and their "
        "strength, what the evidence supports concluding or doing (not individualized advice). 1–3 "
        "sentences, resting on the findings, no new fact. Populate only for a Reasoning Read.")


def _validate_charts(charts: list[ChartSpec], verified: list["VerifiedClaim"]) -> list[dict]:
    """Keep only charts whose EVERY plotted number is grounded: for each bar, the finding index is valid
    AND its `value_str` (and `low_str`/`high_str` when present) appears verbatim (case-insensitive) in
    that finding's text or quote. Fail-safe — any bad number drops the WHOLE chart (a partly-verified
    chart is worse than none). Also enforces a real comparison (>=2 groups). Returns dicts for the API."""
    def _grounded(s: str, finding: int) -> bool:
        s = (s or "").strip().lower()
        if not s or not (1 <= finding <= len(verified)):
            return False
        src = (verified[finding - 1].text + " " + verified[finding - 1].quote).lower()
        return s in src

    out: list[dict] = []
    for ch in charts or []:
        bars = ch.bars or []
        # a chart needs >=2 distinct groups (labels) to be a comparison worth showing
        if len({(b.label or "").strip() for b in bars}) < 2:
            continue
        ok = True
        for b in bars:
            if not _grounded(b.value_str, b.finding):
                ok = False; break
            # interval bounds, when given, must ALSO be grounded in the same cited finding
            if (b.low is not None or b.low_str) and not _grounded(b.low_str, b.finding):
                ok = False; break
            if (b.high is not None or b.high_str) and not _grounded(b.high_str, b.finding):
                ok = False; break
        if ok:
            out.append(ch.model_dump())
        else:
            _log.warning("chart dropped: a plotted figure not found in its cited finding (title=%r)", ch.title)
    return out


# Computable token classes (Rule 18: structural, not a semantic heuristic — the LLM still owns MEANING;
# this only checks a number/date/dose the model wrote also exists in the findings it cited). Matches
# percentages/decimals/integers, ISO and US dates, $ amounts, and dose-like "5 mg" / "10mg".
_HARD_TOKEN_RE = re.compile(
    r"""(?xi)
    (?<![A-Za-z0-9])                        # NOT letter/digit-adjacent → skip PCSK9, B12, COVID19, CoQ10
    (?:
      \d{4}-\d{2}-\d{2}                       # 2026-07-01 (longest first)
      | \$?\d{1,3}(?:,\d{3})+(?:\.\d+)?       # 1,234 / $1,234.56
      | \d+(?:\.\d+)?\s?(?:mg|mcg|µg|g|ml|kg|units?|iu)\b   # 5 mg / 10mg / 250 mcg (dose)
      | \$?\d+(?:\.\d+)?%?                     # 9.5 / 9.5% / $4.2 / 42
      | \d{1,2}/\d{1,2}/\d{2,4}              # 7/1/2026
    )
    """,
)


def _norm_token(tok: str) -> str:
    """Normalize a hard token for membership: lowercase, drop $ , % and internal whitespace so
    '5 mg' and '5mg' compare equal; keep digits, dots, dashes, slashes, unit letters."""
    return tok.strip().lower().lstrip("$").rstrip("%").replace(",", "").replace(" ", "")


def extract_hard_tokens(text: str) -> set[str]:
    """Extract computable numeric/date/dose tokens from prose (normalized). Structural extraction only
    (Rule 18) — used to enforce that interpretation adds no number/date/dose the findings don't state."""
    return {_norm_token(m.group(0)) for m in _HARD_TOKEN_RE.finditer(text or "")}


def _validate_interpretation(items: list["InterpretationItem"],
                             verified: list["VerifiedClaim"]) -> list[dict]:
    """Keep only interpretation items that are (a) a valid kind, (b) resting on ≥1 real finding
    (dangling-ref: basis indices are clamped to 1..n; an item left with none is dropped), and (c)
    introduce NO hard token (number/%/date/$/dose) absent from the TEXT/QUOTE of their basis findings
    (no-new-facts). Fail-safe — any violation drops that item. This is PROVENANCE (Rule 6), not a
    correctness check: it proves the interpretation didn't fabricate a figure, not that it's the right
    reading. Returns dicts (with resolved 1-based `basis_findings`) for the API."""
    allowed = {"tension", "gap", "assumption", "implication", "what_would_change_this"}
    n = len(verified)
    out: list[dict] = []
    for it in items or []:
        kind = (it.kind or "").strip()
        text = (it.text or "").strip()
        if kind not in allowed or not text:
            continue
        basis = [b for b in (it.basis_findings or []) if isinstance(b, int) and 1 <= b <= n]
        if not basis:            # dangling: interpretation must rest on ≥1 grounded finding
            _log.warning("interpretation dropped: no valid basis finding (kind=%s)", kind)
            continue
        # no-new-facts: every hard token in the item's text must appear in a basis finding's text/quote
        basis_src = " ".join((verified[b - 1].text + " " + verified[b - 1].quote) for b in basis)
        basis_tokens = extract_hard_tokens(basis_src)
        item_tokens = extract_hard_tokens(text)
        if not item_tokens.issubset(basis_tokens):
            _log.warning("interpretation dropped: hard token not in basis findings (kind=%s, extra=%s)",
                         kind, item_tokens - basis_tokens)
            continue
        out.append({"text": text, "kind": kind, "basis_findings": basis})
    return out


def _refs_valid(text: str, n_findings: int) -> bool:
    """Domain-free provenance check on a composed answer: it must cite at least one
    finding and every inline [n] must resolve to a real finding (1..n_findings).

    This is structural validation of citation FORMAT (Rule 18: parsing/validating a
    format is code's job, not a semantic heuristic) — it guards against a structured
    directive tempting the model to over-cite or invent a reference number.
    """
    refs = [int(m) for m in re.findall(r"\[(\d+)\]", text)]
    if not refs:
        return False
    return all(1 <= r <= n_findings for r in refs)


# Evidence-fitness (flag): a small, BOUNDED tier boost added on top of the dense relevance score, so
# when two findings are similarly relevant the stronger tier (guideline/SR > RCT > cohort > case report)
# surfaces into the compose cap. Boost-only + small weight so cosine still dominates and an unknown tier
# (rank 0) is a no-op → never demotes a finding below its relevance rank. Max authority rank = 6.
_EVIDENCE_FITNESS_WEIGHT = 0.15
_EVIDENCE_MAX_RANK = 6


async def _rank_claims_by_relevance(question, claims, embedder, top, *,
                                    evidence_ranker=None):
    """Keep the `top` verified claims most RELEVANT to the question, by dense cosine similarity of
    claim↔question embeddings (Rule 18 — a computable relevance signal, not a keyword heuristic). When
    `evidence_ranker` is supplied (evidence-fitness on), a SMALL bounded evidence-tier boost is added so
    a stronger-tier finding wins ties — boost-only, never demoting below the relevance baseline. Neither
    touches the span/entailment gates; only which already-verified claims survive the cap changes.
    Fail-safe: any embedding error → the original order's first `top` (never worse than today)."""
    import asyncio
    import math
    if len(claims) <= top:
        return list(claims)
    try:
        vecs = await asyncio.to_thread(lambda: embedder.embed([question] + [c.text for c in claims]))
    except Exception:   # noqa: BLE001
        return list(claims)[:top]
    qv = vecs[0]
    qn = math.sqrt(sum(x * x for x in qv)) or 1.0

    def _boost(i: int) -> float:
        if evidence_ranker is None:
            return 0.0
        try:
            r = evidence_ranker(getattr(claims[i], "evidence_kind", "") or "")
        except Exception:   # noqa: BLE001 — ranking must never break selection
            return 0.0
        return _EVIDENCE_FITNESS_WEIGHT * (max(0, int(r)) / _EVIDENCE_MAX_RANK)

    def _score(i: int) -> float:
        v = vecs[1 + i]
        dot = sum(a * b for a, b in zip(qv, v))
        vn = math.sqrt(sum(x * x for x in v)) or 1.0
        return dot / (qn * vn) + _boost(i)          # cosine + bounded tier boost (boost-only)

    order = sorted(range(len(claims)), key=_score, reverse=True)
    return [claims[i] for i in order[:top]]


# ---- results -------------------------------------------------------------

@dataclass
class VerifiedClaim:
    text: str
    atom_id: str
    quote: str
    source_key: str = ""
    document_title: str = ""
    document_id: str = ""
    # Evidence-fitness (Phase 1): the cited atom's facets + a vertical-classified evidence tier. Raw
    # data only — nothing consumes it unless the evidence-fitness flag is on (ranking) or an eval reads
    # it (evidence_floor). Domain-free: `evidence_kind` is filled by a vertical-supplied classifier.
    facets: dict = field(default_factory=dict)
    evidence_kind: str = ""


@dataclass
class RejectedClaim:
    text: str
    atom_id: str
    quote: str
    reason: str          # "unknown_atom" | "quote_not_grounded"


@dataclass
class AnswerResult:
    # The synthesized prose answer (factra "living answer" model) — grounded in
    # the verified findings below; references them inline as [1], [2], …
    composed_answer: str = ""
    # A labeled, DESCRIPTIVE reading of any user-uploaded image (from the vision pre-step).
    # NOT a diagnosis, NOT a verified claim — surfaced separately so the UI can show it as
    # context; it only framed the search, it never entered the grounded answer/compose.
    visual_observation: str = ""
    verified_claims: list[VerifiedClaim] = field(default_factory=list)
    rejected_claims: list[RejectedClaim] = field(default_factory=list)
    coverage_gaps: list[str] = field(default_factory=list)   # vertical-signalled gaps
    # per-source contribution: which sources were retrieved vs. actually CITED in a
    # verified claim → shows what sources help answer (user-requested analytics).
    source_stats: dict[str, dict[str, int]] = field(default_factory=dict)
    steps: int = 0
    atoms_gathered: int = 0
    retried_empty: bool = False          # the extract recovery re-ask fired (observability)
    compose_failed: bool = False         # compose exhausted its retries → the answer is the fail note
    stopped_reason: str = "answered"     # "answered" | "budget" | "max_steps"
    effort: float = 1.0                  # the resolved effort multiplier this run used (observability)
    resolved_question: str = ""          # condensed self-contained question (set only if it differed)
    clarification: str = ""              # a clarifying question to ask instead of answering (ambiguous follow-up)
    charts: list = field(default_factory=list)   # validated grounded bar charts (dicts) for the UI
    derived_from_prior: bool = False     # answer is a transform of the PREVIOUS answer (no new retrieval)
    # Reasoning Read (flag): a purpose-driven analysis — a stated PURPOSE, the interpretation FACTORS
    # that bear on it, a converging CONCLUSION, and the 3-dimension confidence read. All empty/None
    # unless the reasoning-read flag drove the compose directive (byte-identical OFF).
    interpretation: list = field(default_factory=list)
    confidence: dict | None = None
    reasoning_purpose: str = ""
    reasoning_conclusion: str = ""
    # Troubleshooting trace (flag): per-turn steps, tool-call breakdown, the grounding funnel,
    # retries, and failures — None unless collect_diagnostics was requested (byte-identical OFF).
    diagnostics: dict | None = None

    @property
    def grounded(self) -> bool:
        """True iff the delivered answer has ≥1 span-verified claim.

        Rejected (ungrounded) claims are caught by the gate and excluded from the
        answer — they're reported separately via `rejected_claims`, not a reason to
        call the surviving verified claims ungrounded. A pure refusal (0 verified)
        or an all-fabricated answer (0 verified, ≥1 rejected) is not grounded.
        """
        return bool(self.verified_claims)


async def run_react(
    *,
    question: str,
    llm: LLMClient,
    embedder: Embedder,
    source: RetrievalSource,
    tenant_id: str,
    workspace_id: str | None = None,
    budget: BudgetState,
    gating: GatingPolicy | None = None,
    system_prompt: str = "You are an evidence-grounded research agent.",
    answer_format: str | None = None,
    attachment_context: str | None = None,
    history_context: str | None = None,
    planner_llm: LLMClient | None = None,     # fast model for search-planning steps (compose uses `llm`)
    on_event=None,                            # optional async callback(dict) for live progress (SSE)
    aux_source: RetrievalSource | None = None,  # e.g. web: queried ONCE per step (no variant fan-out)
    claims_first: bool = False,               # run comprehensive extraction over ALL atoms (flag)
    extraction_lenses: tuple[str, ...] = (),  # vertical-supplied lenses for the extractor
    evidence_select: bool = False,            # rank claims by relevance before the cap + wider atom window
    atom_cap: int = 1600,                     # per-atom char window for the extractor (evidence-select raises it)
    facets: dict | None = None,               # hard retrieval facet filter (empty {} = no filter, byte-identical)
    max_steps: int = 8,
    k: int = 10,
    planner_atom_window: int = 60,            # atoms SHOWN to the planner per step (store keeps all)
    compose_claim_cap: int = _COMPOSE_CLAIM_CAP,  # max verified findings sent to compose (effort-scalable)
    extract_collect: int = _EXTRACT_COLLECT,      # candidate pool before relevance-ranking (effort-scalable)
    answer_focus: bool = False,               # ANSWER the question + scope to its subject (vs compile findings)
    reasoning_read: bool = False,             # surface the validated interpretation + confidence layer (flag)
    collect_diagnostics: bool = False,        # capture a troubleshooting trace (turns/tools/retries/failures)
    classify_evidence=None,                   # vertical hook (source_key, facets) -> evidence_kind str (Rule 18: structural)
    evidence_fitness: bool = False,           # boost stronger evidence tiers into the compose cap (flag)
    evidence_ranker=None,                     # vertical hook: evidence_kind -> int rank (the authority pyramid)
) -> AnswerResult:
    import asyncio
    atoms = AtomStore()
    result = AnswerResult()
    notes: list[str] = []          # running coverage-gap / step notes for the agent
    # Troubleshooting trace (flag): built ONLY when requested, purely from data already flowing through
    # the loop (no extra LLM calls). None → byte-identical OFF path.
    _diag_t0 = time.monotonic() if collect_diagnostics else None
    diag = ({"trace": [], "retries": {"compose": 0, "compose_ref_retry": False, "extract_recovery": 0},
             "failures": [], "compose_calls": 0} if collect_diagnostics else None)
    # The span-verifier's block loader must cover EVERY source a claim can cite — corpus AND aux
    # (web). Since search is split (corpus multi-query + aux single-query), combine their loaders
    # so a web-cited quote is still verifiable (else all web claims would be rejected).
    _corpus_loader = source.make_block_loader(tenant_id, workspace_id)
    if aux_source is not None:
        _aux_loader = aux_source.make_block_loader(tenant_id, workspace_id)
        def _combined_loader(document_id: str, block_id: str):
            t = _corpus_loader(document_id, block_id)
            return t if t is not None else _aux_loader(document_id, block_id)
        verifier = BlockSpanVerifier(_combined_loader)
    else:
        verifier = BlockSpanVerifier(_corpus_loader)
    planner = planner_llm or llm   # planning steps can use a cheaper/faster model than compose

    async def emit(ev: dict) -> None:
        if on_event is not None:
            try:
                await on_event(ev)
            except Exception:
                pass               # progress events are best-effort; never break the research loop

    # Labeled user-provided context (image reading and/or uploaded-document text) for the
    # step prompts ONLY (search + reasoning framing). It is deliberately kept OUT of the
    # question string and the compose step, so attachment content can never surface as if
    # it were a grounded corpus finding.
    att = (attachment_context or "").strip()
    img_ctx = (
        f"USER-PROVIDED CONTEXT (from an uploaded image and/or document; NOT corpus "
        f"evidence — use it ONLY to decide what to search for and how to interpret "
        f"findings; NEVER cite it as a source or a verified claim):\n"
        f"{att}\n\n"
        if att else ""
    )
    # Prior conversation turns (for a FOLLOW-UP question). Context ONLY — it lets the agent resolve
    # an elliptical follow-up ("what about in children?") against what was already discussed. Like
    # image/doc context, it NEVER becomes a grounded claim and never enters the compose step.
    conv = (history_context or "").strip()
    conv_ctx = (
        f"CONVERSATION SO FAR (prior questions and answers in this thread; context to interpret "
        f"the CURRENT question — NOT corpus evidence, NEVER cite it as a source or verified claim):\n"
        f"{conv}\n\n"
        if conv else ""
    )

    def _mk_verified(text: str, atom_id: str, quote: str, atom) -> VerifiedClaim:
        """Build a VerifiedClaim, stamping the cited atom's facets + evidence tier (best-effort;
        classification is a structural vertical hook — a bad/absent classifier never breaks the answer)."""
        kind = ""
        if classify_evidence is not None:
            try:
                kind = classify_evidence(atom.source_key, atom.facets) or ""
            except Exception:   # noqa: BLE001 — classification must never break grounding
                kind = ""
        return VerifiedClaim(text, atom_id, quote, atom.source_key, atom.document_title,
                             atom.document_id, facets=dict(atom.facets or {}), evidence_kind=kind)

    def _apply_answer(step: AgentStep) -> None:
        for c in step.claims:
            atom = atoms.get(c.atom_id)
            if atom is None or atom.locator is None:
                result.rejected_claims.append(RejectedClaim(c.text, c.atom_id, c.quote, "unknown_atom"))
            elif verifier.verify(c.quote, atom.locator):
                result.verified_claims.append(_mk_verified(c.text, c.atom_id, c.quote, atom))
            else:
                result.rejected_claims.append(RejectedClaim(c.text, c.atom_id, c.quote, "quote_not_grounded"))

    async def _ask(mode: str = "step") -> AgentStep:
        # Show the planner only the most-recent window of atoms (the store keeps ALL for grounding /
        # verification) — keeps late-step prompts from snowballing. Claims can cite only shown atoms.
        _all = atoms.all()
        _shown = _all[-planner_atom_window:] if len(_all) > planner_atom_window else _all
        obs = "\n".join(f"{a.atom_id}: {a.text}" for a in _shown) or "(no evidence yet)"
        if mode == "extract":
            # DEDICATED extraction recovery: the agent answered with NO claims even though relevant
            # evidence exists. This prompt does NOT reuse the permissive discipline below — when
            # evidence exists an empty answer is INVALID here (the #1 abstention cause). Provenance
            # is unchanged: every emitted claim still passes the verbatim span-check.
            instr = (
                "You returned an EMPTY claims list, but relevant evidence IS gathered above. When "
                "relevant evidence exists, an empty answer is INVALID — you MUST extract the facts it "
                "directly supports. Emit at least one claim for EACH directly-relevant atom you can "
                "(more is better); a PARTIAL answer is correct and expected — do not withhold because "
                "the question asks for a ranking/recommendation/completeness the evidence can't fully "
                "settle. For each claim: cite the atom_id and copy a 'quote' EXACTLY, character-for-"
                "character, from that atom's text (no paraphrase/summary/reformatting). action MUST be "
                "'answer'; do NOT search. Format example (STRUCTURE ONLY — do not reuse these words): "
                '{"action":"answer","claims":[{"text":"A trial evaluates drug X for condition Y.",'
                '"atom_id":"a3","quote":"a verbatim span copied from atom a3"}]}')
        elif mode == "force":
            instr = ("You have reached the evidence-gathering limit. You MUST now "
                     "action='answer'. Do NOT search.")
        else:
            instr = ("Either action='search' with a query (and optional reformulations in "
                     "'queries') to gather more, or action='answer' with claims.")
        # Shared answering discipline: report what the evidence DIRECTLY supports (partial is
        # fine — the synthesis notes what isn't), and copy quotes VERBATIM so the span-check
        # passes. This is the fix for advice/ranking questions where the model would otherwise
        # abstain wholesale despite holding relevant evidence.
        discipline = (
            " When you answer, report EVERY fact the evidence DIRECTLY supports — even if it "
            "only PARTIALLY answers the question, or cannot satisfy a ranking, recommendation, "
            "or 'which is best/safest' the question implies (report the supported facts; the "
            "synthesis will note what is not supported). A partial grounded answer is far better "
            "than none. Each claim must cite an atom_id and a 'quote' copied EXACTLY, "
            "character-for-character, from that atom — do NOT paraphrase, summarize, or reformat "
            "numbers/units. Return an empty claims list ONLY if NONE of the gathered evidence is "
            "relevant to the question.")
        # extract mode is self-contained + forceful — do NOT append the permissive discipline (its
        # "empty ONLY if NONE relevant" clause is the loophole the recovery must override).
        if mode != "extract":
            instr = instr + discipline
        # One fresh user message per step (all evidence so far). Ends with a user
        # turn — required by chat LLMs — and keeps the agent stateless per step.
        # img_ctx (if any) frames the search but is never merged into `question` (so it
        # stays out of the compose step and can't read as a grounded finding).
        user = (conv_ctx + img_ctx + f"Question: {question}\n\nEVIDENCE GATHERED SO FAR:\n{obs}\n\n"
                + ("NOTES:\n" + "\n".join(notes) + "\n\n" if notes else "") + instr)
        # NOTE: temperature is intentionally NOT set — the current model rejects it
        # ("deprecated for this model"). Variance is countered by the answering
        # discipline above + the extract recovery re-ask, not by sampling controls.
        res = await planner.complete(system=system_prompt,
                                     messages=[{"role": "user", "content": user}],
                                     response_format=AgentStep, max_tokens=_PLANNER_MAX_TOKENS)
        budget.charge(calls=1, tokens=res.output_tokens)
        result.steps += 1
        return res.parsed

    async def _finalize_answer(step: AgentStep) -> None:
        """Apply the answer's claims through the provenance gate, then — if the agent emitted NOTHING
        (0 verified AND 0 rejected) while it had gathered evidence — retry a DEDICATED forceful
        extraction up to a few times before giving up. This is the fix for run-to-run abstention:
        the model sometimes samples an empty answer despite relevant evidence; a single re-ask (the
        old behavior) reproduced it. The guard only ever runs in the already-failing 0-verified/
        0-rejected path — it never touches a run that produced verified or rejected claims, never
        weakens the span gate (claims still pass verify()), and is bounded by attempts + budget."""
        _apply_answer(step)
        attempts = 0
        while (not result.verified_claims and not result.rejected_claims
               and atoms.all() and not budget.exhausted and attempts < 3):
            attempts += 1
            try:
                budget.reserve()
            except BudgetExceeded:
                break
            result.retried_empty = True              # observability: the recovery fired
            retry = await _ask(mode="extract")
            if retry.action == "answer":
                _apply_answer(retry)
            # if it returned action="search" (ignoring the extract instruction), loop and re-ask
            # extract — bounded by `attempts`/budget so a stubborn model can't spin forever.
        if diag is not None and attempts:
            diag["retries"]["extract_recovery"] = attempts

    stale_searches = 0          # consecutive searches that added NO new atoms (spinning detector)
    for step_i in range(max_steps):
        if budget.exhausted:
            result.stopped_reason = "budget"
            break
        try:
            budget.reserve()
        except BudgetExceeded:
            result.stopped_reason = "budget"
            break

        # Force an answer on the final step, OR early when the agent is spinning — two searches in
        # a row that surfaced NO new evidence means more searching won't help; answer over what we
        # have instead of burning the full step budget (latency fix for no-evidence questions).
        force = step_i == max_steps - 1 or (stale_searches >= 2 and bool(atoms.all()))
        await emit({"type": "step", "step": step_i + 1})
        step: AgentStep = await _ask(mode="force" if force else "step")

        if step.action == "search":
            q = step.query or question
            await emit({"type": "search", "query": q, "variants": list(step.queries or [])})
            qvec = await asyncio.to_thread(lambda: list(embedder.embed([q])[0]))  # off the loop
            base_req = RetrievalRequest(
                query=q, tenant_id=tenant_id, workspace_id=workspace_id,
                query_embedding=qvec, k=k, facets=dict(facets or {}),
            )
            # Corpus: agent reformulations → multi-query fusion (recall); else a single search.
            # aux (web): ONE call per step on the ORIGINAL query (no per-variant fan-out) — runs
            # CONCURRENTLY with the corpus so it adds breadth without multiplying latency.
            corpus_co = (multi_query_retrieve(source, base_req, step.queries, embedder=embedder)
                         if step.queries else source.search(base_req))
            if aux_source is not None:
                got = await asyncio.gather(corpus_co, aux_source.search(base_req), return_exceptions=True)
                hits = []
                for r in got:
                    if not isinstance(r, Exception):
                        hits += r
            else:
                hits = await corpus_co
            before = len(atoms.all())
            atoms.add_hits(hits)
            added = len(atoms.all()) - before
            stale_searches = stale_searches + 1 if added == 0 else 0
            srcs = sorted({(h.source_key or "corpus") for h in hits})
            await emit({"type": "found", "added": added, "total": len(atoms.all()), "sources": srcs})
            if diag is not None:
                diag["trace"].append({"step": step_i + 1, "action": "search", "query": q,
                                      "variants": list(step.queries or []), "retrieved": added,
                                      "total_atoms": len(atoms.all()), "sources": srcs,
                                      "forced": force})

            # vertical gating: surface a real coverage gap so the agent reaches for
            # other sources or answers honestly instead of guessing.
            if gating is not None:
                gap = gating.coverage_gap(q, hits)
                if gap:
                    result.coverage_gaps.append(gap)
                    notes.append(f"COVERAGE GAP: {gap} — use another source or say so; do not guess.")
            continue

        # action == "answer": provenance hard gate (+ recovery re-ask if it abstained)
        await emit({"type": "verifying"})
        await _finalize_answer(step)
        await emit({"type": "verified", "verified": len(result.verified_claims),
                    "rejected": len(result.rejected_claims)})
        if diag is not None:
            diag["trace"].append({"step": step_i + 1, "action": "answer", "forced": force,
                                  "emitted": len(step.claims),
                                  "verified": len(result.verified_claims),
                                  "rejected": len(result.rejected_claims)})
        result.stopped_reason = "answered"
        break
    else:
        # Loop exhausted without an answer action. Force one final answer over the
        # evidence gathered (so the agent never silently returns nothing) — unless
        # the budget is spent.
        result.stopped_reason = "max_steps"
        if not budget.exhausted:
            try:
                budget.reserve()
                final = await _ask(mode="force")
                if final.action == "answer":
                    await _finalize_answer(final)
                    result.stopped_reason = "answered"
            except BudgetExceeded:
                pass

    result.atoms_gathered = len(atoms.all())

    # SECOND-MODEL FALLBACK GROUNDER (factra pattern): the Anthropic agent gathered relevant atoms
    # but still emitted NO claims (0 verified AND 0 rejected) even after the forceful extract-recovery.
    # Re-asking the same model is unreliable here — hand the atoms to a second model (OpenAI) to
    # atomize into cited claims, then run them through the SAME verbatim span gate (_apply_answer).
    # Provenance is unchanged: only claims whose quote verifies survive. Fail-safe: no key / error /
    # nothing → 0 claims and the original abstention stands.
    if (not result.verified_claims and not result.rejected_claims
            and atoms.all() and not budget.exhausted):
        await emit({"type": "grounding"})
        try:
            from noesis_kernel.research.fallback_grounder import ground_claimless
            fb = await ground_claimless(
                question=question, atoms=[(a.atom_id, a.text) for a in atoms.all()])
            if fb:
                result.retried_empty = True
                _apply_answer(AgentStep(action="answer", claims=[
                    ClaimOut(text=c["text"], atom_id=c["atom_id"], quote=c["quote"]) for c in fb]))
                await emit({"type": "verified", "verified": len(result.verified_claims),
                            "rejected": len(result.rejected_claims)})
        except Exception:   # noqa: BLE001 — fallback is best-effort; never break the answer
            pass

    # CLAIMS-FIRST comprehensive extraction (flag): the terse loop cites only a few atoms, so most
    # retrieved evidence goes unused (e.g. 2 grounded from 18). Mine EVERY atom with a cheap batched
    # model, then ADD any claim that passes BOTH the unchanged verbatim span gate AND an independent
    # entailment gate. Only adds provenance-clean claims (never fabricates, never weakens the gate);
    # runs OFF the expensive loop model. Dedups against what the loop already grounded.
    if claims_first and atoms.all() and not budget.exhausted:
        await emit({"type": "extracting"})
        try:
            from noesis_kernel.research.claims_first import entail_claims, extract_claims
            from noesis_kernel.research.provenance import normalize
            cands = await extract_claims(
                question=question, atoms=[(a.atom_id, a.text) for a in atoms.all()],
                lenses=list(extraction_lenses), atom_cap=atom_cap)
            span_ok = []                                   # candidates whose quote verbatim-verifies
            for c in cands:
                atom = atoms.get(c["atom_id"])
                if atom is not None and atom.locator is not None \
                        and verifier.verify(c["quote"], atom.locator):
                    span_ok.append((c, atom))
            verdicts = await entail_claims(claims=[c for c, _ in span_ok]) if span_ok else []
            seen = {(vc.atom_id, normalize(vc.quote)) for vc in result.verified_claims}
            added = 0
            for (c, atom), ok in zip(span_ok, verdicts):
                if not ok:                                 # entailment gate (support, not just quote)
                    continue
                key = (c["atom_id"], normalize(c["quote"]))
                if key in seen:                            # dedup vs existing + each other
                    continue
                seen.add(key)
                result.verified_claims.append(_mk_verified(c["text"], c["atom_id"], c["quote"], atom))
                added += 1
                # OFF: cap first-come at the compose limit (unchanged). ON: collect a bigger pool so
                # the relevance ranking below has real choices before it trims to the compose cap.
                if len(result.verified_claims) >= (extract_collect if evidence_select else compose_claim_cap):
                    break
            await emit({"type": "extracted", "added": added, "candidates": len(cands),
                        "total": len(result.verified_claims)})
            if diag is not None:
                diag["extraction"] = {"candidates": len(cands), "added": added}
        except Exception as _ex:   # noqa: BLE001 — extraction is best-effort; never break the answer
            if diag is not None:
                diag["failures"].append({"stage": "extraction", "detail": repr(_ex)[:200]})

    # Evidence SELECTION (flags): compose is capped for cost/scannability, so WHICH verified findings
    # survive the cap matters. Default = first-come. Under evidence-select, keep the findings most
    # RELEVANT to the question; under evidence-fitness, additionally boost stronger evidence TIERS into
    # the cap (span+entailment already passed → provenance unchanged; this only reorders/trims already-
    # verified claims). Either flag triggers the ranking pass.
    if (evidence_select or evidence_fitness) and len(result.verified_claims) > compose_claim_cap:
        await emit({"type": "selecting", "from": len(result.verified_claims), "to": compose_claim_cap})
        result.verified_claims = await _rank_claims_by_relevance(
            question, result.verified_claims, embedder, compose_claim_cap,
            evidence_ranker=(evidence_ranker if evidence_fitness else None))

    # Compose a synthesized answer FROM the verified findings only (factra "living
    # answer" model). Grounded by construction: the composer sees only the verified
    # findings and must reference them [n]; it may not add outside facts. A vertical
    # may supply an optional `answer_format` directive (domain-owned) that shapes the
    # structure — the kernel stays domain-free and only threads the string through.
    if result.verified_claims:          # compose is the DELIVERABLE — always attempt it when we have
        await emit({"type": "composing", "findings": len(result.verified_claims)})  # findings (not
        n_findings = len(result.verified_claims)
        findings = "\n".join(
            f"[{i}] {vc.text}  (quote: \"{vc.quote}\" — source: {vc.source_key})"
            for i, vc in enumerate(result.verified_claims, 1))

        async def _compose(directive: str | None) -> ComposedAnswer:
            # Base ANSWER instruction kept identical to the original (directive-free path stays a
            # near-exact no-op). A trailing META judgment (directly_addresses/gap_note) is appended
            # AFTER it — it asks only for extra metadata, not a different answer, so answer text is
            # unaffected. The vertical directive, when present, is appended AFTER that.
            compose_user = (
                f"Question: {question}\n\nVERIFIED FINDINGS (the ONLY facts you may use):\n"
                f"{findings}\n\n"
                "Write a clear, well-organized answer to the question that synthesizes "
                "these findings into coherent prose. Reference each finding inline as "
                "[n] where you use it. Use ONLY the findings above — do not add facts, "
                "figures, or claims not present in them. If they only partially answer "
                "the question, say what is and isn't supported."
                # ANSWER-FOCUS (flag): ANSWER the specific question and scope to its subject, instead of
                # compiling every retrieved finding. Fixes elliptical follow-ups ("what dose" → dumping
                # every drug's dose) AND single-turn "compile everything". Grounding is unchanged — it
                # still uses ONLY the verified findings and still cites [n].
                + (" Directly ANSWER the specific question asked. If some findings concern a DIFFERENT "
                   "subject, drug, population, or topic than the question, use ONLY the findings about "
                   "the asked subject and ignore the rest — do not enumerate unrelated findings. If the "
                   "findings do not contain the specific answer the question asks for, say so explicitly "
                   "as a gap; do NOT substitute a list of unrelated findings." if answer_focus else "")
                + "\n\nSEPARATELY (metadata, not part of the answer prose): set directly_addresses=false "
                "if the findings only address the question by analogy/adjacent topic rather than "
                "DIRECTLY (e.g. no evidence on the exact intervention/population/outcome asked); then "
                "put ONE short line in gap_note naming the direct evidence that is missing. Otherwise "
                "directly_addresses=true and gap_note empty."
                # REASONING READ (flag): anchor the structured interpretation/confidence fields at the
                # KERNEL level, symmetric to the directly_addresses metadata above — the domain-free
                # mechanics live here; the domain MEANING (what each kind is, neutrality) is in the
                # directive below. Without this anchor the model composes great prose and leaves the
                # trailing structured fields empty (the fields have defaults, so nothing forces them).
                + ("\n\nSEPARATELY, you MUST ALSO populate the STRUCTURED Reasoning Read fields (required "
                   "outputs, NOT optional, separate from the answer prose above): `reasoning_purpose` "
                   "(one sentence naming the decision/outcome the reasoning serves), 2–5 `interpretation` "
                   "factors that each bear on that purpose, `reasoning_conclusion` (the informed judgment "
                   "toward the purpose), and the three-dimension `confidence` read — all following the "
                   "REASONING READ instructions in the directive below. Each interpretation factor must "
                   "set `basis_findings` to the finding number(s) it rests on and introduce no number/"
                   "date/dose not already in those findings."
                   if reasoning_read else "")
                + (("\n\n" + directive) if directive else ""))
            comp = await llm.complete(
                system=system_prompt,
                messages=[{"role": "user", "content": compose_user}],
                response_format=ComposedAnswer, max_tokens=_COMPOSE_MAX_TOKENS)
            budget.charge(calls=1, tokens=comp.output_tokens)
            if diag is not None:
                diag["compose_calls"] += 1
            return comp.parsed

        # Compose must NOT be silently dropped on a transient LLM blip (the 'grounded, N claims,
        # empty answer' bug). It is the user-facing deliverable, so: (1) RETRY a few times — cheap
        # and idempotent, the findings are already in hand; (2) it is NOT gated on the loop budget
        # (a heavy gather must not starve the one call that writes the answer); (3) if it truly
        # can't complete, SURFACE a note + log it (Rule 13) rather than returning a blank answer.
        parsed = None
        text = ""
        for _attempt in range(_COMPOSE_ATTEMPTS):
            try:
                cand = await _compose(answer_format)
                text = (cand.answer or "").strip()   # a malformed/empty parse raises or stays "" →
                parsed = cand                         # counted as this attempt's outcome, inside the try
                if text:
                    break                             # got a real answer — done
                raise ValueError("empty compose answer")   # empty → treat as a failed attempt, retry
            except Exception as _e:   # noqa: BLE001
                _log.warning("compose attempt %d/%d failed: %r", _attempt + 1, _COMPOSE_ATTEMPTS, _e)
                if _attempt + 1 < _COMPOSE_ATTEMPTS:
                    await asyncio.sleep(_COMPOSE_BACKOFF_S * (_attempt + 1))   # backoff for a transient error
        if text:
            # Domain-free provenance check: if a directive produced an answer with a bad/absent [n]
            # reference, retry ONCE with the SAME directive (a fresh sample usually fixes an [n]
            # fluke while preserving the directive's AUDIENCE/tone — a directive-free recompose would
            # replace e.g. a patient answer with a generic clinician-toned one). Best-effort: a failed
            # fallback never overwrites the answer we already have.
            if answer_format and not _refs_valid(text, n_findings):
                if diag is not None:
                    diag["retries"]["compose_ref_retry"] = True
                try:
                    alt = await _compose(answer_format)
                    if (alt.answer or "").strip():
                        parsed, text = alt, alt.answer.strip()
                except Exception as _e:   # noqa: BLE001
                    _log.warning("compose ref-retry failed: %r", _e)
            result.composed_answer = text
            # Grounded charts: keep only bars whose figure appears in the cited finding (drop the whole
            # chart otherwise). Empty when the charts flag isn't driving the directive → no-op.
            result.charts = _validate_charts(getattr(parsed, "charts", []) or [], result.verified_claims)
            # Reasoning Read (flag): validate the interpretation layer (drop dangling/fabricated items)
            # and carry the confidence read. Gated on the flag so the OFF path never surfaces them even
            # if the model volunteered them; the guard is fail-safe (a fabricated inference is dropped).
            if reasoning_read:
                result.interpretation = _validate_interpretation(
                    getattr(parsed, "interpretation", []) or [], result.verified_claims)
                conf = getattr(parsed, "confidence", None)
                result.confidence = conf.model_dump() if conf is not None else None
                # Purpose + conclusion FRAME the factors. Grounded no-new-facts against ALL findings
                # (they synthesize across the whole set, not one basis) — a fabricated figure drops the
                # text (fail-safe). Purpose is usually number-free (it restates the decision), so it
                # passes trivially; the guard only bites if the model invents a figure.
                _all_src = " ".join((vc.text + " " + vc.quote) for vc in result.verified_claims)
                _all_tokens = extract_hard_tokens(_all_src)
                def _grounded_frame(s: str) -> str:
                    s = (s or "").strip()
                    return s if (s and extract_hard_tokens(s).issubset(_all_tokens)) else ""
                result.reasoning_purpose = _grounded_frame(getattr(parsed, "reasoning_purpose", ""))
                result.reasoning_conclusion = _grounded_frame(getattr(parsed, "reasoning_conclusion", ""))
            # Honesty signal → coverage gap: a "grounded-on-analogues" answer still flags the gap,
            # so the UI shows the prominent fill-the-gaps affordance (LLM-owned judgment, no regex).
            if parsed.directly_addresses is False and (parsed.gap_note or "").strip():
                result.coverage_gaps.append(parsed.gap_note.strip())
        if not result.composed_answer:
            # Every compose attempt failed — SURFACE it (never a silent blank); the verified
            # evidence still stands and is shown, and the user is told to retry.
            result.compose_failed = True
            result.composed_answer = _COMPOSE_FAIL_NOTE
            _log.warning("compose produced NO answer despite %d verified findings", n_findings)
            if diag is not None:
                diag["failures"].append({"stage": "compose",
                                         "detail": f"exhausted {_COMPOSE_ATTEMPTS} attempts — answer not generated"})

    # per-source contribution: retrieved (atoms) vs. cited (verified claims)
    stats: dict[str, dict[str, int]] = {}
    for a in atoms.all():
        s = a.source_key or "unknown"
        stats.setdefault(s, {"retrieved": 0, "cited": 0})["retrieved"] += 1
    for vc in result.verified_claims:
        s = vc.source_key or "unknown"
        stats.setdefault(s, {"retrieved": 0, "cited": 0})["cited"] += 1
    result.source_stats = stats

    # Troubleshooting summary (flag): fold the captured trace into a compact, UI-ready shape. Pure
    # bookkeeping over data already in hand — no extra model calls; None unless collect_diagnostics.
    if diag is not None:
        rej_by_reason: dict[str, int] = {}
        for rc in result.rejected_claims:
            rej_by_reason[rc.reason] = rej_by_reason.get(rc.reason, 0) + 1
        n_search = sum(1 for t in diag["trace"] if t.get("action") == "search")
        compose_calls = diag.pop("compose_calls", 0)
        diag["retries"]["compose"] = max(0, compose_calls - 1)   # attempts beyond the first
        diag["funnel"] = {
            "atoms_gathered": len(atoms.all()),
            "claims_emitted": len(result.verified_claims) + len(result.rejected_claims),
            "verified": len(result.verified_claims),
            "rejected": len(result.rejected_claims),
            "rejected_by_reason": rej_by_reason,
        }
        diag["tool_calls"] = {
            "llm_total": budget.spent_calls,
            "planner_steps": result.steps,
            "searches": n_search,
            "web_enabled": aux_source is not None,
            "compose_calls": compose_calls,
        }
        diag["budget"] = {"llm_calls": budget.spent_calls, "max_calls": budget.max_calls,
                          "tokens": budget.spent_tokens}
        diag["stopped_reason"] = result.stopped_reason
        diag["retried_empty"] = result.retried_empty
        diag["compose_failed"] = result.compose_failed
        # A4: evidence-tier histogram of the cited findings (prod-observable evidence-fitness signal).
        tiers: dict[str, int] = {}
        for vc in result.verified_claims:
            k = getattr(vc, "evidence_kind", "") or "unclassified"
            tiers[k] = tiers.get(k, 0) + 1
        diag["evidence_tiers"] = tiers
        # A6: hard-token scan of the PROSE answer — a number/dose/date/% in the prose that is NOT in any
        # verified finding is a potential fabrication the structured guards can't see. Report it (never
        # auto-drop the answer). Deterministic, no model call.
        unsupported = _unsupported_prose_tokens(result.composed_answer, result.verified_claims)
        if unsupported:
            diag["failures"].append({"stage": "prose_grounding",
                                     "detail": "unsupported figures in prose: " + ", ".join(sorted(unsupported))})
        diag["prose_unsupported_tokens"] = sorted(unsupported)
        diag["duration_ms"] = int((time.monotonic() - _diag_t0) * 1000)
        result.diagnostics = diag
    return result


def _unsupported_prose_tokens(prose: str, verified: list["VerifiedClaim"]) -> set[str]:
    """Hard tokens (number/dose/date/%) in the composed PROSE that appear in NO verified finding's
    text/quote — i.e. figures the prose introduced that the evidence doesn't support. Structural
    (Rule 18); the compose fail-note has none, so a failed compose reports nothing. Inline citation
    markers [n] are STRIPPED first (they're references, not figures)."""
    if not prose:
        return set()
    clean = re.sub(r"\[\d+\]", " ", prose)          # citation refs are not evidence figures
    src = " ".join((vc.text + " " + vc.quote) for vc in verified)
    return extract_hard_tokens(clean) - extract_hard_tokens(src)
