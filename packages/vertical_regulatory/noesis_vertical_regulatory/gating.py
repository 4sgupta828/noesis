"""RegulatoryGatingPolicy — a REAL gating policy (not always-False/None).

Domain-format logic (docket regex, jurisdiction) lives HERE, never in the kernel
loop. The semantic verdict stays LLM-run in the kernel; this decides scope.
"""
from __future__ import annotations

from noesis_kernel.contract.dto import BlockHit

from . import entities
from .scope import SCOPE_DIMENSION, normalize_jurisdiction

# plan keys that make a question "bindable" to the corpus (worth the hard gate).
_BINDABLE_KEYS = ("docket", "jurisdiction", "year", "utility", "case_number")


class RegulatoryGatingPolicy:
    def gate_applies(self, question: str, plan: dict) -> bool:
        if entities.looks_like_docket(question):
            return True
        return any(plan.get(k) for k in _BINDABLE_KEYS)

    def claim_in_scope(self, claim: object, cited_hits: list[BlockHit]) -> bool:
        # Corpus-grounded claims face the gate; a claim citing nothing does not.
        return bool(cited_hits)

    def coverage_gap(self, question: str, hits: list[BlockHit]) -> str | None:
        """If the question names a jurisdiction no retrieved hit covers, that's a
        real coverage gap — answer honestly instead of guessing.

        NOTE (Rule 18): scope should come from the LLM-extracted, allowlist-
        validated plan, not from scanning free text (the word "in" is not
        Indiana). As a demo shortcut we match only an explicit uppercase 2-letter
        CODE (a format, not a semantic guess); production reads it from the plan.
        """
        asked = None
        for raw in question.replace(",", " ").split():
            tok = raw.strip(".,?!;:")
            if len(tok) == 2 and tok.isupper() and normalize_jurisdiction(tok):
                asked = tok
                break
        if asked is None:
            return None
        covered = {h.facets.get(SCOPE_DIMENSION) for h in hits}
        if asked not in covered:
            return f"no evidence for jurisdiction {asked} in the corpus"
        return None
