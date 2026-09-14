"""Illustrative clinical knowledge for the ambient care-gap + coding engine — SEED DATA.

⚠️  ILLUSTRATIVE SEED, NOT A LICENSED GUIDELINE/CODING DATABASE. ⚠️
Production binds care-gap logic to a licensed/curated guideline corpus (the Noesis evidence engine)
and coding to a licensed grouper (ICD-10-CM / CMS-HCC). Every entry carries a `basis` citation so the
engine can enforce its congruence rule (no finding without a cited basis). See cds-epic-plan.md Part III.

Drug→class resolution is REUSED from the Rx-CDS engine (`api.rxcds.data.MOLECULE_CLASSES`); this file
adds only the condition vocabulary, the care-gap rules, and coding hints on top of it.
"""
from __future__ import annotations

from typing import Dict, List

# --- Condition vocabulary: transcript/keyword -> canonical condition -----------
# canonical -> {label, keywords, icd10 (US coding hint), display}
CONDITIONS: Dict[str, Dict] = {
    "heart_failure": {"label": "Heart failure (reduced EF)",
                      "keywords": ["heart failure", "hfref", "chf", "hf", "systolic heart failure", "reduced ejection", "hf with reduced"],
                      "icd10": {"code": "I50.22", "desc": "Chronic systolic (congestive) heart failure"}},
    "diabetes": {"label": "Type 2 diabetes mellitus",
                 "keywords": ["diabetes", "t2dm", "type 2 diabet", "diabetic", "a1c", "hba1c"],
                 "icd10": {"code": "E11.9", "desc": "Type 2 diabetes mellitus without complications"}},
    "hypertension": {"label": "Essential hypertension",
                     "keywords": ["hypertension", "high blood pressure", "htn", "elevated blood pressure"],
                     "icd10": {"code": "I10", "desc": "Essential (primary) hypertension"}},
    "ckd": {"label": "Chronic kidney disease",
            "keywords": ["chronic kidney", "ckd", "renal impairment", "reduced egfr", "kidney disease"],
            "icd10": {"code": "N18.9", "desc": "Chronic kidney disease, unspecified"}},
    "tobacco_use": {"label": "Tobacco use",
                    "keywords": ["tobacco", "smoking", "smoker", "smokes", "cigarette", "nicotine"],
                    "icd10": {"code": "Z72.0", "desc": "Tobacco use"}},
    "hyperlipidemia": {"label": "Hyperlipidemia",
                       "keywords": ["hyperlipidemia", "high cholesterol", "dyslipidemia", "elevated ldl"],
                       "icd10": {"code": "E78.5", "desc": "Hyperlipidemia, unspecified"}},
}

# --- Care-gap rules: guideline-recommended therapy/action a patient should have --
# Each rule: {id, condition, label, kind: "drug"|"action",
#             need_any (therapy classes that satisfy it, for drug rules),
#             severity, basis, note}
# A DRUG rule is a GAP when the patient is on NONE of `need_any`. An ACTION rule is always surfaced
# as a to-confirm (we cannot verify it was done from the med list) — shown as a prompt, not an alarm.
CARE_GAPS: List[Dict] = [
    # Heart-failure GDMT — the four pillars
    {"id": "hf_renin", "condition": "heart_failure", "kind": "drug",
     "label": "Renin-angiotensin inhibition (ACEi / ARB / ARNI)", "need_any": ["acei", "arb", "arni"],
     "severity": "major", "note": "A GDMT pillar for HFrEF; ARNI preferred where tolerated.",
     "basis": {"source": "ACC/AHA/HFSA HF guideline", "citation": "GDMT: RAS inhibition in HFrEF — illustrative."}},
    {"id": "hf_bb", "condition": "heart_failure", "kind": "drug",
     "label": "Evidence-based beta-blocker (carvedilol / metoprolol succinate / bisoprolol)", "need_any": ["gdmt-betablocker"],
     "severity": "major", "note": "A GDMT pillar; only the three evidence-based agents count.",
     "basis": {"source": "ACC/AHA/HFSA HF guideline", "citation": "GDMT: evidence-based beta-blocker in HFrEF — illustrative."}},
    {"id": "hf_mra", "condition": "heart_failure", "kind": "drug",
     "label": "Mineralocorticoid receptor antagonist (spironolactone / eplerenone)", "need_any": ["mra"],
     "severity": "major", "note": "A GDMT pillar; monitor potassium/renal function.",
     "basis": {"source": "ACC/AHA/HFSA HF guideline", "citation": "GDMT: MRA in HFrEF — illustrative."}},
    {"id": "hf_sglt2", "condition": "heart_failure", "kind": "drug",
     "label": "SGLT2 inhibitor (dapagliflozin / empagliflozin)", "need_any": ["sglt2"],
     "severity": "major", "note": "A GDMT pillar; benefits HFrEF regardless of diabetes status.",
     "basis": {"source": "ACC/AHA/HFSA HF guideline", "citation": "GDMT: SGLT2 inhibitor in HFrEF — illustrative."}},
    # Diabetes
    {"id": "dm_statin", "condition": "diabetes", "kind": "drug",
     "label": "Statin for cardiovascular risk reduction", "need_any": ["statin"],
     "severity": "moderate", "note": "Recommended for most adults with diabetes for ASCVD risk.",
     "basis": {"source": "ADA Standards of Care", "citation": "Statin therapy in diabetes — illustrative."}},
    {"id": "dm_sglt2_organ", "condition": "diabetes", "kind": "drug",
     "label": "SGLT2 inhibitor for cardiorenal protection", "need_any": ["sglt2"],
     "severity": "moderate", "note": "Preferred where HF or CKD coexists (organ protection beyond glucose).",
     "basis": {"source": "ADA / KDIGO", "citation": "SGLT2 inhibitor for cardiorenal protection in diabetes — illustrative."},
     "boost_if_condition": ["heart_failure", "ckd"]},
    {"id": "dm_a1c", "condition": "diabetes", "kind": "action",
     "label": "Confirm HbA1c checked and at individualized target",
     "severity": "info", "note": "Cannot be verified from the medication list — confirm.",
     "basis": {"source": "ADA Standards of Care", "citation": "HbA1c monitoring — illustrative."}},
    # CKD
    {"id": "ckd_renin", "condition": "ckd", "kind": "drug",
     "label": "ACEi/ARB if albuminuria present", "need_any": ["acei", "arb", "arni"],
     "severity": "moderate", "note": "Renoprotective with albuminuria; confirm albuminuria + potassium.",
     "basis": {"source": "KDIGO", "citation": "RAS blockade in albuminuric CKD — illustrative."}},
    # Tobacco
    {"id": "tob_cessation", "condition": "tobacco_use", "kind": "action",
     "label": "Offer tobacco-cessation counseling + pharmacotherapy",
     "severity": "moderate", "note": "Brief counseling + pharmacotherapy at every visit.",
     "basis": {"source": "USPSTF", "citation": "Tobacco cessation intervention — illustrative."}},
]

