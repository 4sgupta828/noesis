"""Shape/validity gate for the held-out clinical benchmark (free, CI). Catches authoring errors —
NOT a quality measurement (that's the budgeted record baseline). Guards against contamination and
malformed gold so the benchmark stays trustworthy."""
from noesis_vertical_medical.eval_clinical_gold import CLINICAL_GOLD
from noesis_vertical_medical.authority import MedicalAuthorityPolicy

_VALID_TIERS = {"case_report", "case_series", "cross_sectional", "cohort", "rct",
                "systematic_review", "guideline"}
_VALID_RISK = {"low", "med", "high"}
_A = MedicalAuthorityPolicy()


def test_every_case_is_well_formed():
    for cid, c in CLINICAL_GOLD.items():
        assert c.get("question", "").strip(), f"{cid}: empty question"
        assert c.get("expect") in ("value", "refuse", "rank"), f"{cid}: bad expect"
        assert c.get("clinical_risk", "low") in _VALID_RISK, f"{cid}: bad clinical_risk"
        for t in c.get("evidence_floor_kinds", ()):
            assert t in _VALID_TIERS and _A.rank(t) > 0, f"{cid}: unknown evidence tier {t!r}"


def test_refuse_cases_have_no_answer_gold():
    # a refuse case must not also demand answer content (that would be contradictory gold)
    for cid, c in CLINICAL_GOLD.items():
        if c.get("expect") == "refuse":
            assert not c.get("required_phrases"), f"{cid}: refuse case must not require phrases"
            assert not c.get("expected_values"), f"{cid}: refuse case must not expect values"
            assert not c.get("evidence_floor_kinds"), f"{cid}: refuse case has no evidence floor"


def test_coverage_is_stratified():
    cats = {c.get("category") for c in CLINICAL_GOLD.values()}
    assert {"treatment", "safety", "refuse"} <= cats, f"missing categories: {cats}"
    # the risk-weighting + critical gate only bite if high-risk + refuse cases exist
    assert any(c.get("clinical_risk") == "high" for c in CLINICAL_GOLD.values()), "no high-risk case"
    assert sum(1 for c in CLINICAL_GOLD.values() if c.get("expect") == "refuse") >= 2, "too few refuse cases"


def test_no_expected_numeric_values_yet():
    # v0 deliberately defers effect-size gold (Rule 6). This test documents that + fails loudly if
    # someone adds a numeric value without the specialist-review process — forcing a conscious decision.
    for cid, c in CLINICAL_GOLD.items():
        assert not c.get("expected_values"), (
            f"{cid}: expected_values set — v0 defers numeric gold to specialist review; "
            "remove this guard deliberately when the reviewed benchmark lands")
