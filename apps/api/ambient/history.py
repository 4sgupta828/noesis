"""Longitudinal patient history (past ~5 years) — SYNTHETIC, deterministic per case.

⚠️ Illustrative demo data, NOT a real medical record. Generates a plausible, DETAILED 5-year chart
that is CONSISTENT with the case's conditions, age, and current labs — the kind of nitty-gritty a
doctor evaluates holistically: full dated encounters with the vitals + labs drawn that day, what
medications changed, the assessment and disposition; longitudinal lab trends; and background (social,
family, baseline, immunizations, screenings). Real deployments source this from the EHR / ABDM record.
"""
from __future__ import annotations

import datetime
import hashlib
import random
from typing import Dict, List, Optional

_MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]

LAB_META = {  # lab -> (unit, lower_is_better)
    "egfr": ("mL/min", False), "a1c": ("%", True), "ldl": ("mg/dL", True),
    "sbp": ("mmHg", True), "potassium": ("mmol/L", None), "weight": ("kg", None),
}
LAB_LABEL = {"egfr": "eGFR", "a1c": "HbA1c", "ldl": "LDL", "sbp": "Systolic BP",
             "potassium": "Potassium", "weight": "Weight"}
COND_LABS = {
    "heart_failure": ["egfr", "sbp", "potassium"], "ckd": ["egfr", "potassium"],
    "diabetes": ["a1c", "ldl"], "hypertension": ["sbp"], "cad": ["ldl"], "hyperlipidemia": ["ldl"],
    "obesity": [], "atrial_fibrillation": [],
}
DEFAULTS = {"egfr": 62, "a1c": 7.6, "ldl": 118, "sbp": 138, "potassium": 4.4, "weight": 84}
_DOCS = ["Dr. A. Rao", "Dr. M. Chen", "Dr. S. Patel", "Dr. J. Okafor", "Dr. L. Nguyen", "Dr. R. Kapoor",
         "Dr. E. Martinez", "Dr. K. Sharma", "Dr. T. Ibrahim", "Dr. P. Andersson"]
_FIRST_LINE = {
    "heart_failure": "an ACE inhibitor + beta-blocker", "diabetes": "metformin 500 mg BID",
    "hypertension": "amlodipine 5 mg daily", "ckd": "an ACE inhibitor (nephroprotection)",
    "cad": "a high-intensity statin + aspirin", "hyperlipidemia": "atorvastatin 40 mg",
    "atrial_fibrillation": "a DOAC + rate control", "asthma": "an ICS-containing controller",
    "copd": "a long-acting bronchodilator", "depression": "sertraline 50 mg",
    "osteoporosis": "alendronate + calcium/vitamin D", "hypothyroidism": "levothyroxine",
    "obesity": "a structured lifestyle program",
}


def _seed(s: str) -> int:
    return int(hashlib.md5(s.encode()).hexdigest()[:12], 16)


def _full_date(rng: random.Random, year: int) -> Dict:
    m = rng.randint(0, 11)
    d = rng.randint(1, 28)
    return {"iso": f"{year}-{m+1:02d}-{d:02d}", "disp": f"{d} {_MONTHS[m]} {year}", "year": year,
            "sort": year * 400 + m * 31 + d}


def _series(rng, current, lower_better, n, start_year, decimals):
    drift = rng.uniform(0.06, 0.22)
    worsen = rng.random() < 0.45
    if lower_better is False:      # eGFR — renal decline is progressive
        worsen = True
    sign = 1 if not worsen else -1
    first = current * (1 - sign * drift)
    pts = []
    for i in range(n):
        frac = i / (n - 1)
        base = first + (current - first) * frac
        val = base + base * rng.uniform(-0.03, 0.03)
        pts.append({"year": start_year + i, "value": round(val, decimals) if decimals else round(val)})
    pts[-1]["value"] = round(current, decimals) if decimals else round(current)
    return pts


def _direction(pts, lower_better):
    first, last = pts[0]["value"], pts[-1]["value"]
    delta = last - first
    if abs(delta) < (abs(first) * 0.04 or 0.1):
        return {"dir": "stable", "good": None, "delta": delta}
    down = delta < 0
    good = None if lower_better is None else ((down and lower_better) or ((not down) and (not lower_better)))
    return {"dir": "down" if down else "up", "good": good, "delta": round(delta, 1)}


def _trend_at(trends, key, year):
    for t in trends:
        if t["key"] == key:
            best = min(t["points"], key=lambda p: abs(p["year"] - year))
            return best["value"]
    return None


