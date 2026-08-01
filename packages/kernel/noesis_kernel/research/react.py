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


# ---- results -------------------------------------------------------------

@dataclass
class VerifiedClaim:
    text: str
    atom_id: str
    quote: str
    source_key: str = ""
    document_title: str = ""


@dataclass
class RejectedClaim:
    text: str
    atom_id: str
    quote: str
    reason: str          # "unknown_atom" | "quote_not_grounded"


@dataclass
class AnswerResult:
    verified_claims: list[VerifiedClaim] = field(default_factory=list)
    rejected_claims: list[RejectedClaim] = field(default_factory=list)
    coverage_gaps: list[str] = field(default_factory=list)   # vertical-signalled gaps
    steps: int = 0
    atoms_gathered: int = 0
    stopped_reason: str = "answered"     # "answered" | "budget" | "max_steps"

    @property
    def grounded(self) -> bool:
        """True iff the run produced ≥1 claim and none were rejected."""
        return bool(self.verified_claims) and not self.rejected_claims


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
    max_steps: int = 8,
    k: int = 10,
) -> AnswerResult:
    atoms = AtomStore()
    result = AnswerResult()
    notes: list[str] = []          # running coverage-gap / step notes for the agent

    for _ in range(max_steps):
        if budget.exhausted:
            result.stopped_reason = "budget"
            break
        try:
            budget.reserve()
        except BudgetExceeded:
            result.stopped_reason = "budget"
            break

        obs = "\n".join(f"{a.atom_id}: {a.text}" for a in atoms.all()) or "(no evidence yet)"
        # One fresh user message per step (all evidence so far). Ends with a user
        # turn — required by chat LLMs — and keeps the agent stateless per step.
        user = (f"Question: {question}\n\nEVIDENCE GATHERED SO FAR:\n{obs}\n\n"
                + ("NOTES:\n" + "\n".join(notes) + "\n\n" if notes else "")
                + "Either action='search' with a query (and optional reformulations in "
                  "'queries') to gather more, or action='answer' with claims — each claim "
                  "citing an atom_id and a verbatim 'quote' from that atom.")
        llm_res = await llm.complete(system=system_prompt,
                                     messages=[{"role": "user", "content": user}],
                                     response_format=AgentStep)
        budget.charge(calls=1, tokens=llm_res.output_tokens)
        result.steps += 1
        step: AgentStep = llm_res.parsed

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
            atoms.add_hits(hits)

            # vertical gating: surface a real coverage gap so the agent reaches for
            # other sources or answers honestly instead of guessing.
            if gating is not None:
                gap = gating.coverage_gap(q, hits)
                if gap:
                    result.coverage_gaps.append(gap)
                    notes.append(f"COVERAGE GAP: {gap} — use another source or say so; do not guess.")
            continue

        # action == "answer": provenance hard gate on every claim
        verifier = BlockSpanVerifier(source.make_block_loader(tenant_id, workspace_id))
        for c in step.claims:
            atom = atoms.get(c.atom_id)
            if atom is None or atom.locator is None:
                result.rejected_claims.append(RejectedClaim(c.text, c.atom_id, c.quote, "unknown_atom"))
            elif verifier.verify(c.quote, atom.locator):
                result.verified_claims.append(VerifiedClaim(
                    c.text, c.atom_id, c.quote, atom.source_key, atom.document_title))
            else:
                result.rejected_claims.append(RejectedClaim(c.text, c.atom_id, c.quote, "quote_not_grounded"))
        result.stopped_reason = "answered"
        break
    else:
        result.stopped_reason = "max_steps"

    result.atoms_gathered = len(atoms.all())
    return result
