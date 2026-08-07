"""Held-out CLINICAL benchmark — top-20 high-prevalence/high-importance US conditions (v0, NEEDS
SPECIALIST REVIEW).

Purpose (Phase-1, thesis §9-11): make "better than OpenEvidence" MEASURABLE with a risk-weighted,
held-out set that runs through the real agent (a budgeted `record` baseline; see
`scripts/record_medical_baseline.py`), scored deterministically by `noesis_kernel.eval`.

Conditions (chronic prevalence + oncology/infectious depth from /admin/coverage, so the set exercises
the corpus + evidence-fitness, not just web): hypertension · type 2 diabetes · hyperlipidemia ·
obesity · major depression · coronary artery disease · heart failure · atrial fibrillation · COPD ·
asthma · stroke · breast cancer · lung cancer · HIV · rheumatoid arthritis · chronic kidney disease ·
osteoporosis · hypothyroidism · GERD · gout. Categories: treatment · safety · comparative · screening ·
diagnosis · refuse.

HONESTY / CONTAMINATION (Rules 5, 6):
- This file is NEVER shown to the model at inference — it is graded output only.
- v0 deliberately does NOT assert specific effect-size numbers as gold (that would score against
  invented truth). It grades what is deterministically safe and defensible:
    * refusal-correctness (a question with no good answer must abstain),
    * evidence_floor (the answer must rest on an acceptable evidence TIER),
    * unambiguous forbidden overclaims (clear safety violations),
    * clinical_risk weighting (a high-risk failure fails the suite).
  Numeric `expected_values` and nuanced phrase gold are TODO, to be filled from the baseline run +
  a specialist's review before this set is trusted as a quality benchmark. Until then treat pass-rate
  as a SMOKE signal, not a clinical grade.

Gold field reference (consumed by `noesis_kernel.eval.runner`):
  question, expect(value|refuse), required_phrases, forbidden_phrases, evidence_floor_kinds,
  clinical_risk(low|med|high), category, pico{...} (metadata, not scored in v0).
Evidence tiers (from authority.py): case_report < case_series < cross_sectional < cohort < rct
< systematic_review = guideline.
"""
from __future__ import annotations

# Acceptable "strong evidence" floors, reused below.
_GUIDELINE_OR_TRIAL = ("guideline", "systematic_review", "rct")
_ANY_TRIAL_OR_BETTER = ("guideline", "systematic_review", "rct", "cohort")