def build_history(conds, labs, patient, seed_str, recent_hosp=False) -> Dict:
    active = [c["condition"] for c in conds]
    labels = {c["condition"]: c["label"] for c in conds}
    if not active:
        return {}
    rng = random.Random(_seed(seed_str))
    today = datetime.date.today()
    yr, start = today.year, today.year - 5
    age = int(getattr(patient, "age_years", None) or 60)
    sex = (getattr(patient, "sex", None) or "").lower()

    # --- lab trends (current value = chart/heard value where available) ---
    want = []
    for c in active:
        for l in COND_LABS.get(c, []):
            if l not in want:
                want.append(l)
    cur = {}
    if isinstance(labs.get("a1c"), dict): cur["a1c"] = labs["a1c"]["value"]
    if isinstance(labs.get("ldl"), dict): cur["ldl"] = labs["ldl"]["value"]
    if isinstance(labs.get("potassium"), dict): cur["potassium"] = labs["potassium"]["value"]
    if isinstance(labs.get("bp"), dict): cur["sbp"] = labs["bp"]["systolic"]
    if getattr(patient, "egfr", None) is not None: cur["egfr"] = patient.egfr
    elif isinstance(labs.get("egfr"), dict): cur["egfr"] = labs["egfr"]["value"]

    trends = []
    for l in want[:4]:
        unit, lower_better = LAB_META[l]
        current = cur.get(l, DEFAULTS[l])
        dec = 1 if l in ("a1c", "potassium") else 0
        pts = _series(rng, current, lower_better, 5, start, dec)
        trends.append({"key": l, "label": LAB_LABEL[l], "unit": unit, "points": pts,
                       "first": pts[0]["value"], "last": pts[-1]["value"], **_direction(pts, lower_better)})

    # --- baseline anthropometrics (used for vitals + background) ---
    height = rng.randint(163, 183) if sex == "male" else rng.randint(150, 170)
    weight0 = round((height - 100) + rng.randint(-4, 20))
    bmi = round(weight0 / ((height / 100) ** 2), 1)

    def vitals_at(year, extra_hr=None):
        sbp = _trend_at(trends, "sbp", year) or rng.randint(122, 148)
        dbp = round(sbp * 0.58)
        hr = extra_hr if extra_hr else rng.randint(64, 86)
        wt = weight0 + rng.randint(-3, 4)
        return [f"BP {sbp}/{dbp}", f"HR {hr}", f"Wt {wt} kg", f"SpO₂ {rng.randint(95,99)}%"]

    def labs_at(year):
        out = []
        for key, lbl in (("egfr", "eGFR"), ("a1c", "HbA1c"), ("ldl", "LDL"), ("potassium", "K")):
            v = _trend_at(trends, key, year)
            if v is not None:
                out.append(f"{lbl} {v}")
        return out

    # --- encounters (each with a full date + detail) ---
    events = []
    onset = {}
    for c in active[:4]:
        oy = start + rng.randint(0, 2)
        onset[c] = oy
        events.append(_enc(rng, oy, "diagnosis", f"New diagnosis: {labels[c]}",
                           reason=f"Work-up leading to {labels[c].lower()}",
                           vitals=vitals_at(oy), labs=labs_at(oy) + _dx_labs(c, rng),
                           changes=[f"Started {_FIRST_LINE.get(c, 'guideline therapy')}"],
                           assessment=f"New {labels[c].lower()}.",
                           plan="Patient education; recheck in 4–6 weeks."))
    if "cad" in active:
        py = min(yr - 1, start + rng.randint(1, 3))
        events.append(_enc(rng, py, "procedure", "Myocardial infarction — PCI with drug-eluting stent",
                           reason="Acute chest pain, ST changes",
                           vitals=vitals_at(py, extra_hr=rng.randint(88, 104)),
                           labs=labs_at(py) + [f"Troponin {rng.choice(['peak 4.2','peak 8.9'])} ng/mL", "LVEF 45%"],
                           changes=["Aspirin + clopidogrel started (12-month DAPT)", "High-intensity statin started"],
                           assessment="Type 1 NSTEMI, culprit LAD lesion stented.",
                           plan=f"Cardiac rehab referral; discharged after {rng.randint(2,4)} days; cardiology follow-up 2 weeks."))
    if "heart_failure" in active and not recent_hosp:
        hy = min(yr - 1, start + rng.randint(1, 3))
        events.append(_enc(rng, hy, "hospitalization", "Heart-failure decompensation admission",
                           reason="Progressive dyspnea, weight gain, edema",
                           vitals=vitals_at(hy, extra_hr=rng.randint(92, 110)) + ["JVP elevated", "bibasilar crackles"],
                           labs=labs_at(hy) + [f"BNP {rng.randint(650,1900)} pg/mL", f"LVEF {rng.choice([25,30,35])}%"],
                           changes=["IV furosemide", "ACEi + beta-blocker uptitrated", "MRA added"],
                           assessment="Acute-on-chronic HFrEF, volume overload.",
                           plan=f"Diuresed to euvolemia; discharged after {rng.randint(3,6)} days; 7-day follow-up, daily weights."))
    if "atrial_fibrillation" in active:
        ay = onset.get("atrial_fibrillation", start + 1)
        events.append(_enc(rng, ay, "procedure", "Atrial fibrillation — rate control ± cardioversion",
                           reason="Palpitations, irregular pulse",
                           vitals=vitals_at(ay, extra_hr=rng.randint(96, 138)),
                           labs=["TSH normal", f"CHA₂DS₂-VASc {rng.randint(2,5)}"],
                           changes=["Anticoagulation started (DOAC)", "Rate control (beta-blocker)"],
                           assessment="New AF; stroke risk elevated by score.",
                           plan="Anticoagulation counseled; TTE ordered; follow-up 4 weeks."))
    if "copd" in active or "asthma" in active:
        ey = start + rng.randint(1, 4)
        cc = "asthma" if "asthma" in active else "COPD"
        events.append(_enc(rng, ey, "ed", f"Emergency visit — {cc} exacerbation",
                           reason="Acute breathlessness, wheeze",
                           vitals=vitals_at(ey, extra_hr=rng.randint(96, 118)) + [f"RR {rng.randint(22,28)}", f"peak flow {rng.randint(180,320)}"],
                           labs=[], changes=["Nebulized bronchodilators + systemic steroids"],
                           assessment=f"{cc} exacerbation, likely viral trigger.",
                           plan="Discharged with steroid taper; controller therapy reviewed; PCP follow-up 1 week."))
    for gy in (start + 2, yr - 1):
        chg = rng.choice(["Continued current regimen", "Uptitrated antihypertensive", "Statin dose increased",
                          "Added an agent for tighter control", "No medication changes"])
        events.append(_enc(rng, gy, "routine", "Routine follow-up",
                           reason="Chronic-disease review",
                           vitals=vitals_at(gy), labs=labs_at(gy),
                           changes=[chg], assessment="Chronic conditions reviewed.",
                           plan=f"Continue plan; recheck in {rng.choice([3,6,12])} months; labs ordered."))
    if recent_hosp:
        events.append(_enc(rng, yr, "hospitalization", "Recent hospitalization (this year)",
                           reason="Acute deterioration",
                           vitals=vitals_at(yr, extra_hr=rng.randint(88, 108)),
                           labs=labs_at(yr), changes=["Medications adjusted inpatient"],
                           assessment="Stabilized; discharge med changes to reconcile.",
                           plan="Reconcile discharge medications this visit; close follow-up."))

    seen = set(); enc = []
    for e in events:
        k = (e["date"]["disp"], e["title"])
        if k in seen: continue
        seen.add(k); enc.append(e)
    enc.sort(key=lambda e: e["date"]["sort"], reverse=True)

    # --- background: social / family / baseline / immunizations / screenings ---
    background = _background(rng, active, labels, age, sex, height, weight0, bmi, yr)

    # --- self-reported + summary ---
    self_rep = _self_reported(rng, active)
    summary = _summary(active, labels, onset, enc, trends, self_rep, background, start)

    return {
        "window": f"{start}–{yr}", "summary": summary, "background": background,
        "trends": trends, "encounters": enc, "self_reported": self_rep,
        "note": "Illustrative synthetic longitudinal history — not a real medical record.",
    }


