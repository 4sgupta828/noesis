"""US and India modes — one core engine, two configurations.

The extraction + drug-safety + care-gap engine is identical across modes. Modes differ only in:
  - guideline flavour (label appended to care-gap sources),
  - the POST-VISIT output: US emits DEFENSIBLE coding (ICD-10 + E/M hint, MEAT-bound); India emits a
    patient summary + national-guideline framing (no HCC/coding),
  - the regulatory disclaimer (US: non-device, reviewable-basis posture; India: advisory SaMD posture).
Vocabulary (US generics vs Indian brands) is handled by the shared Rx-CDS resolver, which knows both.
"""
from __future__ import annotations

from typing import Dict

MODES: Dict[str, Dict] = {
    "US": {
        "label": "United States",
        "guideline_flavor": "US (ACC/AHA, ADA, USPSTF)",
        "post_visit": "coding",   # emit ICD-10 + E/M hint, MEAT-bound
        "disclaimer": (
            "Advisory clinical decision support. Surfaces reviewable options with a transparent, cited "
            "basis so the clinician independently reviews and retains authority (kept informational, not a "
            "directive — FDA non-device posture). Absence of a finding is not clearance. Coding suggestions "
            "are DEFENSIBLE (evidence must be present in the encounter), never maximised. Illustrative seed "
            "knowledge base — not a licensed clinical or coding database."
        ),
    },
    "IN": {
        "label": "India",
        "guideline_flavor": "India (ICMR / NLEM / national programmes) + global",
        "post_visit": "summary",  # patient summary, no HCC coding
        "disclaimer": (
            "Advisory clinical decision support (India). The registered practitioner retains full "
            "authority (CDSCO SaMD / NMC advisory posture). Absence of a finding is not clearance. "
            "Illustrative seed knowledge base — not a licensed clinical database; production requires a "
            "licensed drug-interaction source, the hardened Indian brand normaliser, ABDM/FHIR context, "
            "and DPDP-compliant handling of the encounter."
        ),
    },
}

DEFAULT_MODE = "US"


def resolve_mode(name: str) -> str:
    n = (name or "").strip().upper()
    if n in ("INDIA", "IN"):
        return "IN"
    if n in ("US", "USA", "UNITED STATES"):
        return "US"
    return DEFAULT_MODE
