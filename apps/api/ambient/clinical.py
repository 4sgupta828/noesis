"""Clinical-note derivations — turns the engine analysis into the sections of a real encounter note:
follow-up tests/procedures, a medications plan (what / why / how long), non-drug therapy (physical
therapy, rehab, lifestyle), a prescription-coherency check, and illustrative similar-patient precedents.

Deterministic and illustrative. Precedents are SYNTHETIC (no real patient data) and are shown for
context only — the recommendations remain guideline-anchored, not peer-conformity (per cds-epic-plan
Part II: conformity != correctness).
"""
from __future__ import annotations

import hashlib
from typing import Dict, List, Optional

from api.rxcds import data as rxdata

from . import data as adata
from .synthesis import RATIONALE

# --- molecule -> the conditions it typically treats (for coherency + "continue" lines) ----------
INDICATION: Dict[str, List[str]] = {
    "atorvastatin": ["hyperlipidemia", "diabetes", "cad"],
    "lisinopril": ["hypertension", "heart_failure", "ckd"], "ramipril": ["hypertension", "heart_failure", "ckd"],
    "enalapril": ["hypertension", "heart_failure"], "losartan": ["hypertension", "heart_failure", "ckd"],
    "sacubitril/valsartan": ["heart_failure"], "metoprolol": ["heart_failure", "cad", "hypertension", "atrial_fibrillation"],
    "carvedilol": ["heart_failure", "hypertension"], "bisoprolol": ["heart_failure", "hypertension"],
    "spironolactone": ["heart_failure", "hypertension"], "eplerenone": ["heart_failure"],
    "empagliflozin": ["heart_failure", "diabetes", "ckd"], "dapagliflozin": ["heart_failure", "diabetes", "ckd"],
    "metformin": ["diabetes"], "glimepiride": ["diabetes"], "insulin glargine": ["diabetes"],
    "furosemide": ["heart_failure"], "amlodipine": ["hypertension"], "levothyroxine": ["hypothyroidism"],
    "warfarin": ["atrial_fibrillation"], "apixaban": ["atrial_fibrillation"], "rivaroxaban": ["atrial_fibrillation"],
    "dabigatran": ["atrial_fibrillation"], "clopidogrel": ["cad"], "aspirin": ["cad"],
    "sertraline": ["depression"], "escitalopram": ["depression"], "alendronate": ["osteoporosis"],
    "budesonide/formoterol": ["asthma", "copd"], "fluticasone/salmeterol": ["asthma", "copd"],
    "tiotropium": ["copd"], "albuterol": ["asthma", "copd"],
}
# molecule/class -> plain-language indication label + typical duration
_ACUTE = {"amoxicillin", "clavulanic acid", "clarithromycin", "azithromycin", "ciprofloxacin"}
_NSAID = {"ibuprofen", "naproxen", "diclofenac", "aceclofenac"}

# --- follow-up tests / procedures by condition --------------------------------------------------
FOLLOWUP_TESTS: Dict[str, List[str]] = {
    "heart_failure": ["Basic metabolic panel (potassium, renal function)", "Echocardiogram if not recent", "Daily weights"],
    "diabetes": ["HbA1c in ~3 months", "Fasting lipid panel", "Urine albumin-to-creatinine ratio", "Annual retinal exam"],
    "ckd": ["Repeat eGFR and potassium", "Urine albumin-to-creatinine ratio"],
    "hypertension": ["Home blood-pressure log", "Basic metabolic panel"],
    "atrial_fibrillation": ["TSH", "Renal function (for anticoagulant dosing)", "Echocardiogram"],
    "cad": ["Fasting lipid panel", "Consider stress testing if symptomatic"],
    "hyperlipidemia": ["Fasting lipid panel in 6–12 weeks"],
    "asthma": ["Spirometry", "Reassess control (ACT score)"],
    "copd": ["Spirometry", "Reassess exacerbation frequency"],
    "osteoporosis": ["Repeat DEXA in ~2 years", "25-OH vitamin D level"],
    "hypothyroidism": ["TSH in 6–8 weeks after any dose change"],
    "depression": ["Repeat PHQ-9 in 2–4 weeks"],
}
# extra monitoring triggered by a newly-started drug class
DRUG_MONITORING = {
    "mra": "Potassium + creatinine 1–2 weeks after starting/uptitrating an MRA",
    "acei": "Potassium + creatinine 1–2 weeks after starting/uptitrating RAS blockade",
    "sglt2": "Baseline renal function before SGLT2 initiation",
    "statin": "Lipid panel (± LFTs) after statin initiation",
}

# --- non-drug therapy (physical therapy / rehab / lifestyle) by condition -----------------------
NONDRUG: Dict[str, List[str]] = {
    "heart_failure": ["Cardiac rehabilitation referral", "Sodium restriction and fluid awareness"],
    "cad": ["Cardiac rehabilitation referral", "Structured exercise + dietary counseling"],
    "copd": ["Pulmonary rehabilitation referral", "Smoking cessation support"],
    "osteoporosis": ["Weight-bearing and resistance exercise", "Fall-prevention / home-safety review"],
    "diabetes": ["Diabetes self-management education and dietitian referral"],
    "obesity": ["Dietitian referral and structured lifestyle/exercise program"],
    "depression": ["Psychotherapy (CBT) referral"],
    "tobacco_use": ["Behavioral cessation counseling"],
}