def _enc(rng, year, typ, title, reason, vitals, labs, changes, assessment, plan) -> Dict:
    return {"date": _full_date(rng, year), "year": year, "type": typ, "title": title,
            "provider": _DOCS[rng.randrange(len(_DOCS))], "reason": reason,
            "vitals": vitals, "labs": labs, "changes": changes, "assessment": assessment, "plan": plan,
            "carepath": plan}


def _dx_labs(c, rng):
    return {
        "diabetes": [f"FPG {rng.randint(160,240)} mg/dL", f"A1c {rng.choice(['9.1','9.8','8.6'])}%"],
        "heart_failure": [f"LVEF {rng.choice([28,30,35])}%", f"BNP {rng.randint(500,1200)} pg/mL"],
        "hyperlipidemia": [f"LDL {rng.randint(150,205)} mg/dL"],
        "cad": ["stress test positive"], "ckd": [f"UACR {rng.randint(45,320)} mg/g"],
        "hypothyroidism": [f"TSH {rng.choice(['8.4','12.1','6.9'])} mIU/L"],
    }.get(c, [])


def _background(rng, active, labels, age, sex, height, weight0, bmi, yr) -> Dict:
    social, family, imm, screen = [], [], [], []
    if "tobacco_use" in active or "copd" in active:
        py = rng.randint(15, 45)
        social.append(f"Tobacco: {py} pack-years, {rng.choice(['current smoker','recently quit','cutting down'])}")
    else:
        social.append(f"Tobacco: {rng.choice(['never smoker','former smoker (quit >10y)'])}")
    social.append(f"Alcohol: {rng.choice(['none','occasional','2–3 drinks/week'])}")
    social.append(f"Occupation: {rng.choice(['retired','office worker','manual labour','homemaker','teacher'])}"
                  + (", lives with spouse" if rng.random() < .6 else ", lives alone"))
    if any(c in active for c in ("cad", "heart_failure", "hypertension", "atrial_fibrillation")):
        family.append(f"Father — myocardial infarction at {rng.randint(52,66)}")
    if "diabetes" in active:
        family.append("Mother — type 2 diabetes")
    if not family:
        family.append("No significant family history reported")
    base = [f"Height {height} cm", f"Weight {weight0} kg", f"BMI {bmi} ({'obese' if bmi>=30 else 'overweight' if bmi>=25 else 'normal'})"]
    imm.append(f"Influenza — {rng.choice(['Oct','Nov'])} {yr}")
    if age >= 65:
        imm.append(f"Pneumococcal — {yr-rng.randint(1,4)}")
    if age >= 50:
        imm.append(f"Recombinant zoster — {yr-rng.randint(0,3)}")
    imm.append(f"COVID-19 — up to date ({yr})")
    if 45 <= age <= 75:
        screen.append(f"Colonoscopy — {yr-rng.randint(1,6)}: {rng.choice(['normal','one polyp removed','normal'])}")
    if sex == "female" and age >= 40:
        screen.append(f"Mammogram — {yr-rng.randint(0,2)}: {rng.choice(['normal','benign findings'])}")
    if not screen:
        screen.append("Age-appropriate screening: see care gaps")
    return {"social": social, "family": family, "baseline": base, "immunizations": imm, "screenings": screen}


