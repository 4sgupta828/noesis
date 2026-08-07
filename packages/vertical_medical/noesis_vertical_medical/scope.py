"""Medical scope model — condition (disease area) is the primary narrowing dim.

Medical scope is the CONDITION the
question is about. The validator is permissive (free-text condition), lowercased;
routing/coverage keys on it. A closed ontology (MeSH/SNOMED) would replace the
free-text normalize once the terminology backbone is wired.
"""
from __future__ import annotations

SCOPE_DIMENSION = "condition"


def normalize_condition(value: str) -> str:
    return value.strip().lower()


def validate_scope(scope: dict[str, str]) -> dict[str, str]:
    out: dict[str, str] = {}
    c = scope.get(SCOPE_DIMENSION)
    if c and c.strip():
        out[SCOPE_DIMENSION] = normalize_condition(c)
    return out
