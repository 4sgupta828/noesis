"""Longitudinal patient history (past ~5 years) — SYNTHETIC, deterministic per case.

⚠️ Illustrative demo data, NOT a real medical record. Generates a plausible 5-year history that is
CONSISTENT with the case's conditions, age, and current labs (the latest lab point equals the value
heard this visit where available). Produces: past encounters (routine / hospitalization / ED /
procedure) with their care path, key lab trends (with a good/bad reading), self-reported trends, and a
short history-context summary. Real deployments would build this from the EHR / ABDM longitudinal record.
"""
from __future__ import annotations

import datetime
import hashlib
import random
from typing import Dict, List, Optional

# lab -> (unit, lower_is_better)
LAB_META = {
    "egfr": ("mL/min", False), "a1c": ("%", True), "ldl": ("mg/dL", True),
    "sbp": ("mmHg", True), "potassium": ("mmol/L", None), "weight": ("kg", None),
}
LAB_LABEL = {"egfr": "eGFR", "a1c": "HbA1c", "ldl": "LDL", "sbp": "Systolic BP",
             "potassium": "Potassium", "weight": "Weight"}

# which labs matter for which conditions
COND_LABS = {
    "heart_failure": ["egfr", "sbp", "potassium"], "ckd": ["egfr", "potassium"],
    "diabetes": ["a1c", "ldl"], "hypertension": ["sbp"], "cad": ["ldl"], "hyperlipidemia": ["ldl"],
    "obesity": ["weight"], "atrial_fibrillation": [],
}
# plausible current values if not heard this visit
DEFAULTS = {"egfr": 62, "a1c": 7.6, "ldl": 118, "sbp": 138, "potassium": 4.4, "weight": 84}


def _seed(s: str) -> int:
    return int(hashlib.md5(s.encode()).hexdigest()[:12], 16)


def _series(rng: random.Random, current: float, lower_better, n: int, start_year: int, decimals: int):
    """Generate n yearly points ending at `current`, trending in a seeded direction."""
    # choose a direction: bias eGFR to decline, LDL/A1c to improve, others mixed
    drift = rng.uniform(0.06, 0.22)                      # total fractional change across the window
    worsen = rng.random() < 0.45
    if lower_better is False:      # eGFR: renal decline is progressive — always trend down
        worsen = True
    sign = 1 if not worsen else -1                       # +: value rose toward current
    # earliest value = current shifted opposite to the trend
    first = current * (1 - sign * drift)
    pts = []
    for i in range(n):
        frac = i / (n - 1)
        base = first + (current - first) * frac
        noise = base * rng.uniform(-0.03, 0.03)
        val = round(base + noise, decimals) if decimals else round(base + noise)
        pts.append({"year": start_year + i, "value": val})
    pts[-1]["value"] = round(current, decimals) if decimals else round(current)
    return pts


def _direction(pts, lower_better) -> Dict:
    first, last = pts[0]["value"], pts[-1]["value"]
    delta = last - first
    if abs(delta) < (abs(first) * 0.04 or 0.1):
        return {"dir": "stable", "good": None, "delta": delta}
    down = delta < 0
    if lower_better is None:
        good = None
    else:
        good = (down and lower_better) or ((not down) and (not lower_better))
    return {"dir": "down" if down else "up", "good": good, "delta": round(delta, 1)}