def _self_reported(rng, active):
    out = []
    if "tobacco_use" in active:
        out.append({"label": "Tobacco use", "trend": rng.choice(["cutting down but still smoking", "continues ~1 pack/day", "multiple quit attempts"])})
    if "diabetes" in active:
        out.append({"label": "Diet / activity", "trend": rng.choice(["improved adherence this year", "inconsistent, sedentary", "started a walking routine"])})
    if "heart_failure" in active:
        out.append({"label": "Exertional symptoms", "trend": rng.choice(["stable NYHA II", "worsening dyspnea on exertion", "improved since GDMT uptitration"])})
    if "depression" in active:
        out.append({"label": "Mood (PHQ-9)", "trend": rng.choice(["improving", "persistent low mood", "stable on therapy"])})
    return out


def _dx_carepath(c):  # retained for compatibility
    return _FIRST_LINE.get(c, "guideline therapy")


def _summary(active, labels, onset, encounters, trends, self_rep, background, start) -> str:
    parts = []
    earliest = min(onset.values()) if onset else start
    conds = ", ".join(labels[c] for c in active[:3])
    parts.append(f"Longitudinal history of {conds}; earliest diagnosis {earliest}.")
    hosp = sum(1 for e in encounters if e["type"] == "hospitalization")
    proc = sum(1 for e in encounters if e["type"] == "procedure")
    ed = sum(1 for e in encounters if e["type"] == "ed")
    ev = []
    if hosp: ev.append(f"{hosp} hospitalization" + ("s" if hosp > 1 else ""))
    if proc: ev.append(f"{proc} procedure" + ("s" if proc > 1 else ""))
    if ed: ev.append(f"{ed} ED visit" + ("s" if ed > 1 else ""))
    if ev:
        parts.append("Past 5 years: " + ", ".join(ev) + ".")
    worse = [t for t in trends if t.get("good") is False and t["dir"] != "stable"]
    better = [t for t in trends if t.get("good") is True and t["dir"] != "stable"]
    if worse:
        t = worse[0]; parts.append(f"Concerning: {t['label']} {t['first']}→{t['last']} {t['unit']} (worsening).")
    if better:
        t = better[0]; parts.append(f"Improving: {t['label']} {t['first']}→{t['last']} {t['unit']}.")
    if background.get("social"):
        parts.append(background["social"][0] + ".")
    if background.get("family") and "No significant" not in background["family"][0]:
        parts.append("FHx: " + background["family"][0] + ".")
    if self_rep:
        parts.append("Self-reported: " + "; ".join(f"{s['label']} — {s['trend']}" for s in self_rep[:1]) + ".")
    return " ".join(parts)
