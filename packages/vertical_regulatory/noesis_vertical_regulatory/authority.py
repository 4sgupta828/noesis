"""RegulatoryAuthorityPolicy — lifecycle/authority ordering (real, not trivial).

Encodes which document families are controlling vs. proposal-grade, so a
proposed value never outranks an approved one (the thing that catches "a Staff
proposal answering an approved-order question"). Consumed by the verification
gate's criteria in P3b; declared here as the vertical's authority contract.
"""
from __future__ import annotations

# higher rank = more authoritative / controlling
_RANK: dict[str, int] = {
    "application": 1,
    "testimony": 1,
    "staff_report": 2,
    "stipulation": 3,
    "order": 4,        # Commission order = controlling
}

PROPOSAL_GRADE = frozenset({"application", "testimony", "staff_report"})


class RegulatoryAuthorityPolicy:
    def rank(self, doc_family: str) -> int:
        return _RANK.get(doc_family, 0)

    def outranks(self, a: str, b: str) -> bool:
        return self.rank(a) > self.rank(b)

    def is_controlling(self, doc_family: str) -> bool:
        return doc_family not in PROPOSAL_GRADE and self.rank(doc_family) > 0
