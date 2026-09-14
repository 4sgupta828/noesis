"""Contraindication / caution checks for care-gap recommendations — the clinical-intelligence layer.

A naive CDS says "start all four heart-failure pillars." A safe one checks each recommendation against
the patient's numbers and comorbidities first: hold an MRA when potassium is high, confirm renal function
before an SGLT2 inhibitor, avoid a beta-blocker in decompensated bradycardia, and so on. This module maps
a care-gap rule id + the extracted labs/conditions/patient to a caution.

Returns None (proceed) or {level, reason, basis}:
  - "hold"    — a real reason not to initiate now (surfaced prominently).
  - "confirm" — check/obtain something before initiating.
Every caution carries a cited basis (congruence discipline). Thresholds are ILLUSTRATIVE.
"""
from __future__ import annotations

from typing import Dict, List, Optional


def _num(labs: Dict, key: str) -> Optional[float]:
    v = labs.get(key)
    if isinstance(v, dict):
        return v.get("value")
    return v


def _has(conditions: List[str], *kws: str) -> bool:
    joined = " ".join(conditions).lower()
    return any(k in joined for k in kws)


def assess(gap_id: str, labs: Dict, conditions: List[str], patient) -> Optional[Dict]:
    egfr = _num(labs, "egfr")
    if egfr is None:
        egfr = getattr(patient, "egfr", None)
    k = _num(labs, "potassium")
    hr = _num(labs, "hr")
    sbp = None
    bp = labs.get("bp")
    if isinstance(bp, dict):
        sbp = bp.get("systolic")
    conds = [c.lower() for c in conditions]
    preg = getattr(patient, "pregnant", None)

    B = lambda cite: {"source": "Guideline / label", "citation": cite + " — illustrative."}

    # --- RAS inhibition (ACEi/ARB/ARNI) ---
    if gap_id in ("hf_renin", "ckd_renin"):
        if preg is True:
            return {"level": "hold", "reason": "Pregnancy — ACEi/ARB/ARNI are contraindicated (fetopathy).",
                    "basis": B("RAS blockade contraindicated in pregnancy")}
        if k is not None and k >= 5.5:
            return {"level": "hold", "reason": f"Hyperkalemia (K {k}) — do not initiate RAS blockade until corrected.",
                    "basis": B("Hold RAS blockade when K ≥ 5.5")}
        if sbp is not None and sbp < 90:
            return {"level": "confirm", "reason": f"Low systolic BP ({sbp}) — confirm the patient tolerates it before initiating.",
                    "basis": B("Caution with RAS blockade in hypotension")}
        if egfr is not None and egfr < 30:
            return {"level": "confirm", "reason": f"eGFR {egfr:g} — initiate cautiously and recheck renal function/potassium.",
                    "basis": B("Caution with RAS blockade in advanced CKD")}

    # --- Beta-blocker (GDMT) ---
    if gap_id == "hf_bb":
        if hr is not None and hr < 50:
            return {"level": "hold", "reason": f"Bradycardia (HR {hr:g}) — do not start/uptitrate a beta-blocker now.",
                    "basis": B("Avoid beta-blocker initiation in bradycardia")}
        if sbp is not None and sbp < 90:
            return {"level": "confirm", "reason": f"Low systolic BP ({sbp}) — start low, confirm euvolemia first.",
                    "basis": B("Caution with beta-blocker in hypotension")}
        if _has(conds, "asthma", "reactive airway", "bronchospasm"):
            return {"level": "confirm", "reason": "Reactive airway disease — prefer a cardioselective agent and confirm tolerance.",
                    "basis": B("Beta-blocker caution in reactive airway disease")}
        if _has(conds, "decompensated", "acute decompensation"):
            return {"level": "confirm", "reason": "Do not initiate during acute decompensation — start once euvolemic.",
                    "basis": B("Initiate beta-blocker once compensated")}

    # --- MRA ---
    if gap_id == "hf_mra":
        if k is not None and k >= 5.5:
            return {"level": "hold", "reason": f"Hyperkalemia (K {k}) — MRA contraindicated until corrected.",
                    "basis": B("MRA contraindicated when K ≥ 5.5")}
        if k is not None and k >= 5.0:
            return {"level": "confirm", "reason": f"Borderline potassium (K {k}) — recheck and monitor closely if started.",
                    "basis": B("MRA caution when K 5.0–5.4")}
        if egfr is not None and egfr < 30:
            return {"level": "confirm", "reason": f"eGFR {egfr:g} — MRA benefit vs hyperkalemia risk; monitor closely.",
                    "basis": B("MRA caution when eGFR < 30")}

    # --- SGLT2 inhibitor ---
    if gap_id in ("hf_sglt2", "dm_sglt2_organ"):
        if egfr is not None and egfr < 20:
            return {"level": "confirm", "reason": f"eGFR {egfr:g} — below the usual initiation threshold; confirm indication.",
                    "basis": B("SGLT2 inhibitor initiation threshold ~eGFR 20")}
        if _has(conds, "recurrent dka", "ketoacidosis", "type 1 diab"):
            return {"level": "confirm", "reason": "DKA risk — counsel on sick-day rules; avoid in type 1 / recurrent DKA.",
                    "basis": B("SGLT2 inhibitor DKA precaution")}

    # --- Statin ---
    if gap_id == "dm_statin":
        if preg is True:
            return {"level": "hold", "reason": "Pregnancy — statins are contraindicated.",
                    "basis": B("Statin contraindicated in pregnancy")}
        if _has(conds, "active liver", "acute hepatitis", "decompensated cirrhosis"):
            return {"level": "confirm", "reason": "Active liver disease — confirm hepatic status before initiating.",
                    "basis": B("Statin caution in active liver disease")}

    return None
