"""Global clinical-guidelines connector — the TOP tier of the evidence pyramid (major society /
WHO / task-force guidance), which the corpus almost entirely lacked (30 guideline blocks of 570k).

Like `india_guidelines`, this is a CURATED REGISTRY, not a crawler: each entry is an authoritative
guideline (issuer, condition tags, source URL) with curated key-recommendation summaries. Facets carry
`pub_type=guideline` (top authority tier) + `source_country=global` (never filtered by country scoping).
Coverage maps to the panel's specialty lenses and to the W5 coverage gaps the warrant eval surfaced
(e.g. febrile-neutropenia hour-one bundle, sepsis bundle, anticoagulation selection).

PROVENANCE / HONESTY (same contract as india_guidelines): inline `text` fields are **curated
key-recommendation summaries** attributed to the issuing body — anchor recommendations chosen to be
durable and low-controversy, each explicitly telling the reader to verify against the full published
document. They are NOT the authoritative full text. A production ingest should fetch the real `url`
once verified, and the registry should be reviewed by a clinician before being treated as a quality
benchmark. Guidelines are dated (`year`) — currency is the reader's check.
"""
from __future__ import annotations


def _summary(body: str, issuer: str) -> str:
    return (f"_Curated key recommendations attributed to **{issuer}** — a guideline-tier summary; "
            f"verify against the full published document._\n\n{body}")


