"""Re-authored QA scorer — generic, domain-free, pure math (no I/O, no DB).

Kept from the prior system's qa scorer: value-present (with the standalone-number
guard so "3.8" doesn't match inside "13.8"), forbidden-values-absent, required/
forbidden phrases, refused-correctly, answered, and citation-grounded.

REMOVED (were welded to the regulatory OH cutover): the corpus-vs-ingest recall
gate, `state_bleed`, and `LEGAL_SOURCE_FAMILIES`-in-core. Attribution to a
required source class is now a GENERIC citation constraint the vertical supplies
per case (facet requirement), not a hardcoded legal-family gate.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

_NORM_STRIPS = re.compile(r"[\$,%]")
# A numeric token: leading digit, optional thousands/decimals, optional percent.
_NUM_TOKEN = re.compile(r"\d[\d,]*(?:\.\d+)?%?")


@dataclass(frozen=True)
class QaClaim:
    text: str
    verified: bool                       # produced by the vertical CitationVerifier
    citation_facets: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class QaAnswer:
    prose: str
    refused: bool = False
    claims: tuple[QaClaim, ...] = ()


@dataclass(frozen=True)
class QaCase:
    id: str
    expect_kind: str = "value"           # "value" | "refuse" | "preservation"
    expected_values: tuple[str, ...] = ()
    forbidden_values: tuple[str, ...] = ()
    required_phrases: tuple[str, ...] = ()
    forbidden_phrases: tuple[str, ...] = ()
    must_be_grounded: bool = True
    # Each constraint: a facet map a cited claim must ⊇ (generic source-class etc).
    citation_constraints: tuple[dict[str, str], ...] = ()
    category: str = ""


@dataclass
class QaScore:
    case_id: str
    values_present: bool
    forbidden_values_absent: bool
    phrases_ok: bool
    refused_correctly: bool
    answered: bool
    citation_grounded: bool
    fully_correct: bool


def _norm_num(s: str) -> str:
    return _NORM_STRIPS.sub("", s.strip().lower())


def _value_present(prose: str, value: str) -> bool:
    """Standalone match: `3.8` must NOT match inside `13.8` / `3.85`.

    Numeric values are compared against whole numeric TOKENS extracted from the
    prose (so a trailing sentence period isn't mistaken for a decimal). Non-numeric
    values fall back to a word-boundary substring match.
    """
    v = _norm_num(value)
    if not v:
        return False
    if any(ch.isdigit() for ch in v):
        return any(_norm_num(tok) == v for tok in _NUM_TOKEN.findall(prose))
    return re.search(rf"\b{re.escape(v)}\b", prose.lower()) is not None


def _facets_satisfy(have: dict[str, str], want: dict[str, str]) -> bool:
    return all(have.get(k) == v for k, v in want.items())


def score_qa(case: QaCase, answer: QaAnswer) -> QaScore:
    prose = answer.prose or ""
    low = prose.lower()

    values_present = all(_value_present(prose, v) for v in case.expected_values)
    forbidden_values_absent = not any(_value_present(prose, v) for v in case.forbidden_values)
    phrases_ok = (
        all(p.lower() in low for p in case.required_phrases)
        and not any(p.lower() in low for p in case.forbidden_phrases)
    )

    should_refuse = case.expect_kind == "refuse"
    refused_correctly = (answer.refused == should_refuse)
    answered = answer.refused is False if not should_refuse else True

    # Grounding: when we answered and grounding is required, every claim must be
    # verified AND every declared citation constraint met by some verified claim.
    if should_refuse or not case.must_be_grounded:
        citation_grounded = True
    else:
        all_verified = bool(answer.claims) and all(c.verified for c in answer.claims)
        constraints_met = all(
            any(c.verified and _facets_satisfy(c.citation_facets, want) for c in answer.claims)
            for want in case.citation_constraints
        )
        citation_grounded = all_verified and constraints_met

    if should_refuse:
        fully_correct = refused_correctly
    else:
        fully_correct = (
            values_present
            and forbidden_values_absent
            and phrases_ok
            and refused_correctly
            and answered
            and citation_grounded
        )

    return QaScore(
        case_id=case.id,
        values_present=values_present,
        forbidden_values_absent=forbidden_values_absent,
        phrases_ok=phrases_ok,
        refused_correctly=refused_correctly,
        answered=answered,
        citation_grounded=citation_grounded,
        fully_correct=fully_correct,
    )
