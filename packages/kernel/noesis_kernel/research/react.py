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

import re
from dataclasses import dataclass, field
from typing import Literal

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
    max_steps: int = 8,
    k: int = 10,
) -> AnswerResult:
    atoms = AtomStore()
    result = AnswerResult()
    notes: list[str] = []          # running coverage-gap / step notes for the agent
    verifier = BlockSpanVerifier(source.make_block_loader(tenant_id, workspace_id))

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
        obs = "\n".join(f"{a.atom_id}: {a.text}" for a in atoms.all()) or "(no evidence yet)"
        if mode == "extract":
            # Recovery re-ask: the agent answered with NO grounded claims even though it
            # gathered relevant evidence. Push it to extract what the evidence supports
            # (counters LLM sampling variance where the same question sometimes abstains).
            instr = ("You returned no grounded claims, but you HAVE gathered evidence "
                     "above. Re-examine it and action='answer'. Do NOT search.")
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
        res = await llm.complete(system=system_prompt,
                                 messages=[{"role": "user", "content": user}],
                                 response_format=AgentStep)
        budget.charge(calls=1, tokens=res.output_tokens)
        result.steps += 1
        return res.parsed

    async def _finalize_answer(step: AgentStep) -> None:
        """Apply the answer's claims through the provenance gate, then — if the agent
        emitted NOTHING (0 verified AND 0 rejected) while it had gathered evidence —
        re-ask once to extract what the evidence supports before giving up. This targets
        the observed variance where the same question sometimes abstains despite good
        evidence; it never fires when the agent already produced or attempted claims."""
        _apply_answer(step)
        if (not result.verified_claims and not result.rejected_claims
                and atoms.all() and not budget.exhausted):
            try:
                budget.reserve()
                result.retried_empty = True          # observability: the recovery fired
                retry = await _ask(mode="extract")
                if retry.action == "answer":
                    _apply_answer(retry)
            except BudgetExceeded:
                pass

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
        step: AgentStep = await _ask(mode="force" if force else "step")

        if step.action == "search":
            q = step.query or question
            base_req = RetrievalRequest(
                query=q, tenant_id=tenant_id, workspace_id=workspace_id,
                query_embedding=list(embedder.embed([q])[0]), k=k,
            )
            # agent reformulations → multi-query fusion (recall); else a single search
            if step.queries:
                hits = await multi_query_retrieve(source, base_req, step.queries, embedder=embedder)
            else:
                hits = await source.search(base_req)
            before = len(atoms.all())
            atoms.add_hits(hits)
            stale_searches = stale_searches + 1 if len(atoms.all()) == before else 0

            # vertical gating: surface a real coverage gap so the agent reaches for
            # other sources or answers honestly instead of guessing.
            if gating is not None:
                gap = gating.coverage_gap(q, hits)
                if gap:
                    result.coverage_gaps.append(gap)
                    notes.append(f"COVERAGE GAP: {gap} — use another source or say so; do not guess.")
            continue

        # action == "answer": provenance hard gate (+ recovery re-ask if it abstained)
        await _finalize_answer(step)
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

    # Compose a synthesized answer FROM the verified findings only (factra "living
    # answer" model). Grounded by construction: the composer sees only the verified
    # findings and must reference them [n]; it may not add outside facts. A vertical
    # may supply an optional `answer_format` directive (domain-owned) that shapes the
    # structure — the kernel stays domain-free and only threads the string through.
    if result.verified_claims and not budget.exhausted:
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

        try:
            budget.reserve()
            parsed = await _compose(answer_format)
            text = parsed.answer.strip()
            # Domain-free provenance check: if a structured directive produced an
            # answer with a bad/absent [n] reference, fall back once to the plain
            # (directive-free) compose — the proven-safe path — when budget allows.
            if answer_format and not _refs_valid(text, n_findings) and not budget.exhausted:
                budget.reserve()
                parsed = await _compose(None)
                text = parsed.answer.strip()
            result.composed_answer = text
            # Honesty signal → coverage gap: a "grounded-on-analogues" answer still flags the gap,
            # so the UI shows the prominent fill-the-gaps affordance (LLM-owned judgment, no regex).
            if parsed.directly_addresses is False and (parsed.gap_note or "").strip():
                result.coverage_gaps.append(parsed.gap_note.strip())
        except Exception:
            # Composition is best-effort enrichment over already-verified findings;
            # its failure must never drop the grounded answer/findings.
            pass

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
