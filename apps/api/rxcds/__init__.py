"""Noesis Rx-CDS — a real-time, deterministic prescription-safety sub-app for India.

Tier-1 of the India prescription-CDSS (see learnings/cds-epic-plan.md, Part II): a
sub-second, LLM-free rules engine that checks a prescription for correctness, dosing,
patient-adaptation, cross-comorbidity concurrency (drug-drug / drug-disease), allergy,
banned FDCs, therapeutic duplication and renal/hepatic/pregnancy/age cautions.

Design discipline carried over from the kernel's evidence contract:
  - CONGRUENCE, not just provenance: every finding carries a cited BASIS. A rule with no
    basis cannot produce a finding (enforced in the engine).
  - SILENCE IS NEVER CLEARANCE: missing patient context (unknown eGFR, no allergy list,
    unknown weight) is surfaced as an explicit "could not verify" coverage gap, never as
    an all-clear.
  - EVIDENCE-ANCHORED, not peer-conformity: findings are anchored to guideline/label/rule
    sources, never to "what most prescriptions look like" (the India validity trap).
  - ADVISORY only: the registered practitioner retains authority (CDSCO SaMD / NMC posture).

It is mounted as an additive, isolated router (namespace /rx) — OFF is a true no-op and it
never touches the research/answer path.
"""
from __future__ import annotations

from .routes import build_router, rxcds_enabled

__all__ = ["build_router", "rxcds_enabled"]
