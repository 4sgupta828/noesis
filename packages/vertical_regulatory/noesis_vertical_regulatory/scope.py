"""Regulatory scope model — jurisdiction = US state.

Domain vocabulary lives HERE (in the vertical), never in the kernel. The kernel
routes on abstract facets; this module defines what the `jurisdiction` facet
means for the regulatory vertical and validates LLM-produced scope signals
against an allowlist (Rule 18: no regex-guessing of scope — validate against a
known set, fail-safe otherwise).
"""
from __future__ import annotations

SCOPE_DIMENSION = "jurisdiction"

# US state + DC 2-letter codes — the regulatory jurisdiction allowlist.
US_STATES: frozenset[str] = frozenset(
    "AL AK AZ AR CA CO CT DE FL GA HI ID IL IN IA KS KY LA ME MD MA MI MN MS MO "
    "MT NE NV NH NJ NM NY NC ND OH OK OR PA RI SC SD TN TX UT VT VA WA WV WI WY DC".split()
)


def normalize_jurisdiction(value: str) -> str | None:
    """Return the canonical 2-letter code if valid, else None (fail-safe)."""
    v = value.strip().upper()
    return v if v in US_STATES else None


def validate_scope(scope: dict[str, str]) -> dict[str, str]:
    """Keep only allowlisted jurisdiction values; drop anything unrecognized."""
    out: dict[str, str] = {}
    j = scope.get(SCOPE_DIMENSION)
    if j is not None:
        canon = normalize_jurisdiction(j)
        if canon is not None:
            out[SCOPE_DIMENSION] = canon
    return out
