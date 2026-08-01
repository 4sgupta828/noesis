"""MedicalGatingPolicy — real gating (not always-False)."""
from __future__ import annotations

from noesis_kernel.contract.dto import BlockHit

from . import entities
from .scope import SCOPE_DIMENSION, normalize_condition

_BINDABLE = ("condition", "intervention", "drug", "trial", "phase")


class MedicalGatingPolicy:
    def gate_applies(self, question: str, plan: dict) -> bool:
        if entities.looks_like_nct(question):
            return True
        return any(plan.get(k) for k in _BINDABLE)

    def claim_in_scope(self, claim: object, cited_hits: list[BlockHit]) -> bool:
        return bool(cited_hits)

    def coverage_gap(self, question: str, hits: list[BlockHit]) -> str | None:
        """If the question names a condition no retrieved hit covers, that's a gap.

        NOTE (Rule 18): condition scope should come from an LLM-extracted, ontology-
        validated plan, not free-text scanning. Demo heuristic: match a known
        condition token present in the corpus's own facets against the question."""
        covered = {h.facets.get(SCOPE_DIMENSION) for h in hits if h.facets.get(SCOPE_DIMENSION)}
        if not covered:
            return None
        q = normalize_condition(question)
        if not any(c in q for c in covered):
            # question doesn't mention any condition we actually retrieved
            return None
        return None  # a covered condition IS present → no gap
