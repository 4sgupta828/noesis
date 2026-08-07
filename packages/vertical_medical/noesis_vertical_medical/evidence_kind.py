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


def _grade_text(s: str) -> str:
    """Map an explicit study-design self-label found in a pub_type OR a title to an authority tier.
    Structural (Rule 18): the work DECLARES its own design ("...: A Systematic Review", pubType
    'Randomized Controlled Trial') — we read that label, we don't infer meaning. Returns "" if none.
    Ordered strongest-first so 'systematic review of randomized trials' grades as the review."""
    if not s:
        return ""
    # Clinical practice guideline / consensus statement = the controlling normative tier. A guideline
    # is a guideline whatever the source (a trusted-domain web AHA/ACC guideline or a Europe PMC
    # guideline article) — reading the declared type, not inferring it (Rule 18).
    if "practice guideline" in s or "clinical guideline" in s or "consensus statement" in s \
            or "guideline for" in s or "guidelines for" in s or "guideline on" in s or "guidelines on" in s \
            or "society guideline" in s or "consensus guideline" in s:
        return "guideline"
    if "systematic review" in s or "meta-analysis" in s or "meta analysis" in s \
            or "cochrane" in s or "network meta" in s:
        return "systematic_review"
    if "randomized controlled trial" in s or "randomised controlled trial" in s \
            or "randomized clinical trial" in s or "randomised clinical trial" in s \
            or "randomized, " in s or "randomised, " in s or "double-blind" in s or "placebo-controlled" in s:
        return "rct"
    if "cohort" in s or "case-control" in s or "case control" in s \
            or "longitudinal study" in s or "prospective study" in s or "registry" in s:
        return "cohort"
    if "cross-sectional" in s or "cross sectional" in s:
        return "cross_sectional"
    if "case series" in s:
        return "case_series"
    if "case report" in s:
        return "case_report"
    return ""


_TIER_RANK = {"systematic_review": 6, "guideline": 6, "rct": 5, "cohort": 4,
              "cross_sectional": 3, "case_series": 2, "case_report": 1}


def strongest_pub_type(pub_types: list[str]) -> str:
    """From a publication-type list, return the one whose declared design grades HIGHEST (so a stored
    facet keeps 'Randomized Controlled Trial' over 'Journal Article'). Falls back to the first if none
    grade. Used at ingest so the corpus captures the discriminating design, not just pubType[0]."""
    if not pub_types:
        return ""
    best, best_rank = pub_types[0], -1
    for pt in pub_types:
        r = _TIER_RANK.get(_grade_text(pt), 0)
        if r > best_rank:
            best, best_rank = pt, r
    return best


def classify(source_key: str, facets: dict[str, str] | None, title: str = "", text: str = "") -> str:
    """Return an `authority.py` evidence-kind key (or "" when unclassifiable).

    Precedence: an explicit publication/study TYPE (pub_type, else the TITLE's self-declared design)
    wins over a source default, because a systematic review indexed via EuropePMC is stronger than the
    generic "article" source default. The title fallback recovers literature whose FIRST stored
    pub_type was generic (EuropePMC stores only pubType[0], often "journal-article").
    """
    f = facets or {}
    sk = (source_key or "").lower()
    src_kind = (f.get("source_kind") or "").lower()
    pub = (f.get("pub_type") or "").lower()
    study = (f.get("study_type") or "").lower()

    # 1) Explicit publication type (most specific), then the title's declared design as a fallback.
    graded = _grade_text(pub) or _grade_text((title or "").lower())
    if graded:
        return graded

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

    # 4) STOPGAP (until EuropePMC is re-ingested with the strongest pubType — see europepmc.py): for
    # existing literature whose stored pub_type is generic and whose title doesn't self-label, read an
    # explicit design declaration from the ABSTRACT. Conservative — only unambiguous phrases; strongest-
    # first via _grade_text. Remove once the corpus carries a gradeable pub_type facet.
    if sk == "europepmc" or src_kind == "article":
        return _grade_text((text or "").lower())

    return ""                     # unknown → rank 0 (never boosts, never demotes)


def recency_year(facets: dict[str, str] | None) -> int | None:
    """Extract a 4-digit publication/trial year from facets (structural), or None."""
    raw = (facets or {}).get("year")
    if raw is None:
        return None
    s = str(raw).strip()[:4]
    return int(s) if s.isdigit() and len(s) == 4 else None
