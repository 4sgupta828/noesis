"""Ambient encounter-intelligence engine (deterministic core, LLM-free).

analyze_encounter(transcript, patient, mode) -> a three-phase view (pre/encounter/post). Contract:
  - Every finding/gap/code carries a cited basis (congruence — enforced).
  - Extracted facts are LINKED to the transcript span they came from (Linked-Evidence parity);
    facts from the chart/context are labelled as such; guideline recommendations are labelled
    "clinical inference" (not from the transcript).
  - Missing data is an explicit coverage gap, never silent clearance.
  - Advisory only; the clinician retains authority.

Reuses the shipped Rx-CDS engine (`api.rxcds`) for drug resolution + safety, and shares that resolver
across US and India modes (it knows US generics and Indian brands).
"""
from __future__ import annotations

import logging
import re
import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

from api.rxcds import data as rxdata
from api.rxcds.engine import PatientContext, check_prescription, normalize

from . import clinical
from . import contraindications
from . import data as adata
from . import history as hist
from . import synthesis
from .modes import MODES, resolve_mode

_PRIMARY_ORDER = ["heart_failure", "cad", "atrial_fibrillation", "diabetes", "ckd", "copd", "asthma",
                  "depression", "osteoporosis", "hypertension", "hyperlipidemia", "hypothyroidism"]

logger = logging.getLogger("noesis.ambient")

_NEGATION_CUES = ("no ", "not ", "denies", "without", "negative for", "ruled out", "never ",
                  "quit", "stopped", "discontinued", "no longer", "d/c", " off ", "resolved")


def _is_negated(text: str, start: int, window: int = 34) -> bool:
    """Lightweight negation: is the term negated by a cue in the preceding window?"""
    pre = text[max(0, start - window):start].lower()
    return any(cue in pre for cue in _NEGATION_CUES)


# --- Transcript-linked extraction ---------------------------------------------

def _build_name_index() -> List[Tuple[str, List[str]]]:
    """Surface name (lowercase) -> molecules. Includes generic/molecule names, brand keys, and brand
    first-tokens. Sorted longest-first so multi-word names match before their fragments."""
    idx: Dict[str, List[str]] = {}
    for key, entry in rxdata.BRANDS.items():
        mols = [c["molecule"] for c in entry["components"]]
        idx.setdefault(key, mols)
        first = key.split()[0]
        idx.setdefault(first, mols)          # "lasix 40" -> "lasix"
        for m in mols:
            idx.setdefault(m, [m])            # molecule name itself
    return sorted(idx.items(), key=lambda kv: -len(kv[0]))


_NAME_INDEX = _build_name_index()


def _find_spans(text: str, needle: str) -> List[Tuple[int, int]]:
    spans = []
    for m in re.finditer(r"(?<![A-Za-z])" + re.escape(needle) + r"(?![A-Za-z])", text, flags=re.IGNORECASE):
        spans.append((m.start(), m.end()))
    return spans


def _snippet(text: str, start: int, end: int, pad: int = 32) -> str:
    a = max(0, start - pad); b = min(len(text), end + pad)
    s = text[a:b].replace("\n", " ").strip()
    return ("…" if a > 0 else "") + s + ("…" if b < len(text) else "")


def extract_conditions(transcript: str, chart_conditions: List[str]) -> List[Dict]:
    """Detect canonical conditions from transcript keywords + chart problem list. Each carries its
    evidence (transcript span with snippet, or 'chart')."""
    out: Dict[str, Dict] = {}
    tl = transcript.lower()
    for cond, meta in adata.CONDITIONS.items():
        # chart
        for c in chart_conditions:
            cl = c.lower()
            if any(kw in cl for kw in meta["keywords"]) or cond in cl:
                out.setdefault(cond, {"condition": cond, "label": meta["label"], "evidence": []})
                out[cond]["evidence"].append({"source": "chart", "text": c})
        # transcript (skip negated mentions — "no diabetes", "quit smoking")
        for kw in meta["keywords"]:
            for (s, e) in _find_spans(tl, kw):
                if _is_negated(transcript, s):
                    continue
                out.setdefault(cond, {"condition": cond, "label": meta["label"], "evidence": []})
                out[cond]["evidence"].append({"source": "transcript", "span": [s, e], "text": _snippet(transcript, s, e)})
                break  # one non-negated span per keyword is enough
    return list(out.values())