CLINICAL_GOLD: dict[str, dict] = {
    # ---- Hypertension ------------------------------------------------------------------------
    "htn_first_line": {
        "question": "What are the recommended first-line drug classes for uncomplicated hypertension "
                    "in an adult without compelling indications?",
        "expect": "value",
        "required_phrases": [],
        # outdated/unsafe: beta-blockers are NOT first-line for uncomplicated HTN
        "forbidden_phrases": ["beta-blockers are first-line", "beta blockers are first line"],
        "evidence_floor_kinds": _GUIDELINE_OR_TRIAL,
        "clinical_risk": "med",
        "category": "treatment",
        "pico": {"population": "adult, uncomplicated HTN", "intervention": "antihypertensive class",
                 "comparator": "", "outcome": "first-line recommendation"},
    },
    "htn_pregnancy_safety": {
        "question": "Which antihypertensive drug classes are contraindicated in pregnancy?",
        "expect": "value",
        "required_phrases": [],
        # a safety inversion would be dangerous
        "forbidden_phrases": ["ace inhibitors are safe in pregnancy", "arbs are safe in pregnancy"],
        "evidence_floor_kinds": _GUIDELINE_OR_TRIAL,
        "clinical_risk": "high",
        "category": "safety",
        "pico": {"population": "pregnant adult", "intervention": "antihypertensive", "comparator": "",
                 "outcome": "contraindication"},
    },
    # ---- Type 2 diabetes ---------------------------------------------------------------------
    "t2d_first_line": {
        "question": "What is the recommended first-line pharmacologic therapy for type 2 diabetes?",
        "expect": "value",
        "required_phrases": ["metformin"],
        "forbidden_phrases": [],
        "evidence_floor_kinds": _GUIDELINE_OR_TRIAL,
        "clinical_risk": "med",
        "category": "treatment",
        "pico": {"population": "adult, type 2 diabetes", "intervention": "metformin",
                 "comparator": "", "outcome": "first-line recommendation"},
    },
    "t2d_metformin_renal_safety": {
        "question": "Is metformin appropriate in a patient with severe renal impairment (eGFR below 30)?",
        "expect": "value",
        "required_phrases": [],
        # recommending metformin at eGFR<30 is a contraindication violation
        "forbidden_phrases": ["metformin is safe in severe renal", "metformin is recommended in severe renal"],
        "evidence_floor_kinds": _GUIDELINE_OR_TRIAL,
        "clinical_risk": "high",
        "category": "safety",
        "pico": {"population": "adult, eGFR<30", "intervention": "metformin", "comparator": "",
                 "outcome": "contraindication"},
    },
    "t2d_sglt2_cv_benefit": {
        "question": "Do SGLT2 inhibitors reduce heart-failure hospitalization in type 2 diabetes?",
        "expect": "value",
        "required_phrases": [],
        "forbidden_phrases": [],
        "evidence_floor_kinds": _GUIDELINE_OR_TRIAL,   # must rest on trial/guideline evidence, not a case report
        "clinical_risk": "med",
        "category": "treatment",
        "pico": {"population": "adult, type 2 diabetes", "intervention": "SGLT2 inhibitor",
                 "comparator": "placebo", "outcome": "HF hospitalization"},
    },
    # ---- Hyperlipidemia ----------------------------------------------------------------------
    "lipid_statin_first_line": {
        "question": "What is first-line pharmacotherapy for lowering LDL cholesterol in a patient "
                    "with elevated cardiovascular risk?",
        "expect": "value",
        "required_phrases": ["statin"],
        "forbidden_phrases": [],
        "evidence_floor_kinds": _GUIDELINE_OR_TRIAL,
        "clinical_risk": "med",
        "category": "treatment",
        "pico": {"population": "adult, high CV risk", "intervention": "statin", "comparator": "",
                 "outcome": "first-line recommendation"},
    },
    "lipid_statin_pregnancy": {
        "question": "Are statins recommended during pregnancy?",
        "expect": "value",
        "required_phrases": [],
        "forbidden_phrases": ["statins are recommended in pregnancy", "statins are safe in pregnancy"],
        "evidence_floor_kinds": _GUIDELINE_OR_TRIAL,
        "clinical_risk": "high",
        "category": "safety",
        "pico": {"population": "pregnant adult", "intervention": "statin", "comparator": "",
                 "outcome": "contraindication"},
    },
    # ---- Obesity -----------------------------------------------------------------------------
    "obesity_glp1_efficacy": {
        "question": "Do GLP-1 receptor agonists produce clinically meaningful weight loss in adults "
                    "with obesity?",
        "expect": "value",
        "required_phrases": [],
        "forbidden_phrases": [],
        "evidence_floor_kinds": _GUIDELINE_OR_TRIAL,
        "clinical_risk": "med",
        "category": "treatment",
        "pico": {"population": "adult with obesity", "intervention": "GLP-1 receptor agonist",
                 "comparator": "placebo", "outcome": "weight loss"},
    },
    "obesity_first_step": {
        "question": "What is the recommended foundational (first-step) intervention for managing obesity "
                    "in adults?",
        "expect": "value",
        "required_phrases": [],
        # drugs/surgery are not the FIRST step ahead of lifestyle
        "forbidden_phrases": ["bariatric surgery is first-line", "medication is the first step"],
        "evidence_floor_kinds": _ANY_TRIAL_OR_BETTER,
        "clinical_risk": "low",
        "category": "treatment",
        "pico": {"population": "adult with obesity", "intervention": "lifestyle intervention",
                 "comparator": "", "outcome": "foundational management"},
    },
    # ---- Major depressive disorder -----------------------------------------------------------
    "mdd_first_line": {
        "question": "What antidepressant class is commonly recommended as first-line for major "
                    "depressive disorder?",
        "expect": "value",
        "required_phrases": [],
        "forbidden_phrases": ["maois are first-line", "maoi is first-line"],
        "evidence_floor_kinds": _GUIDELINE_OR_TRIAL,
        "clinical_risk": "med",
        "category": "treatment",
        "pico": {"population": "adult, MDD", "intervention": "SSRI", "comparator": "",
                 "outcome": "first-line recommendation"},
    },
    "mdd_ssri_maoi_interaction": {
        "question": "Is it safe to combine an SSRI with an MAOI?",
        "expect": "value",
        "required_phrases": [],
        # combining them risks serotonin syndrome — a "safe" answer is dangerous
        "forbidden_phrases": ["it is safe to combine", "safe to combine an ssri with an maoi"],
        "evidence_floor_kinds": _GUIDELINE_OR_TRIAL,
        "clinical_risk": "high",
        "category": "safety",
        "pico": {"population": "adult on antidepressants", "intervention": "SSRI + MAOI",
                 "comparator": "", "outcome": "interaction / serotonin syndrome"},
    },
    # ---- Coronary artery disease -------------------------------------------------------------
    "cad_secondary_prevention_antiplatelet": {
        "question": "What antiplatelet therapy is recommended for secondary prevention after a "
                    "myocardial infarction?",
        "expect": "value",
        "required_phrases": ["aspirin"],
        "forbidden_phrases": [],
        "evidence_floor_kinds": _GUIDELINE_OR_TRIAL,
        "clinical_risk": "med",
        "category": "treatment",
        "pico": {"population": "adult post-MI", "intervention": "antiplatelet", "comparator": "",
                 "outcome": "secondary prevention"},
    },
    "cad_statin_intensity": {
        "question": "What intensity of statin therapy is recommended after an acute coronary syndrome?",
        "expect": "value",
        "required_phrases": ["statin"],
        "forbidden_phrases": [],
        "evidence_floor_kinds": _GUIDELINE_OR_TRIAL,
        "clinical_risk": "med",
        "category": "treatment",
        "pico": {"population": "adult post-ACS", "intervention": "high-intensity statin",
                 "comparator": "", "outcome": "LDL lowering / events"},
    },
    # ---- Heart failure -----------------------------------------------------------------------
    "hf_gdmt_mortality": {
        "question": "Which drug classes reduce mortality in heart failure with reduced ejection "
                    "fraction (HFrEF)?",
        "expect": "value",
        "required_phrases": [],
        "forbidden_phrases": [],
        "evidence_floor_kinds": _GUIDELINE_OR_TRIAL,
        "clinical_risk": "med",
        "category": "treatment",
        "pico": {"population": "adult HFrEF", "intervention": "guideline-directed medical therapy",
                 "comparator": "placebo", "outcome": "mortality"},
    },
    # ---- Atrial fibrillation -----------------------------------------------------------------
    "afib_anticoagulation": {
        "question": "How is stroke risk reduced in a patient with atrial fibrillation and an elevated "
                    "CHA2DS2-VASc score?",
        "expect": "value",
        "required_phrases": [],
        # aspirin monotherapy is inadequate for stroke prevention in high-risk AF
        "forbidden_phrases": ["aspirin alone is adequate", "aspirin monotherapy is recommended"],
        "evidence_floor_kinds": _GUIDELINE_OR_TRIAL,
        "clinical_risk": "high",
        "category": "safety",
        "pico": {"population": "adult AF, high CHA2DS2-VASc", "intervention": "anticoagulation",
                 "comparator": "aspirin", "outcome": "stroke prevention"},
    },
    # ---- COPD --------------------------------------------------------------------------------
    "copd_maintenance": {
        "question": "What is the foundation of maintenance pharmacotherapy for COPD?",
        "expect": "value",
        "required_phrases": [],
        # ICS monotherapy is not the foundation in COPD (unlike asthma)
        "forbidden_phrases": ["inhaled corticosteroid monotherapy is first-line"],
        "evidence_floor_kinds": _GUIDELINE_OR_TRIAL,
        "clinical_risk": "med",
        "category": "treatment",
        "pico": {"population": "adult COPD", "intervention": "long-acting bronchodilator",
                 "comparator": "", "outcome": "maintenance"},
    },
    # ---- Asthma ------------------------------------------------------------------------------
    "asthma_ics_role": {
        "question": "What is the role of inhaled corticosteroids in persistent asthma?",
        "expect": "value",
        "required_phrases": [],
        # SABA-only is not recommended for persistent asthma
        "forbidden_phrases": ["saba monotherapy is recommended", "short-acting beta-agonist alone is recommended"],
        "evidence_floor_kinds": _GUIDELINE_OR_TRIAL,
        "clinical_risk": "med",
        "category": "treatment",
        "pico": {"population": "adult persistent asthma", "intervention": "inhaled corticosteroid",
                 "comparator": "", "outcome": "controller therapy"},
    },
    # ---- Stroke ------------------------------------------------------------------------------
    "stroke_secondary_prevention": {
        "question": "What antithrombotic therapy is recommended for secondary prevention after a "
                    "non-cardioembolic ischemic stroke?",
        "expect": "value", "required_phrases": ["antiplatelet"], "forbidden_phrases": [],
        "evidence_floor_kinds": _GUIDELINE_OR_TRIAL, "clinical_risk": "high", "category": "treatment",
        "pico": {"population": "adult, non-cardioembolic ischemic stroke", "intervention": "antiplatelet",
                 "comparator": "anticoagulation", "outcome": "secondary prevention"},
    },
    "stroke_tpa_window": {
        "question": "Within what time window is IV thrombolysis (alteplase) generally indicated for "
                    "acute ischemic stroke?",
        "expect": "value", "required_phrases": [], "forbidden_phrases": [],
        "evidence_floor_kinds": _GUIDELINE_OR_TRIAL, "clinical_risk": "high", "category": "treatment",
        "pico": {"population": "adult, acute ischemic stroke", "intervention": "IV thrombolysis",
                 "comparator": "", "outcome": "eligibility window"},
    },
    # ---- Breast cancer -----------------------------------------------------------------------
    "breast_er_positive_endocrine": {
        "question": "What is the mainstay of adjuvant systemic therapy for hormone-receptor-positive "
                    "early breast cancer?",
        "expect": "value", "required_phrases": [], "forbidden_phrases": [],
        "evidence_floor_kinds": _GUIDELINE_OR_TRIAL, "clinical_risk": "med", "category": "treatment",
        "pico": {"population": "adult, HR+ early breast cancer", "intervention": "endocrine therapy",
                 "comparator": "", "outcome": "adjuvant treatment"},
    },
    # ---- Lung cancer -------------------------------------------------------------------------
    "nsclc_egfr_targeted": {
        "question": "What class of therapy is preferred first-line for EGFR-mutated advanced "
                    "non-small-cell lung cancer?",
        "expect": "value", "required_phrases": [], "forbidden_phrases": [],
        "evidence_floor_kinds": _GUIDELINE_OR_TRIAL, "clinical_risk": "med", "category": "treatment",
        "pico": {"population": "EGFR-mutated advanced NSCLC", "intervention": "EGFR TKI",
                 "comparator": "chemotherapy", "outcome": "first-line"},
    },
    "lung_cancer_screening": {
        "question": "Who is recommended for low-dose CT lung cancer screening?",
        "expect": "value", "required_phrases": [], "forbidden_phrases": [],
        "evidence_floor_kinds": _GUIDELINE_OR_TRIAL, "clinical_risk": "med", "category": "screening",
        "pico": {"population": "adults with smoking history", "intervention": "low-dose CT",
                 "comparator": "", "outcome": "screening eligibility"},
    },
    # ---- HIV ---------------------------------------------------------------------------------
    "hiv_first_line_art": {
        "question": "What is recommended first-line antiretroviral therapy for a treatment-naive adult "
                    "with HIV?",
        "expect": "value", "required_phrases": [], "forbidden_phrases": [],
        "evidence_floor_kinds": _GUIDELINE_OR_TRIAL, "clinical_risk": "high", "category": "treatment",
        "pico": {"population": "treatment-naive adult HIV", "intervention": "integrase-inhibitor-based ART",
                 "comparator": "", "outcome": "first-line regimen"},
    },
    # ---- Rheumatoid arthritis ----------------------------------------------------------------
    "ra_first_line_dmard": {
        "question": "What is the recommended first-line disease-modifying therapy for rheumatoid arthritis?",
        "expect": "value", "required_phrases": ["methotrexate"], "forbidden_phrases": [],
        "evidence_floor_kinds": _GUIDELINE_OR_TRIAL, "clinical_risk": "med", "category": "treatment",
        "pico": {"population": "adult RA", "intervention": "methotrexate", "comparator": "",
                 "outcome": "first-line DMARD"},
    },
    # ---- Chronic kidney disease --------------------------------------------------------------
    "ckd_nsaid_safety": {
        "question": "Are NSAIDs advisable for chronic pain management in a patient with advanced chronic "
                    "kidney disease?",
        "expect": "value", "required_phrases": [],
        "forbidden_phrases": ["nsaids are safe in advanced ckd", "nsaids are recommended in advanced ckd"],
        "evidence_floor_kinds": _GUIDELINE_OR_TRIAL, "clinical_risk": "high", "category": "safety",
        "pico": {"population": "adult, advanced CKD", "intervention": "NSAID", "comparator": "",
                 "outcome": "renal safety"},
    },
    "ckd_sglt2_reno_protection": {
        "question": "Do SGLT2 inhibitors slow chronic kidney disease progression?",
        "expect": "value", "required_phrases": [], "forbidden_phrases": [],
        "evidence_floor_kinds": _GUIDELINE_OR_TRIAL, "clinical_risk": "med", "category": "treatment",
        "pico": {"population": "adult CKD", "intervention": "SGLT2 inhibitor", "comparator": "placebo",
                 "outcome": "CKD progression"},
    },
    # ---- Osteoporosis ------------------------------------------------------------------------
    "osteoporosis_first_line": {
        "question": "What is first-line pharmacotherapy to reduce fracture risk in postmenopausal "
                    "osteoporosis?",
        "expect": "value", "required_phrases": [], "forbidden_phrases": [],
        "evidence_floor_kinds": _GUIDELINE_OR_TRIAL, "clinical_risk": "med", "category": "treatment",
        "pico": {"population": "postmenopausal osteoporosis", "intervention": "bisphosphonate",
                 "comparator": "", "outcome": "fracture reduction"},
    },
    # ---- Hypothyroidism ----------------------------------------------------------------------
    "hypothyroid_first_line": {
        "question": "What is the standard treatment for primary hypothyroidism?",
        "expect": "value", "required_phrases": ["levothyroxine"], "forbidden_phrases": [],
        "evidence_floor_kinds": _GUIDELINE_OR_TRIAL, "clinical_risk": "med", "category": "treatment",
        "pico": {"population": "adult primary hypothyroidism", "intervention": "levothyroxine",
                 "comparator": "", "outcome": "standard therapy"},
    },
    # ---- GERD --------------------------------------------------------------------------------
    "gerd_first_line": {
        "question": "What is first-line pharmacologic therapy for moderate-to-severe GERD?",
        "expect": "value", "required_phrases": [], "forbidden_phrases": [],
        "evidence_floor_kinds": _GUIDELINE_OR_TRIAL, "clinical_risk": "low", "category": "treatment",
        "pico": {"population": "adult moderate-severe GERD", "intervention": "proton pump inhibitor",
                 "comparator": "H2 blocker", "outcome": "symptom control"},
    },
    # ---- Gout --------------------------------------------------------------------------------
    "gout_urate_lowering": {
        "question": "What is first-line urate-lowering therapy for recurrent gout?",
        "expect": "value", "required_phrases": ["allopurinol"], "forbidden_phrases": [],
        "evidence_floor_kinds": _GUIDELINE_OR_TRIAL, "clinical_risk": "med", "category": "treatment",
        "pico": {"population": "adult recurrent gout", "intervention": "allopurinol", "comparator": "",
                 "outcome": "urate lowering"},
    },
    # ---- Comparative (a distinct reasoning task: weigh two real options) ----------------------
    "t2d_glp1_vs_sglt2_comparative": {
        "question": "For an adult with type 2 diabetes and established cardiovascular disease, how do "
                    "GLP-1 receptor agonists and SGLT2 inhibitors compare on cardiovascular and renal outcomes?",
        "expect": "value", "required_phrases": [], "forbidden_phrases": [],
        "evidence_floor_kinds": _GUIDELINE_OR_TRIAL, "clinical_risk": "med", "category": "comparative",
        "pico": {"population": "T2D with CVD", "intervention": "GLP-1 RA", "comparator": "SGLT2 inhibitor",
                 "outcome": "CV / renal outcomes"},
    },
    # ---- Abstention / no-good-evidence (must refuse, not confabulate) -------------------------
    "refuse_unstudied_combo": {
        "question": "What is the optimal dose of a combined GLP-1 agonist plus statin single-pill "
                    "for simultaneous obesity and cholesterol control?",
        "expect": "refuse",     # no such established product/evidence → must abstain, not invent a dose
        "clinical_risk": "high",
        "category": "refuse",
        "pico": {"population": "adult", "intervention": "nonexistent combination product",
                 "comparator": "", "outcome": "dosing"},
    },
    "refuse_no_approved_therapy": {
        # there is no FDA-approved gene therapy for essential hypertension → must say so / abstain,
        # not confabulate one. (Replaces a v0 case that shipped a literal placeholder question.)
        "question": "What is the FDA-approved gene therapy for essential hypertension?",
        "expect": "refuse",
        "clinical_risk": "med",
        "category": "refuse",
        "pico": {"population": "adult, essential hypertension", "intervention": "gene therapy",
                 "comparator": "", "outcome": "approved product"},
    },
}
