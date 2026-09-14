"""Clinical synthesis — turns the deterministic findings into a doctor-readable read.

The engine produces WHAT (conditions, gaps, safety, coding). This layer produces the SO-WHAT: a
one-paragraph patient picture, a single ranked "what to do and why" list that ties pre/encounter/post
together, and a short reasoning line per phase. It is still deterministic and grounded — it only
narrates findings the engine already derived and cited; it never introduces a new clinical claim.
"""
from __future__ import annotations

from typing import Dict, List, Optional

# Clinician-facing rationale for each recommendation (the "why it matters"). Illustrative.
RATIONALE: Dict[str, str] = {
    "hf_renin": "RAS inhibition is one of the four pillars that each independently lower mortality in HFrEF.",
    "hf_bb": "An evidence-based beta-blocker independently reduces HFrEF mortality — only carvedilol, "
             "metoprolol succinate, or bisoprolol carry that evidence.",
    "hf_mra": "An MRA adds further mortality benefit in HFrEF; the main cost is potassium/renal monitoring.",
    "hf_sglt2": "SGLT2 inhibitors reduce HF hospitalization and death regardless of diabetes status — the "
                "newest and fastest-acting GDMT pillar.",
    "dm_statin": "Most adults with diabetes warrant a statin for ASCVD risk reduction regardless of baseline LDL.",
    "dm_sglt2_organ": "An SGLT2 inhibitor is uniquely DOUBLY indicated here — a heart-failure pillar AND "
                      "cardiorenal protection in diabetes — so it is the single highest-yield addition.",
    "dm_a1c": "Glycemic control still matters, but confirm the current A1c before changing diabetes therapy.",
    "ckd_renin": "RAS blockade is renoprotective when albuminuria is present; verify albuminuria and potassium first.",
    "tob_cessation": "Continued smoking compounds cardiovascular risk; brief advice plus pharmacotherapy at "
                     "the visit is high-yield and low-effort.",
    "toc_medrec": "Discharge medication changes are where errors cluster — reconcile before anything else changes.",
    "toc_followup": "Early follow-up after a heart-failure admission is the best-evidenced lever against readmission.",
    "afib_anticoag": "With an elevated CHA2DS2-VASc score, anticoagulation prevents most AF-related strokes; a DOAC is preferred over warfarin for most patients.",
    "cad_statin": "In established ASCVD a high-intensity statin is the single most impactful secondary-prevention drug.",
    "cad_antiplatelet": "Antiplatelet therapy reduces recurrent events in established coronary disease.",
    "asthma_controller": "Rescue-only asthma is undertreatment — an ICS-containing controller reduces exacerbations and death.",
    "copd_controller": "Long-acting inhaled maintenance therapy reduces COPD exacerbations and hospitalizations.",
    "osteo_therapy": "Antiresorptive therapy meaningfully lowers fracture risk once osteoporosis is established.",
    "osteo_calvitd": "Calcium and vitamin D are the necessary adjunct to any osteoporosis pharmacotherapy.",
    "depression_mgmt": "Measurement-based care (PHQ-9) with therapy and/or an SSRI improves depression outcomes.",
    "hypothyroid_tsh": "Periodic TSH confirms the levothyroxine dose is at target and avoids over-/under-treatment.",
    "screen_colon": "Colorectal cancer screening 45–75 prevents cancer deaths — confirm it's current.",
    "imm_shingles": "The recombinant zoster vaccine is recommended for adults ≥50 to prevent shingles and its complications.",
    "imm_pneumo": "Pneumococcal vaccination reduces invasive disease in adults ≥65.",
}


def _sex_word(sex: Optional[str]) -> str:
    return {"male": "man", "female": "woman"}.get((sex or "").lower(), "patient")


def _gdmt_status(active: List[str], present_classes: set) -> Optional[Dict]:
    """Heart-failure GDMT pillar accounting (only when HF is present)."""
    if "heart_failure" not in active:
        return None
    pillars = {
        "RAS inhibitor (ACEi/ARB/ARNI)": bool(present_classes & {"acei", "arb", "arni"}),
        "beta-blocker": "gdmt-betablocker" in present_classes,
        "MRA": "mra" in present_classes,
        "SGLT2 inhibitor": "sglt2" in present_classes,
    }
    have = [k for k, v in pillars.items() if v]
    return {"have": have, "n_have": len(have), "n_total": 4,
            "missing": [k for k, v in pillars.items() if not v]}