# --- Post-discharge transitions-of-care actions (fire when recent_hospitalization) --
TRANSITION_ACTIONS: List[Dict] = [
    {"id": "toc_medrec", "kind": "action", "severity": "moderate",
     "label": "Complete medication reconciliation after hospitalization",
     "note": "Discharge med changes are a common source of error — reconcile against the current list.",
     "basis": {"source": "Transitions-of-care guidance", "citation": "Post-discharge medication reconciliation — illustrative."}},
    {"id": "toc_followup", "kind": "action", "severity": "moderate",
     "label": "Ensure timely post-discharge follow-up (≈7–14 days)",
     "note": "Early follow-up reduces readmission after a heart-failure hospitalization.",
     "basis": {"source": "Transitions-of-care guidance", "citation": "Early post-discharge follow-up — illustrative."}},
]

# --- Guideline strength (Class of Recommendation) per care-gap rule — illustrative --------------
STRENGTH: Dict[str, str] = {
    "hf_renin": "Class I", "hf_bb": "Class I", "hf_mra": "Class I", "hf_sglt2": "Class I",
    "dm_statin": "Class I", "dm_sglt2_organ": "Class I", "dm_a1c": "Class I",
    "ckd_renin": "Class I", "tob_cessation": "Class I",
    "toc_medrec": "Class I", "toc_followup": "Class I",
}

# --- Vitals / labs extraction (regex over the transcript) ------------------------------------
# name -> {pattern, unit, kind}. Patterns capture a numeric value near a cue. Values are transcript-
# linked and drive threshold-aware contraindication checks (see contraindications.py).
LAB_PATTERNS: Dict[str, Dict] = {
    "bp": {"regex": r"(?:blood pressure|bp)\D{0,14}(\d{2,3})\s*/\s*(\d{2,3})", "unit": "mmHg", "kind": "bp"},
    "hr": {"regex": r"(?:heart rate|pulse|hr)\D{0,14}(\d{2,3})\b", "unit": "bpm", "kind": "num"},
    "egfr": {"regex": r"(?:egfr|gfr)\D{0,14}(\d{1,3})\b", "unit": "mL/min/1.73m2", "kind": "num"},
    "potassium": {"regex": r"(?:potassium|k\+|serum k)\D{0,14}(\d\.\d)\b", "unit": "mmol/L", "kind": "num"},
    "a1c": {"regex": r"(?:hba1c|a1c)\D{0,14}(\d{1,2}(?:\.\d)?)\b", "unit": "%", "kind": "num"},
    "ldl": {"regex": r"(?:ldl)\D{0,14}(\d{2,3})\b", "unit": "mg/dL", "kind": "num"},
    "ef": {"regex": r"(?:ejection fraction|ef)\D{0,14}(\d{1,2})\s*%?", "unit": "%", "kind": "num"},
}

# Therapy classes the care-gap engine cares about (for the "present therapies" readout)
GDMT_CLASSES = ["acei", "arb", "arni", "gdmt-betablocker", "mra", "sglt2", "statin"]
CLASS_LABEL = {
    "acei": "ACE inhibitor", "arb": "ARB", "arni": "ARNI", "gdmt-betablocker": "beta-blocker (GDMT)",
    "mra": "MRA", "sglt2": "SGLT2 inhibitor", "statin": "statin",
}