def extract_labs(transcript: str) -> Dict:
    """Extract vitals/labs (BP, HR, eGFR, K+, A1c, LDL, EF) from the transcript, each transcript-linked.
    These drive threshold-aware contraindication checks."""
    import re as _re
    labs: Dict = {}
    for name, spec in adata.LAB_PATTERNS.items():
        m = _re.search(spec["regex"], transcript, flags=_re.IGNORECASE)
        if not m:
            continue
        if spec["kind"] == "bp":
            labs[name] = {"systolic": int(m.group(1)), "diastolic": int(m.group(2)), "unit": spec["unit"],
                          "text": _snippet(transcript, m.start(), m.end())}
        else:
            try:
                val = float(m.group(1))
            except ValueError:
                continue
            labs[name] = {"value": val, "unit": spec["unit"], "text": _snippet(transcript, m.start(), m.end())}
    return labs


def extract_meds(transcript: str, current_meds: List[str]) -> List[Dict]:
    """Detect medications in the transcript (+ explicit current meds). Each carries molecules + the
    transcript span (or 'chart' for current meds). Longest-name-first, non-overlapping."""
    found: List[Dict] = []
    claimed: List[Tuple[int, int]] = []
    seen_sigs: set = set()  # dedupe the same molecule set said in both transcript AND chart

    def _sig(mols):
        return tuple(sorted(mols))

    def overlaps(s, e):
        return any(not (e <= cs or s >= ce) for (cs, ce) in claimed)

    for name, mols in _NAME_INDEX:
        for (s, e) in _find_spans(transcript, name):
            if overlaps(s, e):
                continue
            claimed.append((s, e))
            # a stopped/discontinued med is not a CURRENT med — don't count it as present
            if _is_negated(transcript, s):
                continue
            sig = _sig(mols)
            if sig in seen_sigs:
                continue
            seen_sigs.add(sig)
            found.append({"mention": transcript[s:e], "molecules": mols, "source": "transcript",
                          "span": [s, e], "text": _snippet(transcript, s, e)})
    # explicit current meds (chart) — skip any already heard in the transcript
    for cm in current_meds:
        it = normalize(cm)
        if it.molecules() and _sig(it.molecules()) not in seen_sigs:
            seen_sigs.add(_sig(it.molecules()))
            found.append({"mention": cm, "molecules": it.molecules(), "source": "chart", "text": cm})
    return found


def _classes_of_molecules(molecules: List[str]) -> set:
    cls = set()
    for m in molecules:
        for c in rxdata.MOLECULE_CLASSES.get(m, []):
            cls.add(c)
    return cls


# --- Care gaps ----------------------------------------------------------------

_STROKE_RISK_CONDS = {"hypertension", "diabetes", "heart_failure", "cad"}


def _age_ok(rule: Dict, age) -> bool:
    if age is None:
        return "min_age" not in rule and "max_age" not in rule or True  # unknown age → don't suppress
    if "min_age" in rule and age < rule["min_age"]:
        return False
    if "max_age" in rule and age > rule["max_age"]:
        return False
    return True


def _has_stroke_risk(active_conditions: List[str], patient) -> bool:
    age = getattr(patient, "age_years", None)
    if age is not None and age >= 65:
        return True
    if set(active_conditions) & _STROKE_RISK_CONDS:
        return True
    ctext = " ".join(getattr(patient, "conditions", []))
    return "stroke" in ctext or "tia" in ctext or "vascular" in ctext