GLOBAL_GUIDELINES: tuple[dict, ...] = (
    # ---- emergency / critical care ----
    {"id": "ssc-sepsis", "issuer": "Surviving Sepsis Campaign (SCCM/ESICM)",
     "title": "Surviving Sepsis Campaign — Management of Sepsis and Septic Shock",
     "conditions": ["sepsis", "septic shock", "hypotension infection", "urosepsis"],
     "url": "https://www.sccm.org/survivingsepsiscampaign", "year": 2021,
     "text": _summary(
         "- Obtain **blood cultures before antibiotics** whenever it does not substantially delay therapy, "
         "and give **broad-spectrum antimicrobials within 1 hour** for sepsis with shock.\n"
         "- Begin **30 mL/kg crystalloid** within the first 3 hours for sepsis-induced hypoperfusion, then "
         "reassess; **norepinephrine is the first-line vasopressor**, targeting MAP ≥ 65 mmHg.\n"
         "- Measure lactate and remeasure to guide resuscitation; achieve **source control** (e.g. drain an "
         "obstructed/infected urinary tract, remove infected devices) as rapidly as feasible.",
         "Surviving Sepsis Campaign")},
    {"id": "nccn-idsa-febrile-neutropenia", "issuer": "IDSA / NCCN",
     "title": "Fever and Neutropenia in Patients with Cancer — Antimicrobial Management",
     "conditions": ["febrile neutropenia", "neutropenic fever", "chemotherapy fever"],
     "url": "https://www.idsociety.org/practice-guideline/neutropenic-fever/", "year": 2011,
     "text": _summary(
         "- Febrile neutropenia is a **medical emergency**: draw blood cultures and start **empiric "
         "anti-pseudomonal beta-lactam monotherapy** (e.g. cefepime, piperacillin–tazobactam, or a "
         "carbapenem) **within 1 hour** of presentation.\n"
         "- Risk-stratify (e.g. MASCC); high-risk patients need inpatient IV therapy. Do not delay "
         "antibiotics to await the culture result.\n"
         "- Add gram-positive coverage (vancomycin) only for specific indications (haemodynamic "
         "instability, pneumonia, suspected line infection, severe mucositis) — not routinely.",
         "IDSA / NCCN")},
    {"id": "aha-acls-acs", "issuer": "AHA/ACC",
     "title": "Acute Coronary Syndromes — Early Management",
     "conditions": ["acute coronary syndrome", "myocardial infarction", "stemi", "nstemi", "chest pain"],
     "url": "https://www.ahajournals.org/", "year": 2023,
     "text": _summary(
         "- Obtain a **12-lead ECG within 10 minutes** of first medical contact for suspected ACS; "
         "**STEMI → immediate reperfusion**, PCI preferred (door-to-balloon ≤ 90 min).\n"
         "- Give **aspirin** promptly for suspected ACS unless contraindicated; use **high-sensitivity "
         "troponin** serial measurement to rule in/out MI.\n"
         "- Risk-stratify NSTE-ACS (e.g. GRACE) to time invasive strategy.",
         "AHA/ACC")},
    {"id": "wao-anaphylaxis", "issuer": "WAO / AAAAI-ACAAI",
     "title": "Anaphylaxis — Assessment and Management",
     "conditions": ["anaphylaxis", "allergic reaction", "bee sting", "urticaria hypotension"],
     "url": "https://www.worldallergy.org/", "year": 2020,
     "text": _summary(
         "- **Intramuscular epinephrine (0.3–0.5 mg of 1 mg/mL, anterolateral thigh) is the first-line "
         "treatment and has no absolute contraindication in anaphylaxis**; give it immediately — "
         "antihistamines and steroids are adjuncts, never substitutes.\n"
         "- Place the patient supine (or position of comfort if dyspnoeic); give oxygen and IV fluids for "
         "hypotension; repeat epinephrine every 5–15 min as needed.\n"
         "- Observe for biphasic reactions; discharge with an **epinephrine auto-injector**, an "
         "anaphylaxis action plan, and allergy referral.",
         "World Allergy Organization")},

    # ---- cardiology / stroke ----
    {"id": "acc-aha-afib", "issuer": "ACC/AHA/ACCP/HRS",
     "title": "Atrial Fibrillation — Diagnosis and Management",
     "conditions": ["atrial fibrillation", "afib", "anticoagulation stroke prevention"],
     "url": "https://www.ahajournals.org/doi/10.1161/CIR.0000000000001193", "year": 2023,
     "text": _summary(
         "- Assess stroke risk with **CHA₂DS₂-VASc**; anticoagulate when risk is elevated "
         "(e.g. score ≥ 2 in men, ≥ 3 in women), weighing bleeding risk — bleeding risk scores inform "
         "mitigation, not automatic withholding.\n"
         "- **DOACs are preferred over warfarin** for eligible non-valvular AF; warfarin remains standard "
         "for mechanical valves and moderate-severe mitral stenosis.\n"
         "- Severe CKD/dialysis limits DOAC evidence — dose per renal function and involve nephrology; "
         "rate vs rhythm control is individualised (early rhythm control benefits selected patients).",
         "ACC/AHA")},
    {"id": "acc-aha-hf", "issuer": "AHA/ACC/HFSA",
     "title": "Heart Failure — Guideline-Directed Medical Therapy",
     "conditions": ["heart failure", "hfref", "gdmt", "cardiomyopathy"],
     "url": "https://www.ahajournals.org/doi/10.1161/CIR.0000000000001063", "year": 2022,
     "text": _summary(
         "- HFrEF core therapy is **four pillars**: ARNI (or ACEi/ARB), **beta-blocker**, **MRA**, and "
         "**SGLT2 inhibitor** — titrated to target doses as tolerated.\n"
         "- **SGLT2 inhibitors benefit across the EF spectrum** including HFpEF; diuretics manage "
         "congestion but do not modify disease.\n"
         "- In CKD, do not reflexively withhold RAAS/SGLT2 therapy — an initial creatinine rise is "
         "expected; monitor potassium/function.",
         "AHA/ACC/HFSA")},
    {"id": "aha-asa-stroke", "issuer": "AHA/ASA",
     "title": "Acute Ischemic Stroke — Early Management",
     "conditions": ["stroke", "ischemic stroke", "tia", "thrombolysis"],
     "url": "https://www.ahajournals.org/", "year": 2019,
     "text": _summary(
         "- Suspected stroke → **non-contrast CT immediately**; IV **thrombolysis within 4.5 h** of onset "
         "for eligible patients, and **mechanical thrombectomy** for large-vessel occlusion in eligible "
         "windows (up to 24 h with imaging selection).\n"
         "- Do not lower blood pressure aggressively in acute ischemic stroke unless > 220/120 mmHg "
         "(or > 185/110 before thrombolysis).",
         "AHA/ASA")},

    # ---- prevention / primary care / endocrine ----
    {"id": "uspstf-statin", "issuer": "USPSTF",
     "title": "Statin Use for Primary Prevention of Cardiovascular Disease",
     "conditions": ["statin", "primary prevention", "cardiovascular risk", "hyperlipidemia"],
     "url": "https://www.uspreventiveservicestaskforce.org/", "year": 2022,
     "text": _summary(
         "- For adults 40–75 with ≥ 1 CV risk factor and **10-year ASCVD risk ≥ 10%**, initiate a statin "
         "for primary prevention (moderate benefit); at 7.5–<10% risk, offer selectively (smaller benefit).\n"
         "- Use a validated risk calculator (pooled cohort equations) rather than lipid level alone.",
         "USPSTF")},
    {"id": "ada-soc", "issuer": "American Diabetes Association",
     "title": "ADA Standards of Care in Diabetes",
     "conditions": ["diabetes", "type 2 diabetes", "dka", "hyperglycemia", "hba1c"],
     "url": "https://diabetesjournals.org/care", "year": 2025,
     "text": _summary(
         "- First-line therapy is individualised: **metformin** and/or agents with proven benefit — in "
         "established ASCVD, HF, or CKD, prefer **GLP-1 RA or SGLT2 inhibitor with demonstrated outcome "
         "benefit** regardless of A1C.\n"
         "- Typical A1C target **< 7%** for many non-pregnant adults, relaxed (e.g. < 8%) for limited life "
         "expectancy, hypoglycaemia risk, or heavy comorbidity (especially elderly).\n"
         "- **DKA**: IV fluids, IV insulin infusion, and **potassium replacement before/with insulin when "
         "K⁺ < 3.3 mEq/L**; identify the precipitant. HHS shares principles with slower correction.",
         "American Diabetes Association")},
    {"id": "kdigo-ckd", "issuer": "KDIGO",
     "title": "KDIGO — Evaluation and Management of Chronic Kidney Disease",
     "conditions": ["chronic kidney disease", "ckd", "proteinuria", "renal dosing"],
     "url": "https://kdigo.org/guidelines/", "year": 2024,
     "text": _summary(
         "- Stage CKD by **eGFR and albuminuria (ACR)**; ACEi/ARB titrated to maximum tolerated dose for "
         "albuminuric CKD; add **SGLT2 inhibitor** for most patients with eGFR ≥ 20 and albuminuria or "
         "diabetes (continue until dialysis/transplant).\n"
         "- **Dose-adjust or avoid renally cleared drugs** (metformin per eGFR thresholds, DOACs, many "
         "antibiotics); avoid nephrotoxins (NSAIDs, contrast where avoidable) in advanced CKD.",
         "KDIGO")},

    # ---- infectious disease ----
    {"id": "idsa-asb", "issuer": "IDSA",
     "title": "Asymptomatic Bacteriuria — Management",
     "conditions": ["asymptomatic bacteriuria", "positive urine culture", "uti elderly", "bacteriuria"],
     "url": "https://www.idsociety.org/practice-guideline/asymptomatic-bacteriuria/", "year": 2019,
     "text": _summary(
         "- **Do NOT screen for or treat asymptomatic bacteriuria** in most adults — including older "
         "adults, diabetics, and the institutionalised — treatment adds harm (resistance, C. difficile) "
         "without benefit. Exceptions: **pregnancy** and **before invasive urologic procedures**.\n"
         "- In an older adult with delirium and a positive urine culture but **no urinary symptoms**, "
         "look for other causes of delirium rather than reflexively treating the urine.",
         "IDSA")},
    {"id": "idsa-ats-cap", "issuer": "ATS/IDSA",
     "title": "Community-Acquired Pneumonia in Adults — Diagnosis and Treatment",
     "conditions": ["pneumonia", "community-acquired pneumonia", "cap"],
     "url": "https://www.thoracic.org/", "year": 2019,
     "text": _summary(
         "- Use a validated severity tool (**PSI preferred, or CURB-65**) plus clinical judgment for the "
         "site-of-care decision.\n"
         "- Outpatient, healthy: **amoxicillin or doxycycline** (macrolide only where resistance is low); "
         "inpatient non-severe: beta-lactam + macrolide, or a respiratory fluoroquinolone.\n"
         "- Treat for a minimum of **5 days** guided by clinical stability — longer courses are not "
         "routinely better.",
         "ATS/IDSA")},

    # ---- pediatrics / ob-gyn ----
    {"id": "aap-febrile-infant", "issuer": "American Academy of Pediatrics",
     "title": "Evaluation and Management of the Well-Appearing Febrile Infant (8–60 days)",
     "conditions": ["neonatal fever", "febrile infant", "fever infant", "neonate fever"],
     "url": "https://publications.aap.org/pediatrics/article/148/2/e2021052228/179243", "year": 2021,
     "text": _summary(
         "- A febrile infant **≤ 21–28 days** needs urine, blood, and **CSF** studies with empiric "
         "parenteral antimicrobials and hospitalisation — adult or older-child pathways do not apply.\n"
         "- Infants 29–60 days: risk-stratify with inflammatory markers; lumbar puncture and empiric "
         "treatment based on stratification; never dismiss fever ≥ 38 °C in a neonate as viral without "
         "evaluation.",
         "AAP")},
    {"id": "acog-preeclampsia", "issuer": "ACOG",
     "title": "Gestational Hypertension and Preeclampsia",
     "conditions": ["preeclampsia", "eclampsia", "hypertension pregnancy", "proteinuria pregnancy"],
     "url": "https://www.acog.org/", "year": 2020,
     "text": _summary(
         "- **Severe-range BP (≥ 160/110) sustained 15 min in pregnancy is an emergency**: treat within "
         "30–60 min with IV **labetalol**, IV **hydralazine**, or oral **nifedipine**; ACE inhibitors/ARBs "
         "are contraindicated in pregnancy.\n"
         "- Give **magnesium sulfate** for seizure prophylaxis in preeclampsia with severe features and "
         "for eclampsia.\n"
         "- Delivery timing: preeclampsia with severe features at **≥ 34 weeks → deliver**; without severe "
         "features, deliver at **37 weeks**.",
         "ACOG")},

    # ---- pulmonary ----
    {"id": "gold-copd", "issuer": "GOLD",
     "title": "GOLD — Diagnosis, Management and Prevention of COPD",
     "conditions": ["copd", "chronic obstructive pulmonary disease", "copd exacerbation"],
     "url": "https://goldcopd.org/", "year": 2025,
     "text": _summary(
         "- Confirm with **post-bronchodilator spirometry (FEV₁/FVC < 0.7)**; smoking cessation and "
         "vaccination are foundational.\n"
         "- Initial pharmacotherapy for most symptomatic patients: **LABA + LAMA**; add ICS mainly with "
         "high eosinophils or frequent exacerbations — ICS monotherapy is not recommended in COPD.\n"
         "- Exacerbations: bronchodilators, short systemic corticosteroid course (~5 days), antibiotics "
         "when purulence/ventilation criteria are met; **NIV** for hypercapnic respiratory failure.",
         "GOLD")},
    {"id": "esc-pe", "issuer": "ESC",
     "title": "Acute Pulmonary Embolism — Diagnosis and Management",
     "conditions": ["pulmonary embolism", "pe", "dvt", "d-dimer", "pleuritic chest pain"],
     "url": "https://www.escardio.org/Guidelines", "year": 2019,
     "text": _summary(
         "- Use **pretest probability (Wells/Geneva; PERC in very-low-risk)** to gate testing: low/"
         "intermediate probability → **D-dimer first** (age-adjusted cut-off); imaging (CTPA) only when "
         "indicated — do not image unselected patients.\n"
         "- Haemodynamic instability → immediate risk stratification and **systemic thrombolysis** for "
         "high-risk PE; otherwise anticoagulate (DOAC preferred for most).\n"
         "- In pregnancy, prefer pathways that minimise fetal radiation (proximal-leg ultrasound; "
         "perfusion-dominant strategies) with specialist input.",
         "ESC")},

    # ---- neurology / geriatrics / psychiatry ----
    {"id": "aan-first-seizure", "issuer": "AAN/AES",
     "title": "Management of an Unprovoked First Seizure in Adults",
     "conditions": ["first seizure", "seizure", "convulsion", "epilepsy"],
     "url": "https://www.aan.com/", "year": 2015,
     "text": _summary(
         "- After a first unprovoked seizure: check glucose/electrolytes/toxicology, obtain **EEG** and "
         "**brain imaging (MRI preferred)**, and exclude provoking causes (alcohol withdrawal, drugs, "
         "metabolic derangement).\n"
         "- Immediate anti-seizure medication roughly halves 2-year recurrence but does not change "
         "long-term remission — starting therapy after a single seizure is an **individualised, "
         "risk-based decision**, not automatic.\n"
         "- Counsel on driving restrictions per local law and on safety precautions.",
         "AAN/AES")},
    {"id": "ags-beers", "issuer": "American Geriatrics Society",
     "title": "AGS Beers Criteria — Potentially Inappropriate Medication Use in Older Adults",
     "conditions": ["polypharmacy", "delirium elderly", "inappropriate medication", "falls medication"],
     "url": "https://geriatricscareonline.org/", "year": 2023,
     "text": _summary(
         "- In older adults, **avoid or deprescribe**: benzodiazepines and non-benzo hypnotics (falls, "
         "delirium), strong **anticholinergics** (diphenhydramine, TCAs, bladder antimuscarinics), "
         "long-duration sulfonylureas, and chronic NSAIDs where safer options exist.\n"
         "- New confusion in an older patient on multiple drugs: **medication review for anticholinergic "
         "burden, sedatives, opioids, and recent additions is a first-line diagnostic step**, alongside "
         "delirium workup (infection, metabolic, structural).\n"
         "- Antipsychotics for behavioural symptoms of dementia carry mortality risk — reserve for danger "
         "after non-drug measures.",
         "American Geriatrics Society")},
    {"id": "apa-nms-serotonin", "issuer": "Consensus critical-care/psychiatry references",
     "title": "Neuroleptic Malignant Syndrome and Serotonin Syndrome — Recognition and Management",
     "conditions": ["neuroleptic malignant syndrome", "nms", "serotonin syndrome", "hyperthermia rigidity"],
     "url": "https://www.ncbi.nlm.nih.gov/books/", "year": 2022,
     "text": _summary(
         "- Both are drug-cause emergencies: **stop the offending agent(s)** and give aggressive "
         "supportive care (cooling, fluids, monitoring).\n"
         "- **Serotonin syndrome** (serotonergic exposure): rapid onset, **clonus/hyperreflexia** dominate; "
         "benzodiazepines ± cyproheptadine.\n"
         "- **NMS** (dopamine-antagonist exposure or dopaminergic withdrawal): evolves over days with "
         "**lead-pipe rigidity, marked CK elevation**; check CK/renal function; dantrolene/bromocriptine "
         "in severe cases.\n"
         "- The distinction rests on the **drug history and exam** — document both drug lists explicitly.",
         "critical-care/psychiatry consensus")},

    # ---- GI / heme / rheum / msk ----
    {"id": "acg-pancreatitis", "issuer": "American College of Gastroenterology",
     "title": "Acute Pancreatitis — Initial Management",
     "conditions": ["acute pancreatitis", "pancreatitis", "lipase elevated"],
     "url": "https://gi.org/guidelines/", "year": 2024,
     "text": _summary(
         "- Diagnosis needs 2 of 3: typical pain, lipase/amylase > 3× ULN, imaging findings — **routine "
         "early CT is not required** when the diagnosis is clear.\n"
         "- Early management: **goal-directed moderate crystalloid resuscitation** (aggressive high-volume "
         "strategies increase harm), early **oral feeding as tolerated**, and aetiology work-up "
         "(ultrasound for gallstones, triglycerides, alcohol).\n"
         "- **No prophylactic antibiotics** for sterile necrosis; urgent **ERCP only for concurrent "
         "cholangitis/obstruction**; cholecystectomy same-admission for mild gallstone pancreatitis.",
         "ACG")},
    {"id": "baveno-varices", "issuer": "Baveno / AASLD",
     "title": "Variceal Hemorrhage in Cirrhosis — Management",
     "conditions": ["variceal bleed", "cirrhosis bleeding", "upper gi bleed cirrhosis", "ascites infection"],
     "url": "https://www.aasld.org/", "year": 2023,
     "text": _summary(
         "- Suspected variceal bleed: **restrictive transfusion (Hb threshold ~7 g/dL)**, vasoactive drug "
         "(terlipressin/octreotide) **and prophylactic antibiotics (e.g. ceftriaxone) for every cirrhotic "
         "GI bleed**, then endoscopic band ligation within 12 h.\n"
         "- Cirrhosis + ascites + deterioration (fever, AKI, encephalopathy): **diagnostic paracentesis "
         "to exclude SBP**; in AKI, hold diuretics/nephrotoxins, volume-expand with **albumin**, and "
         "evaluate for hepatorenal syndrome.",
         "Baveno/AASLD")},
    {"id": "ash-itp", "issuer": "American Society of Hematology",
     "title": "Immune Thrombocytopenia (ITP) — Management",
     "conditions": ["thrombocytopenia", "itp", "petechiae low platelets", "ttp"],
     "url": "https://www.hematology.org/education/clinicians/guidelines-and-quality-care", "year": 2019,
     "text": _summary(
         "- New severe thrombocytopenia: review the **smear and the drug list**, and actively exclude "
         "**TTP** (MAHA + thrombocytopenia — schistocytes, LDH, ADAMTS13; TTP is an emergency needing "
         "plasma exchange) before settling on ITP.\n"
         "- Adult ITP with platelets < 30 or bleeding: first-line **corticosteroids** (short course); IVIG "
         "when a rapid rise is needed; platelet transfusion only for life-threatening bleeding.",
         "ASH")},
    {"id": "acr-septic-arthritis-gout", "issuer": "ACR / EULAR / BSR consensus",
     "title": "Acute Monoarthritis — Septic Arthritis and Crystal Disease",
     "conditions": ["septic arthritis", "monoarthritis", "hot swollen joint", "gout"],
     "url": "https://rheumatology.org/", "year": 2020,
     "text": _summary(
         "- A hot swollen joint is **septic arthritis until proven otherwise**: perform **arthrocentesis "
         "before antibiotics** (cell count, Gram stain, culture, crystals); do not rely on serum urate — "
         "gout and infection can coexist.\n"
         "- Confirmed/suspected septic joint: IV antibiotics + **joint drainage**; delay damages cartilage "
         "within days.\n"
         "- Acute gout (infection excluded): colchicine, NSAIDs, or corticosteroids by comorbidity; do not "
         "stop established urate-lowering therapy during a flare.",
         "ACR/EULAR consensus")},
    {"id": "acr-gca", "issuer": "ACR / EULAR",
     "title": "Giant Cell Arteritis — Diagnosis and Management",
     "conditions": ["giant cell arteritis", "temporal arteritis", "jaw claudication", "vision loss headache"],
     "url": "https://rheumatology.org/", "year": 2021,
     "text": _summary(
         "- Suspected GCA with visual symptoms is an emergency: **start high-dose glucocorticoids "
         "immediately — do not wait for the temporal-artery biopsy** (biopsy remains informative for "
         "≥ 2 weeks after starting steroids).\n"
         "- Confirm with temporal-artery ultrasound or biopsy; check ESR/CRP (usually high, but normal "
         "values do not fully exclude).\n"
         "- Tocilizumab is a glucocorticoid-sparing option for relapsing/refractory disease.",
         "ACR/EULAR")},

    # ---- eye / ENT ----
    {"id": "aao-angle-closure", "issuer": "American Academy of Ophthalmology",
     "title": "Primary Angle-Closure Glaucoma — Acute Management",
     "conditions": ["acute angle closure", "glaucoma", "painful red eye", "halos vision"],
     "url": "https://www.aao.org/education/preferred-practice-pattern", "year": 2020,
     "text": _summary(
         "- Painful red eye + mid-dilated non-reactive pupil + halos/nausea = **acute angle closure until "
         "proven otherwise** — check **IOP urgently** and refer emergently to ophthalmology.\n"
         "- Immediate IOP-lowering: topical beta-blocker, alpha-agonist, pilocarpine + systemic "
         "acetazolamide (avoid in sulfa anaphylaxis/sickle disease); definitive treatment is **laser "
         "peripheral iridotomy**, usually bilateral (fellow eye prophylaxis).",
         "AAO")},
    {"id": "hints-vertigo", "issuer": "AAN / Barany Society consensus",
     "title": "Acute Vestibular Syndrome — Distinguishing Peripheral from Central Vertigo",
     "conditions": ["vertigo", "acute vestibular syndrome", "nystagmus", "dizziness"],
     "url": "https://www.aan.com/", "year": 2023,
     "text": _summary(
         "- In continuous acute vestibular syndrome, a properly performed **HINTS exam (Head-Impulse, "
         "Nystagmus, Test-of-Skew) by a trained examiner outperforms early CT/MRI** for detecting stroke: "
         "normal head impulse, direction-changing nystagmus, or skew deviation → central cause.\n"
         "- Early CT is insensitive for posterior-fossa stroke — a negative CT does not exclude it; use "
         "MRI (may need repeat if early) when central features are present.\n"
         "- HINTS applies only to **continuous** vertigo with nystagmus, not brief positional episodes "
         "(BPPV → Dix-Hallpike/Epley).",
         "AAN/Barany consensus")},

    # ---- FULL-TEXT entries (no inline `text` → fetch_artifact downloads the real document; needs the
    # PDF parser in the ingest registry). First mover: KDIGO 2024 CKD — a stable self-hosted PDF
    # (verified: 6 MB, parses to ~980k chars with SGLT2/eGFR/albuminuria anchors present).
    # NOTE: WHO IRIS bitstream URLs broke in their DSpace migration — WHO full texts need the new
    # /server/api/core/bitstreams/<uuid>/content form, resolved per document before adding.
    {"id": "kdigo-ckd-fulltext", "issuer": "KDIGO",
     "title": "KDIGO 2024 Clinical Practice Guideline — CKD Evaluation and Management (FULL TEXT)",
     "conditions": ["chronic kidney disease", "ckd", "albuminuria", "egfr", "kidney disease management"],
     "url": "https://kdigo.org/wp-content/uploads/2024/03/KDIGO-2024-CKD-Guideline.pdf", "year": 2024},

    # ---- electrolytes ----
    {"id": "hyponatremia-consensus", "issuer": "European Hyponatremia Guideline (ESE/ERA/ESICM)",
     "title": "Diagnosis and Treatment of Hyponatremia",
     "conditions": ["hyponatremia", "low sodium", "sodium 118", "siadh"],
     "url": "https://academic.oup.com/ejendo", "year": 2014,
     "text": _summary(
         "- Severe symptomatic hyponatremia (seizures, coma): **hypertonic (3%) saline boluses** targeting "
         "a ~5 mmol/L rise, with close monitoring.\n"
         "- **Limit correction to ≤ 8–10 mmol/L in 24 h** (lower in high-risk: malnutrition, alcoholism, "
         "hypokalaemia) to avoid osmotic demyelination; overshoot → re-lower (D5W ± desmopressin).\n"
         "- Diagnose the mechanism (volume status, urine osmolality/sodium): thiazides are a leading "
         "drug cause — stop the offending diuretic; treat SIADH with fluid restriction first.",
         "European hyponatremia guideline")},
)