def build_history(conds: List[Dict], labs: Dict, patient, seed_str: str, recent_hosp: bool = False) -> Dict:
    active = [c["condition"] for c in conds]
    labels = {c["condition"]: c["label"] for c in conds}
    if not active:
        return {}
    rng = random.Random(_seed(seed_str))
    today = datetime.date.today()
    yr = today.year
    start = yr - 5
    age = int(getattr(patient, "age_years", None) or 60)

    # --- lab trends (only labs relevant to the active conditions) ---
    want = []
    for c in active:
        for l in COND_LABS.get(c, []):
            if l not in want:
                want.append(l)
    # current values from this visit where available
    cur = {}
    if isinstance(labs.get("egfr"), dict): cur["egfr"] = labs["egfr"]["value"]
    if isinstance(labs.get("a1c"), dict): cur["a1c"] = labs["a1c"]["value"]
    if isinstance(labs.get("ldl"), dict): cur["ldl"] = labs["ldl"]["value"]
    if isinstance(labs.get("potassium"), dict): cur["potassium"] = labs["potassium"]["value"]
    if isinstance(labs.get("bp"), dict): cur["sbp"] = labs["bp"]["systolic"]
    # chart values (context) take precedence so the trend ends at the patient's true current value
    if getattr(patient, "egfr", None) is not None: cur["egfr"] = patient.egfr

    trends = []
    for l in want[:4]:
        unit, lower_better = LAB_META[l]
        current = cur.get(l, DEFAULTS[l])
        decimals = 1 if l in ("a1c", "potassium") else 0
        pts = _series(rng, current, lower_better, 5, start, decimals)
        d = _direction(pts, lower_better)
        trends.append({"key": l, "label": LAB_LABEL[l], "unit": unit, "points": pts,
                       "first": pts[0]["value"], "last": pts[-1]["value"], **d})

    # --- encounters over the window ---
    enc = []
    # condition onset (older patients / more conditions -> earlier onset)
    onset_year = {}
    yr_cursor = start
    for c in active[:4]:
        oy = start + rng.randint(0, 2)
        onset_year[c] = oy
        enc.append({"year": oy, "type": "diagnosis", "title": f"Diagnosed with {labels[c]}",
                    "carepath": _dx_carepath(c)})
    # condition-specific milestones
    if "cad" in active:
        py = min(yr - 1, start + rng.randint(1, 3))
        enc.append({"year": py, "type": "procedure", "title": "Myocardial infarction — PCI with drug-eluting stent",
                    "carepath": "Emergent cath lab, stent placed; started dual antiplatelet + high-intensity statin + cardiac rehab."})
    if "heart_failure" in active and not recent_hosp:
        hy = min(yr - 1, start + rng.randint(1, 3))
        enc.append({"year": hy, "type": "hospitalization", "title": "Heart-failure decompensation admission",
                    "carepath": "IV diuresis, echo (reduced EF confirmed), GDMT initiated/uptitrated; discharged with early follow-up."})
    if "atrial_fibrillation" in active:
        ay = onset_year.get("atrial_fibrillation", start + 1)
        enc.append({"year": ay, "type": "procedure", "title": "Atrial fibrillation — rate control ± cardioversion",
                    "carepath": "Rhythm assessed; anticoagulation decision by CHA2DS2-VASc; rate-control started."})
    if "copd" in active or "asthma" in active:
        ey = start + rng.randint(1, 4)
        enc.append({"year": ey, "type": "ed", "title": "Emergency visit — respiratory exacerbation",
                    "carepath": "Nebulizers + steroids in the ED; controller therapy reviewed on discharge."})
    # routine annual visits (a couple)
    for gy in (start + 2, yr - 1):
        enc.append({"year": gy, "type": "routine", "title": "Routine follow-up",
                    "carepath": "Medication review, labs, risk-factor counseling."})
    if recent_hosp:
        enc.append({"year": yr, "type": "hospitalization", "title": "Recent hospitalization (this year)",
                    "carepath": "Stabilized inpatient; discharged with medication changes — reconcile this visit."})
    # de-dup by (year,title), sort newest first
    seen = set(); uniq = []
    for e in enc:
        k = (e["year"], e["title"])
        if k in seen: continue
        seen.add(k); uniq.append(e)
    uniq.sort(key=lambda e: e["year"], reverse=True)

    # --- self-reported trends ---
    self_rep = []
    if "tobacco_use" in active:
        self_rep.append({"label": "Tobacco use", "trend": rng.choice(
            ["cutting down but still smoking", "continues ~1 pack/day", "multiple quit attempts"])})
    if "diabetes" in active:
        self_rep.append({"label": "Diet / activity", "trend": rng.choice(
            ["improved adherence over the last year", "inconsistent, sedentary", "started a walking routine"])})
    if "heart_failure" in active:
        self_rep.append({"label": "Exertional symptoms", "trend": rng.choice(
            ["stable NYHA II", "worsening dyspnea on exertion", "improved since GDMT uptitration"])})
    if "obesity" in active:
        self_rep.append({"label": "Weight", "trend": "gradual gain over 3 years"})

    # --- summary narrative ---
    summary = _summary(active, labels, onset_year, uniq, trends, self_rep, age, start)

    return {
        "window": f"{start}–{yr}", "summary": summary,
        "trends": trends, "encounters": uniq, "self_reported": self_rep,
        "note": "Illustrative synthetic longitudinal history — not a real medical record.",
    }


