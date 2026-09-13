"""Unit tests for the ambient encounter engine. Pure-Python; no DB/LLM/network."""
from __future__ import annotations

from api.rxcds.engine import PatientContext
from api.ambient.engine import analyze_encounter, extract_conditions, extract_meds

# The Alyssa Stauffacher case: 64, HFrEF + diabetes + tobacco, recently hospitalized.
ALYSSA_TRANSCRIPT = (
    "So since your heart failure hospitalization last month you've been on furosemide and lisinopril, "
    "and we're continuing metformin for your diabetes. You mentioned you're still smoking about half a "
    "pack a day. Your breathing is better but let's talk about your medications."
)


def _gap_ids(res):
    return {g["id"] for g in res["pre_visit"]["care_gaps"]}


def test_extract_conditions_from_transcript():
    conds = extract_conditions(ALYSSA_TRANSCRIPT, [])
    ids = {c["condition"] for c in conds}
    assert {"heart_failure", "diabetes", "tobacco_use"}.issubset(ids)
    # every detected condition carries evidence (a transcript span or chart)
    assert all(c["evidence"] for c in conds)


def test_extract_meds_linked_to_transcript():
    meds = extract_meds(ALYSSA_TRANSCRIPT, [])
    mols = {m for md in meds for m in md["molecules"]}
    assert {"furosemide", "lisinopril", "metformin"}.issubset(mols)
    # transcript-sourced meds carry a span
    assert all("span" in md for md in meds if md["source"] == "transcript")


def test_care_gaps_hf_gdmt():
    res = analyze_encounter(ALYSSA_TRANSCRIPT, PatientContext(), mode="US", recent_hospitalization=True)
    ids = _gap_ids(res)
    # has lisinopril (ACEi) -> RAS pillar COVERED; missing beta-blocker, MRA, SGLT2 -> gaps
    assert "hf_bb" in ids and "hf_mra" in ids and "hf_sglt2" in ids
    assert "hf_renin" not in ids   # covered by lisinopril
    covered_ids = {c["id"] for c in res["pre_visit"]["covered"]}
    assert "hf_renin" in covered_ids


def test_sglt2_double_indication_escalated():
    # SGLT2 gap is escalated to major when both HF and diabetes present
    res = analyze_encounter(ALYSSA_TRANSCRIPT, PatientContext(), mode="US")
    sglt2 = next(g for g in res["pre_visit"]["care_gaps"] if g["id"] == "dm_sglt2_organ")
    assert sglt2["severity"] == "major"


def test_every_gap_and_code_has_basis():
    res = analyze_encounter(ALYSSA_TRANSCRIPT, PatientContext(), mode="US", recent_hospitalization=True)
    for g in res["pre_visit"]["care_gaps"] + res["pre_visit"]["actions"] + res["pre_visit"]["covered"]:
        assert g["basis"]["citation"]
    for code in res["post_visit"]["icd10"]:
        assert code["basis"]["citation"]


def test_us_mode_emits_defensible_coding():
    res = analyze_encounter(ALYSSA_TRANSCRIPT, PatientContext(), mode="US")
    assert res["post_visit"]["kind"] == "coding"
    codes = {c["code"] for c in res["post_visit"]["icd10"]}
    assert "I50.22" in codes and "E11.9" in codes and "Z72.0" in codes
    # every code quotes its supporting encounter evidence (MEAT)
    assert all("\"" in c["basis"]["citation"] for c in res["post_visit"]["icd10"])


def test_india_mode_emits_summary_not_coding():
    res = analyze_encounter(ALYSSA_TRANSCRIPT, PatientContext(), mode="IN")
    assert res["post_visit"]["kind"] == "summary"
    assert "icd10" not in res["post_visit"]
    assert res["mode"] == "IN"


def test_transition_actions_on_recent_hospitalization():
    res = analyze_encounter(ALYSSA_TRANSCRIPT, PatientContext(), mode="US", recent_hospitalization=True)
    action_ids = {a["id"] for a in res["pre_visit"]["actions"]}
    assert "toc_medrec" in action_ids and "toc_followup" in action_ids


def test_drug_safety_reused_from_rxcds():
    # ACEi (lisinopril) + MRA (spironolactone) -> hyperkalemia interaction, via the reused engine
    tx = "We'll add spironolactone to your lisinopril for the heart failure."
    res = analyze_encounter(tx, PatientContext(), mode="US")
    cats = {f["category"] for f in res["encounter"]["safety_findings"]}
    assert "drug-drug-interaction" in cats
    assert all(f["basis"]["citation"] for f in res["encounter"]["safety_findings"])


def test_silence_is_not_clearance_unknown_egfr():
    # SGLT2i present but eGFR unknown -> explicit coverage gap
    tx = "Let's start empagliflozin for your heart failure."
    res = analyze_encounter(tx, PatientContext(egfr=None), mode="US")
    assert res["summary"]["has_coverage_gaps"] is True
    assert any("SGLT2" in u["molecule"] or "suitability" in u["molecule"] for u in res["coverage"]["unverifiable"])


def test_no_conditions_is_flagged_not_silent():
    res = analyze_encounter("Patient here for a routine visit, feeling well.", PatientContext(), mode="US")
    assert res["summary"]["has_coverage_gaps"] is True


def test_latency_fast():
    res = analyze_encounter(ALYSSA_TRANSCRIPT, PatientContext(), mode="US", recent_hospitalization=True)
    assert res["latency_ms"] < 150