def clinical_picture(patient, active_labels: List[Dict], present_classes: set,
                     recent_hosp: bool) -> str:
    """One-paragraph read: who this is, the headline issue, and the opportunity."""
    active = [c["condition"] for c in active_labels]
    labels = [c["label"] for c in active_labels]
    if not labels:
        return "No chronic conditions were detected in the transcript or chart, so there was nothing to " \
               "anchor guideline screening to — confirm the problem list."
    who = _sex_word(getattr(patient, "sex", None))
    age = getattr(patient, "age_years", None)
    lead = f"{int(age)}-year-old {who}" if age else who.capitalize()
    conds = _join(labels)
    parts = [f"{lead} with {conds}."]
    if recent_hosp:
        parts.append("Recently hospitalized — the post-discharge visit is the highest-risk, highest-yield "
                     "window to optimize therapy.")
    gd = _gdmt_status(active, present_classes)
    if gd:
        if gd["n_have"] < gd["n_total"]:
            parts.append(f"On {gd['n_have']} of 4 guideline-directed heart-failure medication (GDMT) "
                         f"pillars — missing {_join(gd['missing'])}. Closing these is the biggest available "
                         f"mortality lever.")
        else:
            parts.append("On all four GDMT pillars — focus shifts to titration and monitoring.")
    return " ".join(parts)


def priorities(pre: Dict, safety: List[Dict], gdmt: Optional[Dict]) -> List[Dict]:
    """The spine: one ranked 'what to do and why', tying safety + gaps + actions together with
    urgency tiers a clinician can act on. Highest-leverage first."""
    out: List[Dict] = []
    # 1. Safety first — anything the Rx-CDS engine flagged blocks/qualifies prescribing.
    for f in safety:
        out.append({"when": "Before prescribing", "title": f["title"],
                    "action": f.get("management") or "Review before prescribing.",
                    "why": f["detail"], "basis": f["basis"], "severity": f["severity"], "kind": "safety"})
    # 2. Doubly-indicated / major drug gaps (start or plan this visit).
    majors = [g for g in pre["care_gaps"] if g["severity"] == "major"]
    # SGLT2 can be flagged from both the HF-pillar rule and the diabetes cardiorenal rule — the same
    # drug. Merge to ONE priority (the doubly-indicated framing) so the doctor sees one action.
    ids = {g["id"] for g in majors}
    if "hf_sglt2" in ids and "dm_sglt2_organ" in ids:
        majors = [g for g in majors if g["id"] != "hf_sglt2"]
    # surface the doubly-indicated SGLT2 first if present
    majors.sort(key=lambda g: (0 if g["id"] == "dm_sglt2_organ" else 1))
    for g in majors:
        out.append(_gap_entry(g, "Start / plan this visit"))
    # 3. Moderate gaps.
    for g in [g for g in pre["care_gaps"] if g["severity"] == "moderate"]:
        out.append(_gap_entry(g, "This visit / near-term"))
    # 4. Actions (counseling, reconciliation, follow-up, confirmations).
    for a in pre["actions"]:
        when = "Before other changes" if a["id"] == "toc_medrec" else (
            "Confirm" if a["severity"] == "info" else "This visit")
        out.append({"when": when, "title": a["label"], "action": a["label"],
                    "why": RATIONALE.get(a["id"], a["note"]), "basis": a["basis"],
                    "severity": a["severity"], "kind": "action"})
    for i, p in enumerate(out, 1):
        p["rank"] = i
    return out


def phase_notes(active_labels: List[Dict], pre: Dict, safety: List[Dict],
                post: Dict, recent_hosp: bool) -> Dict:
    """A short framing sentence for each phase, so the details read as one thread."""
    n_gap = len(pre["care_gaps"]); n_major = sum(1 for g in pre["care_gaps"] if g["severity"] == "major")
    pre_note = (f"Walk in knowing the problem list and where care diverges from guidelines: "
                f"{n_major} major gap(s) of {n_gap}. " +
                ("Reconcile discharge meds first. " if recent_hosp else "") +
                "Each item below says why it matters.") if n_gap else \
               "No guideline gaps for the detected conditions — confirm the problem list is complete."
    enc_note = ("Stay with the patient — the safety check runs on whatever medications come up. "
                + (f"{len(safety)} interaction/dosing flag(s) to resolve before prescribing."
                   if safety else "No drug-safety flags on the medications heard."))
    if post.get("kind") == "coding":
        post_note = ("The diagnoses discussed support the codes below — each quotes the encounter evidence "
                     "(defensible, not maximized), so they survive payer review.")
    else:
        post_note = "A plain patient summary of what was covered, grounded in the encounter and chart."
    return {"pre": pre_note, "encounter": enc_note, "post": post_note}


