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
from dataclasses import dataclass, field
from typing import Literal

_log = logging.getLogger(__name__)

# Compose is the user-facing DELIVERABLE (the prose answer), not discretionary enrichment — a
# transient LLM blip on that one call must not silently drop the answer while the verified evidence
# survives (the 'grounded, N claims, empty answer' bug). Retry a few times, then surface a note.
_COMPOSE_ATTEMPTS = 3
_COMPOSE_BACKOFF_S = 1.5          # base backoff between compose retries (tests patch to 0)
_COMPOSE_FAIL_NOTE = (
    "_The written answer couldn't be generated just now, but the evidence below was retrieved and "
    "verified against its sources. Please retry the question._")

# Compose sees only the verified findings, capped for cost + scannability. Default selection is
# first-come (retrieval/extraction order). Under the evidence-select flag we collect MORE candidates
# and keep the ones most RELEVANT to the question — so compose gets the BEST findings, not the first.
_COMPOSE_CLAIM_CAP = 30       # max verified findings sent to compose
_EXTRACT_COLLECT = 80         # under evidence-select, gather up to this many before ranking down

from pydantic import BaseModel

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


class ComposedAnswer(BaseModel):
    """A synthesized prose answer built ONLY from the verified findings, with
    inline [n] references to them so every statement stays traceable."""
    answer: str
    # Honesty signal (LLM-owned): does the evidence DIRECTLY address the asked question, or is it
    # only analogue/tangential? When false, `gap_note` names what direct evidence is missing — the
    # kernel surfaces it as a coverage gap so a "grounded-on-analogues" answer still flags the gap.
    directly_addresses: bool = True
    gap_note: str = ""


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


async def _rank_claims_by_relevance(question, claims, embedder, top):
    """Keep the `top` verified claims most RELEVANT to the question, by dense cosine similarity of
    claim↔question embeddings. This replaces first-come truncation so compose gets the BEST findings,
    not the first ones retrieved. A dense embedding score is a computable relevance signal (Rule 18 —
    NOT a regex/keyword semantic heuristic); it never touches the span/entailment gates, so which
    claims are ELIGIBLE is unchanged — only which of the already-verified ones survive the cap.
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

    def _cos(i: int) -> float:
        v = vecs[1 + i]
        dot = sum(a * b for a, b in zip(qv, v))
        vn = math.sqrt(sum(x * x for x in v)) or 1.0
        return dot / (qn * vn)

    order = sorted(range(len(claims)), key=_cos, reverse=True)
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
    max_steps: int = 8,
    k: int = 10,
    planner_atom_window: int = 60,            # atoms SHOWN to the planner per step (store keeps all)
) -> AnswerResult:
    import asyncio
    atoms = AtomStore()
    result = AnswerResult()
    notes: list[str] = []          # running coverage-gap / step notes for the agent
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

    def _apply_answer(step: AgentStep) -> None:
        for c in step.claims:
            atom = atoms.get(c.atom_id)
            if atom is None or atom.locator is None:
                result.rejected_claims.append(RejectedClaim(c.text, c.atom_id, c.quote, "unknown_atom"))
            elif verifier.verify(c.quote, atom.locator):
                result.verified_claims.append(VerifiedClaim(
                    c.text, c.atom_id, c.quote, atom.source_key,
                    atom.document_title, atom.document_id))
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
                                     response_format=AgentStep)
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
                query_embedding=qvec, k=k,
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
                result.verified_claims.append(VerifiedClaim(
                    c["text"], c["atom_id"], c["quote"], atom.source_key,
                    atom.document_title, atom.document_id))
                added += 1
                # OFF: cap first-come at the compose limit (unchanged). ON: collect a bigger pool so
                # the relevance ranking below has real choices before it trims to the compose cap.
                if len(result.verified_claims) >= (_EXTRACT_COLLECT if evidence_select else _COMPOSE_CLAIM_CAP):
                    break
            await emit({"type": "extracted", "added": added, "candidates": len(cands),
                        "total": len(result.verified_claims)})
        except Exception:   # noqa: BLE001 — extraction is best-effort; never break the answer
            pass

    # Evidence SELECTION (flag): compose is capped for cost/scannability, so WHICH verified findings
    # survive the cap matters. Default = first-come. Under evidence-select, keep the findings most
    # RELEVANT to the question (span+entailment already passed → provenance unchanged; this only
    # reorders/trims already-verified claims). Applies to the whole set (loop + fallback + extraction).
    if evidence_select and len(result.verified_claims) > _COMPOSE_CLAIM_CAP:
        await emit({"type": "selecting", "from": len(result.verified_claims), "to": _COMPOSE_CLAIM_CAP})
        result.verified_claims = await _rank_claims_by_relevance(
            question, result.verified_claims, embedder, _COMPOSE_CLAIM_CAP)

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
                "\n\nSEPARATELY (metadata, not part of the answer prose): set directly_addresses=false "
                "if the findings only address the question by analogy/adjacent topic rather than "
                "DIRECTLY (e.g. no evidence on the exact intervention/population/outcome asked); then "
                "put ONE short line in gap_note naming the direct evidence that is missing. Otherwise "
                "directly_addresses=true and gap_note empty."
                + (("\n\n" + directive) if directive else ""))
            comp = await llm.complete(
                system=system_prompt,
                messages=[{"role": "user", "content": compose_user}],
                response_format=ComposedAnswer)
            budget.charge(calls=1, tokens=comp.output_tokens)
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
            # Domain-free provenance check: if a structured directive produced an answer with a
            # bad/absent [n] reference, retry ONCE directive-free (the proven-safe path). Best-effort:
            # a failed fallback never overwrites the directive answer we already have.
            if answer_format and not _refs_valid(text, n_findings):
                try:
                    alt = await _compose(None)
                    if (alt.answer or "").strip():
                        parsed, text = alt, alt.answer.strip()
                except Exception as _e:   # noqa: BLE001
                    _log.warning("compose directive-free fallback failed: %r", _e)
            result.composed_answer = text
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

    # per-source contribution: retrieved (atoms) vs. cited (verified claims)
    stats: dict[str, dict[str, int]] = {}
    for a in atoms.all():
        s = a.source_key or "unknown"
        stats.setdefault(s, {"retrieved": 0, "cited": 0})["retrieved"] += 1
    for vc in result.verified_claims:
        s = vc.source_key or "unknown"
        stats.setdefault(s, {"retrieved": 0, "cited": 0})["cited"] += 1
    result.source_stats = stats
    return result
