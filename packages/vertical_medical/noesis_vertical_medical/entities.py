"""Medical entity taxonomy (declared data). Vocabulary lives here, not the kernel."""
from __future__ import annotations

import re

ENTITY_TYPES: tuple[str, ...] = ("trial", "intervention", "condition", "drug", "guideline")

RELATIONSHIPS: dict[str, tuple[str, ...]] = {
    "trial": ("intervention", "condition"),
    "condition": (),
    "intervention": (),
    "drug": (),
    "guideline": (),
}

# ClinicalTrials.gov registry id format (structural — vertical-local, allowed).
NCT_RE = re.compile(r"\bNCT\d{8}\b")


def looks_like_nct(text: str) -> bool:
    return NCT_RE.search(text) is not None