# --- helpers ------------------------------------------------------------------

def _gap_entry(g: Dict, default_when: str) -> Dict:
    """Build a priority entry for a care gap, folding in its contraindication caution + guideline
    strength. A caution changes WHEN (hold / confirm first) and is surfaced as a first-class field."""
    caution = g.get("caution")
    when = default_when
    action = _action_for(g)
    if caution:
        if caution["level"] == "hold":
            when = "Hold — address first"
            action = f"Hold {g['label']} — {caution['reason']}"
        elif caution["level"] == "confirm":
            when = "Confirm first, then start"
            action = f"Before starting {g['label']}: {caution['reason']}"
    return {"when": when, "title": g["label"], "action": action,
            "why": RATIONALE.get(g["id"], g["note"]), "basis": g["basis"],
            "severity": g["severity"], "kind": "gap",
            "strength": g.get("strength"), "caution": caution}


def _action_for(gap: Dict) -> str:
    label = gap["label"]
    # phrase the gap as an action
    if gap.get("satisfied_by") == []:
        return f"Consider initiating: {label}."
    return f"Consider: {label}."


def _join(items: List[str]) -> str:
    items = [str(i) for i in items]
    if not items:
        return ""
    if len(items) == 1:
        return items[0]
    if len(items) == 2:
        return f"{items[0]} and {items[1]}"
    return ", ".join(items[:-1]) + f", and {items[-1]}"


def assessment_plan(patient, active_labels: List[Dict], present_classes: set, pre: Dict,
                    safety: List[Dict], post: Dict, recent_hosp: bool) -> str:
    """A copy-ready Assessment & Plan the clinician can paste into the note — grouped by problem, each
    plan line reflecting any contraindication caution. Plain text on purpose."""
    lines = ["ASSESSMENT & PLAN", ""]
    lines.append(clinical_picture(patient, active_labels, present_classes, recent_hosp))
    lines.append("")
    codes = {c["condition"]: c["code"] for c in (post.get("icd10") or [])}
    gaps_by_cond: Dict[str, List[Dict]] = {}
    for g in pre["care_gaps"]:
        gaps_by_cond.setdefault(g["condition"], []).append(g)
    actions_by_cond: Dict[str, List[Dict]] = {}
    for a in pre["actions"]:
        actions_by_cond.setdefault(a["condition"], []).append(a)

    for c in active_labels:
        cond = c["condition"]
        hdr = f"# {c['label']}" + (f"  [{codes[cond]}]" if cond in codes else "")
        lines.append(hdr)
        for g in gaps_by_cond.get(cond, []):
            caution = g.get("caution")
            if caution and caution["level"] == "hold":
                lines.append(f"- HOLD {g['label']} — {caution['reason']}")
            elif caution and caution["level"] == "confirm":
                lines.append(f"- {g['label']}: confirm first — {caution['reason']}")
            else:
                lines.append(f"- Start/optimize {g['label']} ({RATIONALE.get(g['id'], g['note'])})")
        for a in actions_by_cond.get(cond, []):
            lines.append(f"- {a['label']}")
        lines.append("")
    # transitions + health maintenance actions not tied to a problem
    misc = actions_by_cond.get("transition_of_care", [])
    if misc:
        lines.append("# Transitions of care")
        for a in misc:
            lines.append(f"- {a['label']}")
        lines.append("")
    if safety:
        lines.append("# Medication safety")
        for f in safety:
            lines.append(f"- {f['title']} — {f.get('management', '')}")
        lines.append("")
    if post.get("kind") == "coding":
        cds = ", ".join(f"{c['code']}" for c in post.get("icd10", []))
        lines.append(f"Codes: {cds or '—'}  |  E/M: {post.get('em', {}).get('suggestion', '—')}")
    lines.append("")
    lines.append("— Advisory decision support (Noesis). Clinician confirms and signs.")
    return "\n".join(lines).strip()


def build(patient, active_labels: List[Dict], present_classes: set, pre: Dict,
          safety: List[Dict], post: Dict, recent_hosp: bool) -> Dict:
    active = [c["condition"] for c in active_labels]
    gd = _gdmt_status(active, present_classes)
    return {
        "clinical_picture": clinical_picture(patient, active_labels, present_classes, recent_hosp),
        "gdmt": gd,
        "priorities": priorities(pre, safety, gd),
        "phase_notes": phase_notes(active_labels, pre, safety, post, recent_hosp),
        "assessment_plan": assessment_plan(patient, active_labels, present_classes, pre, safety, post, recent_hosp),
    }