def care_gaps(active_conditions: List[str], present_classes: set, recent_hospitalization: bool,
              patient=None) -> Dict:
    """Return {gaps, covered, actions} anchored to guideline basis. A drug rule is a GAP when the
    patient is on none of its satisfying classes (a covered rule is reported as reassurance). Rules can
    be age-gated (min_age/max_age) or risk-gated (requires_risk, e.g. AF anticoagulation by CHA2DS2-VASc).
    Age-based prevention (screening/immunization) fires on patient age, not a detected condition."""
    gaps, covered, actions = [], [], []
    cond_set = set(active_conditions)
    age = getattr(patient, "age_years", None) if patient is not None else None
    for rule in adata.CARE_GAPS:
        if rule["condition"] not in cond_set:
            continue
        if not _age_ok(rule, age):
            continue
        if rule["kind"] == "action":
            actions.append({"id": rule["id"], "label": rule["label"], "severity": rule["severity"],
                            "note": rule["note"], "basis": rule["basis"], "condition": rule["condition"]})
            continue
        # risk-gated drug rule (AF anticoagulation): only a gap when stroke risk is present
        if rule.get("requires_risk") and not _has_stroke_risk(active_conditions, patient):
            continue
        satisfied = bool(present_classes.intersection(rule["need_any"]))
        sev = rule["severity"]
        if not satisfied and rule.get("boost_if_condition") and cond_set.intersection(rule["boost_if_condition"]):
            sev = "major"
        entry = {"id": rule["id"], "label": rule["label"], "severity": sev, "note": rule["note"],
                 "basis": rule["basis"], "condition": rule["condition"], "need_any": rule.get("need_any", []),
                 "satisfied_by": sorted(present_classes.intersection(rule["need_any"]))}
        (covered if satisfied else gaps).append(entry)
    # age-based prevention (independent of a detected condition)
    for p in adata.PREVENTION:
        if age is not None and _age_ok(p, age):
            actions.append({"id": p["id"], "label": p["label"], "severity": p["severity"],
                            "note": p["note"], "basis": p["basis"], "condition": "prevention"})
    if recent_hospitalization:
        for a in adata.TRANSITION_ACTIONS:
            actions.append({"id": a["id"], "label": a["label"], "severity": a["severity"],
                            "note": a["note"], "basis": a["basis"], "condition": "transition_of_care"})
    return {"gaps": gaps, "covered": covered, "actions": actions}


# --- Coding (US) / summary (India) --------------------------------------------

def coding_suggestions(active_conditions: List[str], cond_evidence: Dict[str, Dict]) -> List[Dict]:
    """DEFENSIBLE ICD-10 suggestions: only for conditions with in-encounter evidence (MEAT-style), and
    every code quotes the evidence it rests on. Never maximised."""
    out = []
    for cond in active_conditions:
        meta = adata.CONDITIONS.get(cond, {})
        icd = meta.get("icd10")
        ev = cond_evidence.get(cond, {}).get("evidence", [])
        if not icd or not ev:
            continue
        supporting = next((e for e in ev if e["source"] == "transcript"), ev[0])
        out.append({"code": icd["code"], "desc": icd["desc"], "condition": cond,
                    "basis": {"source": "Encounter evidence (MEAT)",
                              "citation": f"{supporting['source']}: \"{supporting.get('text', '')}\""}})
    return out


def _em_hint(n_problems: int, has_transition: bool) -> Dict:
    # illustrative E/M complexity signal from problem count + care-transition (NOT a billing determination)
    level = "99214 (moderate complexity)" if (n_problems >= 2 or has_transition) else "99213 (low complexity)"
    return {"suggestion": level,
            "basis": {"source": "E/M (MDM) — illustrative",
                      "citation": f"{n_problems} active problem(s){' + care transition' if has_transition else ''} addressed; "
                                  "final level requires clinician review of MDM/time."}}


# --- Orchestration ------------------------------------------------------------