# --- illustrative precedents (synthetic similar-patient prescriptions) ---------------------------
PRECEDENT_RX: Dict[str, str] = {
    "heart_failure": "ACEi/ARNI + beta-blocker + MRA + SGLT2 inhibitor (four-pillar GDMT)",
    "diabetes": "Metformin + SGLT2 inhibitor + statin",
    "cad": "High-intensity statin + aspirin ± beta-blocker",
    "atrial_fibrillation": "DOAC (apixaban) + rate control (metoprolol)",
    "hypertension": "ACEi or ARB ± amlodipine",
    "ckd": "ACEi/ARB + SGLT2 inhibitor; avoid NSAIDs",
    "hyperlipidemia": "High-intensity statin",
    "asthma": "ICS-containing controller + as-needed reliever",
    "copd": "Long-acting bronchodilator (LAMA) ± ICS",
    "osteoporosis": "Bisphosphonate + calcium/vitamin D",
    "depression": "SSRI + psychotherapy",
    "hypothyroidism": "Levothyroxine titrated to TSH",
}
_DOCTORS = ["Dr. A. Rao", "Dr. M. Chen", "Dr. S. Patel", "Dr. J. Okafor", "Dr. L. Nguyen", "Dr. R. Kapoor",
            "Dr. E. Martinez", "Dr. K. Sharma", "Dr. T. Ibrahim", "Dr. P. Andersson"]


def _seed(s: str) -> int:
    return int(hashlib.md5(s.encode()).hexdigest(), 16)


def precedents(primary_condition: Optional[str], age, sex: Optional[str]) -> Dict:
    if not primary_condition or primary_condition not in PRECEDENT_RX or age is None:
        return {}
    rx = PRECEDENT_RX[primary_condition]
    band_lo, band_hi = int(age) - 5, int(age) + 5
    sx = (sex or "").lower()
    sx_label = {"male": "M", "female": "F"}.get(sx, "—")
    rows = []
    for i in range(3):
        h = _seed(f"{primary_condition}|{age}|{sex}|{i}")
        a = band_lo + (h % (max(1, band_hi - band_lo)))
        rows.append({"patient": f"{sx_label} {a}", "prescription": rx, "doctor": _DOCTORS[h % len(_DOCTORS)]})
    return {"cohort": f"{sx_label}, {band_lo}–{band_hi}y, {adata.CONDITIONS.get(primary_condition, {}).get('label', primary_condition)}",
            "rows": rows,
            "note": "Illustrative synthetic cohort — not real patient records. Shown for context only; "
                    "the recommendations above are guideline-anchored, not based on peer prescribing."}


# --- builders -----------------------------------------------------------------------------------

def _duration_for(molecules: List[str]) -> str:
    if any(m in _ACUTE for m in molecules):
        return "short course — complete as directed"
    if any(m in _NSAID for m in molecules):
        return "shortest effective duration"
    return "ongoing (chronic)"


def build(conds: List[Dict], meds: List[Dict], present_classes: set, gaps: Dict,
          patient, primary_condition: Optional[str]) -> Dict:
    active = [c["condition"] for c in conds]
    active_set = set(active)

    # --- coherency: does each current med have a documented indication among the problems? ---
    coherency = []
    for md in meds:
        inds = set()
        for mol in md["molecules"]:
            inds |= set(INDICATION.get(mol, []))
        matched = sorted(inds & active_set)
        coherency.append({
            "med": md["mention"], "molecules": md["molecules"],
            "indication_present": bool(matched) or not inds,  # unknown-indication drugs aren't flagged
            "matched": [adata.CONDITIONS.get(c, {}).get("label", c) for c in matched],
            "note": ("" if matched else ("no documented indication among the problems — confirm why it is prescribed"
                                         if inds else "")),
        })

    # --- medications plan: continue / start / hold, each with why + duration ---
    medications = {"continue": [], "start": [], "hold": []}
    for md in meds:
        inds = set()
        for mol in md["molecules"]:
            inds |= set(INDICATION.get(mol, []))
        matched = sorted(inds & active_set)
        why = ("for " + ", ".join(adata.CONDITIONS.get(c, {}).get("label", c) for c in matched)) if matched else "review indication"
        medications["continue"].append({"med": md["mention"], "why": why, "duration": _duration_for(md["molecules"])})
    for g in gaps["gaps"]:
        caution = g.get("caution")
        if caution and caution["level"] == "hold":
            medications["hold"].append({"med": g["label"], "why": caution["reason"]})
        else:
            medications["start"].append({"med": g["label"],
                                         "why": RATIONALE.get(g["id"], g["note"]) + (
                                             f" — confirm first: {caution['reason']}" if caution else ""),
                                         "duration": "ongoing (chronic)"})

    # --- follow-up tests/procedures (by condition + drug monitoring for started meds) ---
    follow_up = []
    seen = set()
    for c in active:
        for t in FOLLOWUP_TESTS.get(c, []):
            if t not in seen:
                seen.add(t); follow_up.append(t)
    started_classes = set()
    for g in gaps["gaps"]:
        if not (g.get("caution") and g["caution"]["level"] == "hold"):
            started_classes |= set(g.get("need_any", []))
    for cls, msg in DRUG_MONITORING.items():
        if cls in started_classes and msg not in seen:
            seen.add(msg); follow_up.append(msg)

    # --- non-drug / physical therapy ---
    non_drug = []
    for c in active:
        for n in NONDRUG.get(c, []):
            if n not in non_drug:
                non_drug.append(n)

    return {
        "coherency": coherency,
        "medications": medications,
        "follow_up": follow_up,
        "non_drug": non_drug,
        "precedents": precedents(primary_condition, getattr(patient, "age_years", None), getattr(patient, "sex", None)),
    }
