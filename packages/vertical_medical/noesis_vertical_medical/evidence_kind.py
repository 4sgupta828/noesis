"""Deterministic evidence-kind classifier — facets → the `authority.py` evidence pyramid.

STRUCTURAL, not semantic (Rule 18): this maps computable per-source metadata that the connectors
already emit (`source_kind`, `pub_type`, `study_type`, `phase`, `year`) onto the evidence-tier
vocabulary `MedicalAuthorityPolicy` ranks. It makes NO judgment about MEANING — it reads structured
tags a source published about itself. Unknown/ambiguous → "" (rank 0), so a missing tag never boosts
NOR demotes a finding below its retrieval-relevance baseline (fail-safe: absence ≠ weakness).

This is the primitive Phase-1 evidence-fitness builds on: retrieval ranking boosts by tier (Part A),
and the held-out eval's `evidence_floor` checks the top cited finding meets a tier (Part B).
"""
from __future__ import annotations


def classify(source_key: str, facets: dict[str, str] | None) -> str:
    """Return an `authority.py` evidence-kind key (or "" when unclassifiable).

    Precedence: an explicit publication/study TYPE wins over a source default, because a systematic
    review indexed via EuropePMC is stronger than the "article" source default.
    """
    f = facets or {}
    sk = (source_key or "").lower()
    src_kind = (f.get("source_kind") or "").lower()
    pub = (f.get("pub_type") or "").lower()
    study = (f.get("study_type") or "").lower()

    # 1) Literature publication type is the most specific structural signal (EuropePMC etc.).
    if pub:
        if "systematic" in pub or "meta-analysis" in pub or "meta analysis" in pub:
            return "systematic_review"
        if "randomized" in pub or "randomised" in pub or "rct" in pub:
            return "rct"
        if "cohort" in pub or "case-control" in pub or "case control" in pub:
            return "cohort"
        if "cross-sectional" in pub or "cross sectional" in pub:
            return "cross_sectional"
        if "case series" in pub:
            return "case_series"
        if "case report" in pub:
            return "case_report"
        # any other pub_type (e.g. "journal-article", "review") is too generic to grade → fall through

    # 2) Trial registry: interventional = RCT-graded (weight by phase in the ranker); else observational.
    if sk == "clinicaltrials" or study:
        return "rct" if study == "interventional" else ("cohort" if study else "rct")

    # 3) Source-default tiers for normative / regulatory / surveillance sources.
    if src_kind == "drug_label" or sk in ("openfda", "dailymed"):
        return "guideline"        # a regulatory label is normative for use/contraindications
    if src_kind == "public_health" or sk == "cdc":
        return "guideline"        # CDC/public-health guidance is normative
    if src_kind == "adverse_event" or sk == "faers":
        return "cohort"           # pharmacovigilance = observational safety signal

    return ""                     # unknown → rank 0 (never boosts, never demotes)


def recency_year(facets: dict[str, str] | None) -> int | None:
    """Extract a 4-digit publication/trial year from facets (structural), or None."""
    raw = (facets or {}).get("year")
    if raw is None:
        return None
    s = str(raw).strip()[:4]
    return int(s) if s.isdigit() and len(s) == 4 else None
