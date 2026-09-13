"""Noesis Ambient CDS — encounter-intelligence sub-app (US + India modes, one core).

The differentiated layer that rides ON TOP of an ambient scribe (see learnings/cds-epic-plan.md
Part III). It does NOT try to be the note-taker; it is the safety-and-correctness brain over the
encounter:
  PRE-VISIT   — a grounded patient brief + evidence-anchored care gaps.
  ENCOUNTER   — real-time CDS: drug-safety (reuses the shipped Rx-CDS engine) + guideline care-gap
                prompts, every item cited, abstaining when it can't verify.
  POST-VISIT  — a transcript-grounded assessment/plan + DEFENSIBLE coding (US) or a patient
                summary (India). Each clinical line links to the transcript span it came from
                (Linked-Evidence parity) or is marked clinical inference.

Two modes, one core: US and India share the extraction + safety + care-gap engine; they differ
only in vocabulary (US generics vs Indian brands), guideline flavour, and the post-visit output
(US coding vs India summary) + the regulatory disclaimer. The note-taker itself (ASR + prose) is
a BUY/partner component and is deliberately out of scope here (evaluating/correcting a third-party
note is the planned next layer).

Mounted as an additive, isolated router under /ambient. OFF (NOESIS_AMBIENT=0) is a true no-op.
"""
from __future__ import annotations

from .routes import build_router, ambient_enabled

__all__ = ["build_router", "ambient_enabled"]