def _dx_carepath(c: str) -> str:
    return {
        "heart_failure": "Echo + GDMT started; nurse education and follow-up scheduled.",
        "diabetes": "Metformin started; diabetes education, retinal + foot screening arranged.",
        "hypertension": "Lifestyle + first-line antihypertensive started; home BP monitoring.",
        "ckd": "Cause worked up; nephroprotection (RAS blockade), NSAID avoidance counseled.",
        "cad": "Secondary prevention started (statin + antiplatelet); risk factors addressed.",
        "hyperlipidemia": "Statin started; lipid targets set.",
        "atrial_fibrillation": "Anticoagulation + rate/rhythm strategy set.",
        "asthma": "ICS controller started; inhaler technique + action plan.",
        "copd": "Long-acting inhaler started; smoking cessation + pulmonary rehab.",
        "depression": "Therapy ± SSRI started; PHQ-9 monitoring.",
        "osteoporosis": "Bisphosphonate + calcium/vitamin D; fall-prevention.",
        "hypothyroidism": "Levothyroxine started; TSH titration.",
        "obesity": "Lifestyle program + dietitian referral.",
    }.get(c, "Managed per guideline; follow-up arranged.")


def _summary(active, labels, onset_year, encounters, trends, self_rep, age, start) -> str:
    parts = []
    earliest = min(onset_year.values()) if onset_year else start
    conds = ", ".join(labels[c] for c in active[:3])
    parts.append(f"Longitudinal history of {conds}, with the earliest diagnosis around {earliest}.")
    hosp = [e for e in encounters if e["type"] == "hospitalization"]
    proc = [e for e in encounters if e["type"] == "procedure"]
    ed = [e for e in encounters if e["type"] == "ed"]
    events = []
    if hosp: events.append(f"{len(hosp)} hospitalization{'s' if len(hosp) > 1 else ''}")
    if proc: events.append(f"{len(proc)} procedure{'s' if len(proc) > 1 else ''}")
    if ed: events.append(f"{len(ed)} emergency visit{'s' if len(ed) > 1 else ''}")
    if events:
        parts.append("Over the last 5 years: " + ", ".join(events) + ".")
    # trends: name the clearest good and bad
    worsening = [t for t in trends if t.get("good") is False and t["dir"] != "stable"]
    improving = [t for t in trends if t.get("good") is True and t["dir"] != "stable"]
    if worsening:
        t = worsening[0]
        parts.append(f"Concerning trend: {t['label']} {t['first']}→{t['last']} {t['unit']} (worsening).")
    if improving:
        t = improving[0]
        parts.append(f"Improving: {t['label']} {t['first']}→{t['last']} {t['unit']}.")
    if self_rep:
        parts.append("Self-reported: " + "; ".join(f"{s['label']} — {s['trend']}" for s in self_rep[:2]) + ".")
    return " ".join(parts)
