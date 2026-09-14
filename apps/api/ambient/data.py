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
    "atrial_fibrillation": {"label": "Atrial fibrillation",
                            "keywords": ["atrial fibrillation", "afib", "a-fib", "a fib"],
                            "icd10": {"code": "I48.91", "desc": "Unspecified atrial fibrillation"}},
    "cad": {"label": "Coronary artery disease / ASCVD",
            "keywords": ["coronary artery", "coronary disease", "cad", "post-mi", "post mi",
                         "myocardial infarction", "heart attack", "angina", "stent", "ascvd", "prior mi"],
            "icd10": {"code": "I25.10", "desc": "ASCVD of native coronary artery without angina"}},
    "asthma": {"label": "Asthma",
               "keywords": ["asthma", "asthmatic"],
               "icd10": {"code": "J45.909", "desc": "Unspecified asthma, uncomplicated"}},
    "copd": {"label": "COPD",
             "keywords": ["copd", "emphysema", "chronic bronchitis"],
             "icd10": {"code": "J44.9", "desc": "COPD, unspecified"}},
    "depression": {"label": "Depression",
                   "keywords": ["depression", "depressed", "major depressive", "mdd", "low mood"],
                   "icd10": {"code": "F32.9", "desc": "Major depressive disorder, single episode, unspecified"}},
    "osteoporosis": {"label": "Osteoporosis",
                     "keywords": ["osteoporosis", "osteoporotic", "fragility fracture", "low bone density"],
                     "icd10": {"code": "M81.0", "desc": "Age-related osteoporosis without fracture"}},
    "hypothyroidism": {"label": "Hypothyroidism",
                       "keywords": ["hypothyroid", "hashimoto", "underactive thyroid"],
                       "icd10": {"code": "E03.9", "desc": "Hypothyroidism, unspecified"}},
    "obesity": {"label": "Obesity",
                "keywords": ["obesity", "obese"],
                "icd10": {"code": "E66.9", "desc": "Obesity, unspecified"}},
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
    # Atrial fibrillation — stroke prophylaxis (only when stroke risk present)
    {"id": "afib_anticoag", "condition": "atrial_fibrillation", "kind": "drug",
     "label": "Oral anticoagulation for stroke prevention", "need_any": ["anticoagulant"],
     "severity": "major", "requires_risk": True,
     "note": "Indicated when CHA2DS2-VASc risk is elevated (age ≥65 or a stroke risk factor); a DOAC is preferred over warfarin for most.",
     "basis": {"source": "AHA/ACC/HRS AF guideline", "citation": "Anticoagulation by CHA2DS2-VASc in AF — illustrative."}},
    # Coronary artery disease / ASCVD
    {"id": "cad_statin", "condition": "cad", "kind": "drug",
     "label": "High-intensity statin", "need_any": ["statin"], "severity": "major",
     "note": "Secondary prevention — a high-intensity statin is guideline-recommended in established ASCVD.",
     "basis": {"source": "ACC/AHA cholesterol guideline", "citation": "High-intensity statin in ASCVD — illustrative."}},
    {"id": "cad_antiplatelet", "condition": "cad", "kind": "drug",
     "label": "Antiplatelet therapy (aspirin or clopidogrel)", "need_any": ["antiplatelet"], "severity": "major",
     "note": "Secondary prevention in established coronary disease.",
     "basis": {"source": "ACC/AHA guideline", "citation": "Antiplatelet in secondary prevention — illustrative."}},
    # Airways
    {"id": "asthma_controller", "condition": "asthma", "kind": "drug",
     "label": "Inhaled controller (ICS-containing)", "need_any": ["inhaled-controller"], "severity": "moderate",
     "note": "All but the mildest asthma needs ICS-containing controller therapy, not just a rescue inhaler.",
     "basis": {"source": "GINA", "citation": "ICS-containing controller in asthma — illustrative."}},
    {"id": "copd_controller", "condition": "copd", "kind": "drug",
     "label": "Inhaled long-acting bronchodilator/controller", "need_any": ["inhaled-controller"], "severity": "moderate",
     "note": "Maintenance inhaled therapy reduces COPD exacerbations.",
     "basis": {"source": "GOLD", "citation": "Long-acting inhaled maintenance in COPD — illustrative."}},
    # Osteoporosis
    {"id": "osteo_therapy", "condition": "osteoporosis", "kind": "drug",
     "label": "Antiresorptive therapy (bisphosphonate)", "need_any": ["bisphosphonate"], "severity": "moderate",
     "note": "Pharmacologic therapy reduces fracture risk in osteoporosis.",
     "basis": {"source": "Endocrine Society / ACP", "citation": "Bisphosphonate in osteoporosis — illustrative."}},
    {"id": "osteo_calvitd", "condition": "osteoporosis", "kind": "action",
     "label": "Ensure adequate calcium + vitamin D", "severity": "info",
     "note": "Adjunct to any antiresorptive therapy.",
     "basis": {"source": "Endocrine Society", "citation": "Calcium/vitamin D in osteoporosis — illustrative."}},
    # Depression / thyroid — confirmations
    {"id": "depression_mgmt", "condition": "depression", "kind": "action",
     "label": "Confirm PHQ-9 severity and a treatment plan (therapy ± SSRI)", "severity": "moderate",
     "note": "Measurement-based care; SSRIs are first-line pharmacotherapy.",
     "basis": {"source": "USPSTF / APA", "citation": "Measurement-based depression care — illustrative."}},
    {"id": "hypothyroid_tsh", "condition": "hypothyroidism", "kind": "action",
     "label": "Confirm TSH monitoring on levothyroxine", "severity": "info",
     "note": "Periodic TSH to confirm the dose is at target.",
     "basis": {"source": "ATA", "citation": "TSH monitoring on levothyroxine — illustrative."}},
]

# --- Age-based preventive actions (fire on patient age, not on a detected condition) -------------
PREVENTION: List[Dict] = [
    {"id": "screen_colon", "kind": "action", "severity": "info", "min_age": 45, "max_age": 75,
     "label": "Confirm colorectal cancer screening is up to date",
     "note": "Average-risk adults 45–75 (colonoscopy or FIT).",
     "basis": {"source": "USPSTF", "citation": "Colorectal cancer screening 45–75 — illustrative."}},
    {"id": "imm_shingles", "kind": "action", "severity": "info", "min_age": 50,
     "label": "Offer recombinant zoster (shingles) vaccine",
     "note": "Recommended for adults ≥50.",
     "basis": {"source": "ACIP", "citation": "Recombinant zoster vaccine ≥50 — illustrative."}},
    {"id": "imm_pneumo", "kind": "action", "severity": "info", "min_age": 65,
     "label": "Offer pneumococcal vaccination",
     "note": "Recommended for adults ≥65 (and younger with risk factors).",
     "basis": {"source": "ACIP", "citation": "Pneumococcal vaccination ≥65 — illustrative."}},
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
    "afib_anticoag": "Class I", "cad_statin": "Class I", "cad_antiplatelet": "Class I",
    "asthma_controller": "Class I", "copd_controller": "Class I", "osteo_therapy": "Class I",
    "depression_mgmt": "Class B (USPSTF)", "screen_colon": "Grade A (USPSTF)",
    "imm_shingles": "ACIP", "imm_pneumo": "ACIP",
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
