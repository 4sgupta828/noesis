"""Regulatory entity taxonomy (declared data).

The kernel only knows Source/Document/Entity abstractly; this declares the
regulatory concrete types and their relationships. A docket-number format lives
here (a structural regex on a domain FORMAT is allowed — Rule 18 — as long as
it's in the vertical, not the kernel).
"""
from __future__ import annotations

import re

# Entity types the regulatory vertical declares.
ENTITY_TYPES: tuple[str, ...] = ("case", "filing", "party")

# Relationships (parent → children), for the entity taxonomy.
RELATIONSHIPS: dict[str, tuple[str, ...]] = {
    "case": ("filing", "party"),
    "filing": (),
    "party": (),
}

# PUCO-style docket number format, e.g. "24-1009-EL-AIR". Structural, vertical-local.
DOCKET_RE = re.compile(r"\b\d{2}-\d{3,5}-[A-Za-z]{2}-[A-Za-z]{3}\b")


def looks_like_docket(text: str) -> bool:
    return DOCKET_RE.search(text) is not None
