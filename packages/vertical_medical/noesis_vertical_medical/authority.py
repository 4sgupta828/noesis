"""Medical authority policy — the evidence pyramid.

Controls which evidence outranks which (systematic review > RCT > cohort >
case report), plus trial-specific grading (completed-with-results > phase 3 >
earlier phase). Under the evidence-fitness flag, `rank()` is consumed by the
research loop's relevance-selection step (`_rank_claims_by_relevance`) as a
bounded, boost-only tier signal — so a stronger-tier finding surfaces into the
compose cap ahead of a similarly-relevant weaker one. It never gates the span/
entailment provenance checks (those are tier-agnostic).
"""
from __future__ import annotations

# higher = stronger evidence
_RANK: dict[str, int] = {
    "case_report": 1,
    "case_series": 2,
    "cross_sectional": 3,
    "cohort": 4,
    "rct": 5,
    "systematic_review": 6,   # apex (Cochrane et al.)
    "guideline": 6,           # controlling for practice
}

# ClinicalTrials.gov phase → evidence weight (interventional trials)
_PHASE_RANK = {"phase4": 4, "phase3": 3, "phase2": 2, "phase1": 1, "na": 0, "": 0}


class MedicalAuthorityPolicy:
    def rank(self, evidence_kind: str) -> int:
        return _RANK.get(evidence_kind, 0)

    def outranks(self, a: str, b: str) -> bool:
        return self.rank(a) > self.rank(b)

    def phase_weight(self, phase: str) -> int:
        return _PHASE_RANK.get(phase.replace(" ", "").lower(), 0)

    def is_controlling(self, evidence_kind: str) -> bool:
        return evidence_kind in ("systematic_review", "guideline")
