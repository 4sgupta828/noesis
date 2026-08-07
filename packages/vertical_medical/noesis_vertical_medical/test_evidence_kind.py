"""Evidence-kind classifier: structural facets → the authority pyramid. Unknown → "" (fail-safe)."""
from noesis_vertical_medical.evidence_kind import classify, recency_year
from noesis_vertical_medical.authority import MedicalAuthorityPolicy

A = MedicalAuthorityPolicy()


def test_pub_type_beats_source_default():
    # a systematic review indexed via europepmc outranks the generic "article" default
    assert classify("europepmc", {"source_kind": "article", "pub_type": "Systematic Review"}) == "systematic_review"
    assert classify("europepmc", {"pub_type": "Meta-Analysis"}) == "systematic_review"
    assert classify("europepmc", {"pub_type": "Randomized Controlled Trial"}) == "rct"
    assert classify("europepmc", {"pub_type": "Prospective Cohort Study"}) == "cohort"
    assert classify("europepmc", {"pub_type": "Case Reports"}) == "case_report"


def test_interventional_trial_is_rct_graded():
    assert classify("clinicaltrials", {"study_type": "interventional", "phase": "phase3"}) == "rct"
    assert classify("clinicaltrials", {"study_type": "observational"}) == "cohort"


def test_normative_sources_are_guideline_tier():
    assert classify("openfda", {"source_kind": "drug_label"}) == "guideline"
    assert classify("dailymed", {"source_kind": "drug_label"}) == "guideline"
    assert classify("cdc", {"source_kind": "public_health"}) == "guideline"


def test_faers_is_observational_signal():
    assert classify("faers", {"source_kind": "adverse_event"}) == "cohort"


def test_unknown_is_empty_and_ranks_zero():
    assert classify("web", {}) == ""
    assert classify("", None) == ""
    assert classify("europepmc", {"pub_type": "Journal Article"}) == ""   # too generic to grade
    assert A.rank(classify("web", {})) == 0                                # fail-safe: no boost/demote


def test_tiers_order_via_authority():
    # the classifier's outputs must be rankable and correctly ordered by the pyramid
    assert A.rank(classify("europepmc", {"pub_type": "Systematic Review"})) \
        > A.rank(classify("clinicaltrials", {"study_type": "interventional"}))     # SR > RCT
    assert A.rank(classify("clinicaltrials", {"study_type": "interventional"})) \
        > A.rank(classify("faers", {"source_kind": "adverse_event"}))              # RCT > pharmacovigilance


def test_title_fallback_grades_generic_pubtype():
    # EuropePMC stores only the FIRST pub_type (often generic); recover the tier from the title's
    # explicit self-declared design (v1.1 lever).
    assert classify("europepmc", {"pub_type": "journal-article"},
                    "Statins for primary prevention: A Systematic Review and Meta-Analysis") == "systematic_review"
    assert classify("europepmc", {"pub_type": "research-article"},
                    "A Randomized Controlled Trial of Empagliflozin in Heart Failure") == "rct"
    assert classify("europepmc", {"pub_type": "review"},
                    "A prospective cohort study of statin adherence") == "cohort"
    # explicit pub_type still wins over title, and a generic title stays unclassified
    assert classify("europepmc", {"pub_type": "Meta-Analysis"}, "Some vague title") == "systematic_review"
    assert classify("europepmc", {"pub_type": "journal-article"}, "Statins and cardiovascular outcomes") == ""


def test_recency_year():
    assert recency_year({"year": "2024"}) == 2024
    assert recency_year({"year": 2019}) == 2019
    assert recency_year({}) is None
    assert recency_year({"year": "n/a"}) is None