def _facets(g: dict) -> dict:
    # pub_type=guideline → top authority tier in evidence_kind; source_country=global (never filtered).
    return {"pub_type": "guideline", "source_country": "global",
            "issuer": g.get("issuer", ""), "year": g.get("year"),
            "source_country_label": "Global"}


class GlobalGuidelinesConnector:
    """Curated top-tier guideline source (major societies / WHO / task forces). Same shape as
    IndiaGuidelinesConnector: discovery matches `window['query']` against condition tags / titles;
    an empty query returns the whole registry (bulk ingest)."""
    key = "global_guidelines"

    class _Http:
        egress_class = "datacenter"; engine = "http"; proxy_enabled = False
        async def fetch(self, url: str, **o) -> bytes:  # noqa: ANN003
            import httpx
            # browser-ish UA: society sites (WordPress etc.) sometimes 403 bare clients
            hdrs = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) noesis-ingest"}
            async with httpx.AsyncClient(timeout=60.0, follow_redirects=True, headers=hdrs) as c:
                r = await c.get(url); r.raise_for_status(); return r.content

    def __init__(self, *, registry: tuple[dict, ...] = GLOBAL_GUIDELINES, documents: list[dict] | None = None):
        self.fetch_strategy = self._Http()
        self._reg: dict[str, dict] = {g["id"]: dict(g) for g in registry}
        for d in documents or []:                     # inject/override (tests, verified full text)
            self._reg[d["id"]] = {**self._reg.get(d["id"], {}), **d}

    def _match(self, query: str) -> list[dict]:
        q = (query or "").strip().lower()
        if not q:
            return list(self._reg.values())
        hits = []
        for g in self._reg.values():
            conds = [c.lower() for c in g.get("conditions", [])]
            if any(c in q or q in c for c in conds) or q in g.get("title", "").lower():
                hits.append(g)
        return hits

    async def discover_entities(self, window: dict):
        from noesis_kernel.contract.dto import EntityRef
        return [EntityRef(source_key=self.key, native_id=g["id"], title=g.get("title", ""),
                          facets=_facets(g)) for g in self._match((window or {}).get("query", ""))]

    async def list_documents(self, entity):
        from noesis_kernel.contract.dto import DocumentRef
        g = self._reg.get(entity.native_id, {})
        url = g.get("url", "")
        ctype = "application/pdf" if url.lower().endswith(".pdf") else "text/markdown"
        return [DocumentRef(source_key=self.key, native_id=entity.native_id, title=entity.title,
                            content_type=ctype, facets=_facets(g), entity_ids=(entity.native_id,))]

    async def fetch_artifact(self, doc) -> bytes:
        g = self._reg[doc.native_id]
        if g.get("text"):                             # curated summary (or injected verified text)
            md = (f"# {g.get('title', '')}\n\n"
                  f"_Issuer: {g.get('issuer', '')} · guideline-tier_\n\n{g['text']}\n")
            return md.encode("utf-8")
        url = g.get("url")
        if not url:
            raise ValueError(f"global_guidelines: no text or url for {doc.native_id!r}")
        return await self.fetch_strategy.fetch(url)   # live fetch (PDF/HTML → parser)