def analyze_encounter(transcript: str, patient: PatientContext, mode: str = "US",
                      recent_hospitalization: bool = False) -> Dict:
    t0 = time.perf_counter()
    mode = resolve_mode(mode)
    cfg = MODES[mode]
    transcript = transcript or ""

    conds = extract_conditions(transcript, patient.conditions)
    active = [c["condition"] for c in conds]
    cond_evidence = {c["condition"]: c for c in conds}

    # Fold transcript-detected conditions into the context so drug-disease safety + contraindication
    # checks see comorbidities that were only SPOKEN (not already in the chart problem list).
    _detected = [c["condition"] for c in conds] + [c["label"].lower() for c in conds]
    patient.conditions = list(dict.fromkeys([c.lower() for c in patient.conditions] + _detected))

    # vitals/labs from the transcript drive threshold-aware contraindication checks; a value spoken in
    # the visit fills an unknown context field (never overrides an explicitly-provided one).
    labs = extract_labs(transcript)
    if patient.egfr is None and isinstance(labs.get("egfr"), dict):
        patient.egfr = labs["egfr"]["value"]

    meds = extract_meds(transcript, patient.current_meds)
    all_molecules = sorted({m for md in meds for m in md["molecules"]})
    present_classes = _classes_of_molecules(all_molecules)

    # --- ENCOUNTER: drug safety (reuse Rx-CDS). Pass RESOLVED molecules per deduped item (a brand said
    # without a strength like "Augmentin" still screens); `meds` is already deduped across transcript+chart,
    # so clear ctx.current_meds to avoid double-counting the same drug as two items (false duplicates).
    safety_input = [m for md in meds for m in md["molecules"]]
    patient.current_meds = []
    safety = check_prescription(safety_input, patient) if safety_input else {
        "findings": [], "coverage": {"unverifiable": []}, "summary": {"finding_count": 0}}

    # --- care gaps + contraindication/caution annotation on each drug gap ---
    gaps = care_gaps(active, present_classes, recent_hospitalization, patient)
    cond_texts = list(patient.conditions)
    for g in gaps["gaps"]:
        g["strength"] = adata.STRENGTH.get(g["id"])
        caution = contraindications.assess(g["id"], labs, cond_texts, patient)
        if caution:
            g["caution"] = caution

    # --- POST-VISIT output (mode) ---
    post: Dict = {}
    if cfg["post_visit"] == "coding":
        codes = coding_suggestions(active, cond_evidence)
        post = {"kind": "coding", "icd10": codes,
                "em": _em_hint(len(active), recent_hospitalization)}
    else:
        post = {"kind": "summary", "summary": [
            {"line": c["label"], "basis": {"source": "Encounter/chart",
             "citation": (c["evidence"][0].get("text") if c["evidence"] else c["label"])}} for c in conds]}

    # --- coverage: silence is never clearance ---
    unverifiable = list(safety.get("coverage", {}).get("unverifiable", []))
    if patient.egfr is None and present_classes.intersection({"sglt2", "mra"}):
        unverifiable.append({"molecule": "SGLT2i/MRA suitability",
                             "why": "renal function (eGFR)/potassium not provided — could not confirm suitability/monitoring."})
    if not active:
        unverifiable.append({"molecule": "conditions", "why": "no known chronic conditions detected in transcript or chart — care-gap screening had nothing to anchor to."})

    findings = safety["findings"]
    n_gap_major = sum(1 for g in gaps["gaps"] if g["severity"] == "major")
    latency_ms = round((time.perf_counter() - t0) * 1000, 2)

    logger.info("ambient analyze: mode=%s conds=%d meds=%d safety=%d gaps=%d(major=%d) latency_ms=%.2f",
                mode, len(active), len(meds), len(findings), len(gaps["gaps"]), n_gap_major, latency_ms)

    present_readout = sorted(present_classes.intersection(adata.GDMT_CLASSES),
                             key=lambda c: adata.GDMT_CLASSES.index(c))

    # --- synthesis: the doctor-readable read (picture + ranked why + phase framing) ---
    synth = synthesis.build(
        patient, conds, present_classes,
        {"care_gaps": gaps["gaps"], "actions": gaps["actions"]},
        findings, post, recent_hospitalization,
    )

    # --- clinical-note sections (follow-up, meds plan, non-drug, coherency, precedents) ---
    primary = next((c for c in _PRIMARY_ORDER if c in active), (active[0] if active else None))
    clin = clinical.build(conds, meds, present_classes, gaps, patient, primary)

    # synthetic 5-year longitudinal history (illustrative), seeded per case for stability
    history = hist.build_history(conds, labs, patient, transcript, recent_hospitalization)

    return {
        "mode": mode, "mode_label": cfg["label"],
        "clinical_picture": synth["clinical_picture"],
        "gdmt": synth["gdmt"],
        "priorities": synth["priorities"],
        "phase_notes": synth["phase_notes"],
        "assessment_plan": synth["assessment_plan"],
        "primary_condition": primary,
        "coherency": clin["coherency"],
        "medications": clin["medications"],
        "follow_up": clin["follow_up"],
        "non_drug": clin["non_drug"],
        "precedents": clin["precedents"],
        "history": history,
        "pre_visit": {
            "conditions": conds,
            "present_therapies": [adata.CLASS_LABEL.get(c, c) for c in present_readout],
            "care_gaps": gaps["gaps"], "covered": gaps["covered"], "actions": gaps["actions"],
        },
        "encounter": {
            "medications": meds,
            "safety_findings": findings,
            "care_gap_prompts": gaps["gaps"],
        },
        "post_visit": post,
        "labs": labs,
        "coverage": {"unverifiable": unverifiable},
        "summary": {
            "conditions": len(active), "medications": len(meds),
            "safety_findings": len(findings), "care_gaps": len(gaps["gaps"]),
            "care_gaps_major": n_gap_major, "has_coverage_gaps": bool(unverifiable),
        },
        "latency_ms": latency_ms,
        "disclaimer": cfg["disclaimer"],
    }
