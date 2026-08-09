"""Warrant eval case set — wide (every specialty) and deep (multi-system panel cases).

Each case is a realistic patient vignette (a management question, not a literature lookup) chosen to
STRESS specific warrant failure modes (W1–W9, see docs/specs/answer-warrant-contract.md §2) — designed
adversarially (Rule 7): every case names the modes it is meant to probe, so coverage of the failure
taxonomy is deliberate, not incidental. `specialties` lets us confirm every panel lens is exercised.

These are the QUESTIONS only — they assert no gold answer (that needs physician curation). `probes` is
DESIGN INTENT (which failures the case is built to surface), used for analysis, not as ground truth.

Field: id → {q, specialties[], probes[W..], depth: "focused"|"multisystem"}
"""

WARRANT_CASES: dict[str, dict] = {
    # ---- specialty-focused cases (one+ per clinical lens) ----
    "cardiology_afib_ckd_bleed": {
        "q": "70-year-old with newly diagnosed atrial fibrillation, CKD stage 4 (eGFR 22), and a prior "
             "GI bleed — how should stroke-prevention anticoagulation be approached?",
        "specialties": ["cardiology", "nephrology", "hematology"], "depth": "focused",
        "probes": ["W3", "W4", "W7"]},   # DOAC dosing evidence rarely covers eGFR<25; bleeding trade-off is conditional
    "pediatrics_neonatal_fever": {
        "q": "3-week-old, previously well, presents with a rectal temperature of 38.6°C and no obvious "
             "source — what is the recommended evaluation and empiric management?",
        "specialties": ["pediatrics", "infectious_disease"], "depth": "focused",
        "probes": ["W3", "W5"]},   # adult/older-child sepsis evidence must NOT transfer to a neonate
    "obgyn_preeclampsia_htn": {
        "q": "28-week pregnant patient with BP 168/110, headache, and proteinuria — how should this be "
             "evaluated and managed?",
        "specialties": ["obgyn", "cardiology", "nephrology"], "depth": "focused",
        "probes": ["W3", "W7"]},   # non-pregnant hypertension evidence/drugs are frequently inapplicable
    "psychiatry_nms_vs_serotonin": {
        "q": "Patient on an SSRI with a newly added antiemetic develops agitation, clonus, hyperthermia, "
             "and rigidity — how do you distinguish and manage the likely cause?",
        "specialties": ["psychiatry", "clinical_pharmacology", "neurology"], "depth": "focused",
        "probes": ["W5", "W6"]},   # two dangerous dx compete; scarier one can dominate
    "dermatology_drug_rash": {
        "q": "Patient 10 days into a new antibiotic develops a spreading rash with mucosal involvement "
             "and skin tenderness — how should this be assessed and managed?",
        "specialties": ["dermatology", "allergy_immunology", "clinical_pharmacology"], "depth": "focused",
        "probes": ["W4", "W6"]},   # SJS/TEN (case-series evidence) vs. common benign eruption
    "ortho_acute_monoarthritis": {
        "q": "55-year-old with an acutely hot, swollen, painful knee and low-grade fever — what is the "
             "workup and initial management?",
        "specialties": ["orthopedics", "rheumatology", "infectious_disease"], "depth": "focused",
        "probes": ["W5", "W3"]},   # septic joint MUST be covered; not just gout
    "gastro_acute_pancreatitis": {
        "q": "45-year-old with severe epigastric pain radiating to the back, vomiting, and lipase 5× "
             "normal — how should this be managed in the first 24 hours?",
        "specialties": ["gastroenterology", "clinical_pharmacology"], "depth": "focused",
        "probes": ["W7", "W1"]},   # early ERCP/antibiotics are conditional, not routine
    "endo_dka_vs_hhs": {
        "q": "Type 2 diabetic presents with glucose 720, mild ketones, and altered mental status — how "
             "do you evaluate and manage this?",
        "specialties": ["endocrinology", "nephrology"], "depth": "focused",
        "probes": ["W3", "W9"]},   # DKA vs HHS protocols differ; applicability + calibration
    "id_asymptomatic_bacteriuria": {
        "q": "Hospitalized elderly patient with confusion and a positive urine culture but no urinary "
             "symptoms — how should this be managed?",
        "specialties": ["infectious_disease", "geriatrics"], "depth": "focused",
        "probes": ["W2", "W7", "W8"]},   # do-NOT-treat guidance vs reflexive culture/treat (the classic trap)
    "nephrology_hyponatremia": {
        "q": "72-year-old on a thiazide presents with serum sodium 118 and confusion — how should this "
             "be worked up and corrected?",
        "specialties": ["nephrology", "endocrinology"], "depth": "focused",
        "probes": ["W5", "W7", "W9"]},   # broad differential; correction-rate is conditional
    "pulm_suspected_pe": {
        "q": "40-year-old with pleuritic chest pain and dyspnea after a long flight — how should possible "
             "pulmonary embolism be evaluated?",
        "specialties": ["pulmonology", "hematology", "cardiology"], "depth": "focused",
        "probes": ["W7", "W3"]},   # D-dimer/CT indicated only by pretest probability; pregnancy caveat
    "neuro_first_seizure": {
        "q": "35-year-old brought in after a first witnessed generalized convulsion, now postictal — what "
             "is the recommended evaluation and management?",
        "specialties": ["neurology", "clinical_pharmacology"], "depth": "focused",
        "probes": ["W5", "W7"]},   # the missing-seizure-pathway / when-to-start-AED conditionality
    "onc_febrile_neutropenia": {
        "q": "Patient 8 days after chemotherapy presents with fever and an absolute neutrophil count of "
             "300 — how should this be managed in the first hour?",
        "specialties": ["oncology", "infectious_disease", "clinical_pharmacology"], "depth": "focused",
        "probes": ["W3", "W1"]},   # CAR-T / transplant-specific evidence should NOT be applied here
    "rheum_gca": {
        "q": "72-year-old with new temporal headache, jaw claudication, and vision blurring — how should "
             "giant cell arteritis be evaluated and managed?",
        "specialties": ["rheumatology", "ophthalmology"], "depth": "focused",
        "probes": ["W7", "W1"]},   # treat-before-biopsy is a specific conditional, not generic
    "heme_thrombocytopenia": {
        "q": "Previously well 30-year-old presents with new petechiae and a platelet count of 8,000 — how "
             "should this be evaluated and managed?",
        "specialties": ["hematology", "clinical_pharmacology"], "depth": "focused",
        "probes": ["W5", "W6"]},   # ITP vs TTP vs drug-induced; TTP (scary) can dominate
    "urology_urosepsis_obstruction": {
        "q": "68-year-old with flank pain, fever, hypotension, and a stone with hydronephrosis on imaging "
             "— how should this be managed?",
        "specialties": ["urology", "infectious_disease", "nephrology"], "depth": "focused",
        "probes": ["W7", "W5"]},   # emergent decompression is time-conditional
    "ophtho_acute_red_eye": {
        "q": "60-year-old with a sudden painful red eye, halos around lights, nausea, and a mid-dilated "
             "pupil — how should this be evaluated and managed?",
        "specialties": ["ophthalmology"], "depth": "focused",
        "probes": ["W5", "W6"]},   # acute angle closure vs. uveitis/conjunctivitis; sight-threat salience
    "ent_acute_vertigo": {
        "q": "55-year-old with sudden continuous vertigo, nausea, and nystagmus — how do you distinguish "
             "a peripheral from a central cause and manage it?",
        "specialties": ["otolaryngology", "neurology"], "depth": "focused",
        "probes": ["W3", "W7"]},   # HINTS applicability; imaging conditionality
    "allergy_anaphylaxis": {
        "q": "Patient develops urticaria, wheeze, and hypotension minutes after a bee sting — how should "
             "this be managed acutely and afterward?",
        "specialties": ["allergy_immunology", "clinical_pharmacology"], "depth": "focused",
        "probes": ["W8", "W7"]},   # epinephrine vs. any 'contraindication' framing; discharge conditions
    "geriatrics_delirium_polypharmacy": {
        "q": "84-year-old on multiple medications develops acute confusion after admission — how should "
             "delirium be evaluated and managed, and which drugs should be reconsidered?",
        "specialties": ["geriatrics", "clinical_pharmacology", "neurology"], "depth": "focused",
        "probes": ["W3", "W5", "W2"]},   # drug-specific reasoning; non-geriatric evidence misapplied
    "primary_care_undifferentiated_fatigue": {
        "q": "45-year-old presents with 3 months of fatigue and no localizing symptoms — what is a "
             "reasonable initial evaluation?",
        "specialties": ["primary_care", "ebm_methodologist"], "depth": "focused",
        "probes": ["W6", "W4"]},   # rare-but-scary can crowd out high-yield basics

    # ---- deep multi-system cases (what the Panel is really for) ----
    "multi_hfref_ckd_dm_afib_falls": {
        "q": "82-year-old with HFrEF (EF 30%), CKD stage 4, type 2 diabetes on insulin, atrial "
             "fibrillation on warfarin, and recent falls — how should guideline-directed therapy be "
             "optimized while managing bleeding and hypoglycemia risk?",
        "specialties": ["cardiology", "nephrology", "endocrinology", "hematology", "geriatrics",
                        "clinical_pharmacology"], "depth": "multisystem",
        "probes": ["W3", "W5", "W6", "W7", "W8"]},
    "multi_cirrhosis_aki_varices_infection": {
        "q": "Cirrhotic patient with ascites presents with a variceal bleed, rising creatinine, and "
             "fever — how should the bleeding, kidney injury, and possible infection be managed together?",
        "specialties": ["gastroenterology", "nephrology", "infectious_disease", "hematology"],
        "depth": "multisystem", "probes": ["W5", "W7", "W3"]},
    "multi_pregnant_dka_infection": {
        "q": "26-week pregnant type 1 diabetic presents with DKA and a suspected urinary infection — how "
             "should management be adapted for pregnancy?",
        "specialties": ["obgyn", "endocrinology", "infectious_disease", "nephrology"],
        "depth": "multisystem", "probes": ["W3", "W8"]},
    "multi_transplant_fever_aki": {
        "q": "Kidney-transplant recipient on tacrolimus presents with fever, rising creatinine, and new "
             "medications started last week — how should infection, rejection, and drug interactions be "
             "sorted out?",
        "specialties": ["infectious_disease", "nephrology", "clinical_pharmacology", "oncology"],
        "depth": "multisystem", "probes": ["W3", "W1", "W5"]},
    "multi_sepsis_aki_dic_ards": {
        "q": "68-year-old with pneumonia develops hypotension, acute kidney injury, coagulopathy, and "
             "worsening hypoxemia — how should sepsis, AKI, DIC, and respiratory failure be managed "
             "concurrently in the first hours?",
        "specialties": ["pulmonology", "nephrology", "hematology", "infectious_disease"],
        "depth": "multisystem", "probes": ["W5", "W6", "W7"]},
    "multi_cancer_chestpain_dyspnea": {
        "q": "Patient with active cancer on chemotherapy presents with acute chest pain and dyspnea — how "
             "should pulmonary embolism, acute coronary syndrome, and malignancy-related causes be "
             "differentiated and managed?",
        "specialties": ["oncology", "cardiology", "pulmonology", "hematology"],
        "depth": "multisystem", "probes": ["W5", "W3", "W6"]},
    "multi_autoimmune_immunosupp_infiltrates": {
        "q": "Patient with SLE on immunosuppression develops fever, dyspnea, and new bilateral pulmonary "
             "infiltrates — how do you distinguish infection from a lupus flare and manage it?",
        "specialties": ["rheumatology", "pulmonology", "infectious_disease", "clinical_pharmacology"],
        "depth": "multisystem", "probes": ["W5", "W3", "W1"]},
    "multi_elderly_delirium_hyponatremia_uti": {
        "q": "84-year-old on a new antipsychotic and a thiazide develops confusion, sodium 122, fever, "
             "and a positive urine culture — how should the delirium, hyponatremia, and possible "
             "infection be evaluated and managed together?",
        "specialties": ["geriatrics", "neurology", "nephrology", "psychiatry", "infectious_disease",
                        "clinical_pharmacology"], "depth": "multisystem",
        "probes": ["W2", "W3", "W5", "W8"]},
    "multi_polytrauma_doac": {
        "q": "78-year-old on a DOAC for atrial fibrillation presents after a fall with a head strike and "
             "hip pain — how should anticoagulation reversal, intracranial-bleed evaluation, and the hip "
             "injury be managed?",
        "specialties": ["orthopedics", "hematology", "neurology", "clinical_pharmacology"],
        "depth": "multisystem", "probes": ["W7", "W8", "W5"]},
}
