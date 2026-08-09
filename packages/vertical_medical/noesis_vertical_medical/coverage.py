"""Declared coverage plan for the medical corpus — the source inventory and the
condition roadmap (covered vs. remaining). This is the domain-owned "what we intend to
have" list; the admin endpoint pairs it with LIVE corpus counts to show progress.

Kept as plain data so an ops/admin page can render it without domain code.
"""
from __future__ import annotations

# Ingestible sources and their status. `key` matches rs_block.source_key when live.
SOURCE_INVENTORY = [
    {"key": "clinicaltrials", "label": "ClinicalTrials.gov", "kind": "trials", "tier": "open", "status": "live"},
    {"key": "openfda", "label": "openFDA drug labels", "kind": "drug labels", "tier": "open", "status": "live"},
    {"key": "europepmc", "label": "Europe PMC", "kind": "literature", "tier": "open", "status": "live", "note": "FULL-TEXT enabled 2026-08-09; deliberate SR/MA sweeps across 38 conditions"},
    {"key": "faers", "label": "openFDA FAERS", "kind": "adverse events", "tier": "open", "status": "partial", "note": "16 high-risk/narrow-index drugs swept 2026-08-09; breadth continues"},
    {"key": "cdc", "label": "CDC (data.cdc.gov)", "kind": "public health", "tier": "open", "status": "partial", "note": "14 high-yield topics swept 2026-08-09 (immunization, STI, stewardship…)"},
    {"key": "dailymed", "label": "DailyMed", "kind": "SPL labels", "tier": "open", "status": "live", "note": "~815 labels — top-60 prescribed drugs swept 2026-08-09; bulk remainder open"},
    {"key": "global_guidelines", "label": "Global guidelines (society/WHO/task-force)", "kind": "guidelines", "tier": "open", "status": "live", "note": "27 curated top-tier summaries + FULL TEXT via docling (KDIGO 2024 CKD, ~200 blocks); clinician review of registry pending"},
    {"key": "india_guidelines", "label": "India guidelines (ICMR/MoHFW/programmes)", "kind": "guidelines", "tier": "open", "status": "live", "note": "18 curated entries (source_country=IN); clinician review pending"},
    {"key": "rxnorm", "label": "RxNorm", "kind": "drug normalization", "tier": "open", "status": "connector", "note": "utility; not wired into ingest facets"},
    {"key": "licensed", "label": "Cochrane · NICE · NCCN · NEJM · JAMA", "kind": "reviews / guidelines / journals", "tier": "licensed", "status": "planned", "note": "needs contracts / API access"},
]

# Conditions already ingested (deep = ~300 trials + ~150 papers; type 2 diabetes = reference depth).
# As of 2026-08-03 every roadmap condition is DEEP — depth labels reflect landed corpus blocks.
COVERED_CONDITIONS = [
    {"group": "Oncology", "name": "lung cancer", "depth": "deep"},
    {"group": "Oncology", "name": "prostate cancer", "depth": "deep"},
    {"group": "Oncology", "name": "colorectal cancer", "depth": "deep"},
    {"group": "Oncology", "name": "leukemia", "depth": "deep"},
    {"group": "Oncology", "name": "lymphoma", "depth": "deep"},
    {"group": "Oncology", "name": "melanoma", "depth": "deep"},
    {"group": "Oncology", "name": "breast cancer", "depth": "deep"},
    {"group": "Cardiovascular", "name": "coronary artery disease", "depth": "deep"},
    {"group": "Cardiovascular", "name": "atrial fibrillation", "depth": "deep"},
    {"group": "Cardiovascular", "name": "stroke", "depth": "deep"},
    {"group": "Cardiovascular", "name": "hypertension", "depth": "deep"},
    {"group": "Cardiovascular", "name": "heart failure", "depth": "deep"},
    {"group": "Infectious", "name": "HIV", "depth": "deep"},
    {"group": "Infectious", "name": "hepatitis C", "depth": "deep"},
    {"group": "Respiratory / Immuno", "name": "asthma", "depth": "deep"},
    {"group": "Respiratory / Immuno", "name": "rheumatoid arthritis", "depth": "deep"},
    {"group": "Respiratory / Immuno", "name": "COPD", "depth": "deep"},
    {"group": "Neuro / Psych", "name": "Alzheimer disease", "depth": "deep"},
    {"group": "Neuro / Psych", "name": "depression", "depth": "deep"},
    {"group": "Neuro / Psych", "name": "Parkinson disease", "depth": "deep"},
    {"group": "Metabolic / Renal", "name": "type 2 diabetes", "depth": "reference"},
    {"group": "Metabolic / Renal", "name": "obesity", "depth": "deep"},
    {"group": "Metabolic / Renal", "name": "chronic kidney disease", "depth": "deep"},
    # Tier-2 (2026-08-02): ~300 trials + 150 papers each
    {"group": "Oncology", "name": "pancreatic cancer", "depth": "deep"},
    {"group": "Oncology", "name": "ovarian cancer", "depth": "deep"},
    {"group": "Oncology", "name": "bladder cancer", "depth": "deep"},
    {"group": "Oncology", "name": "renal cell carcinoma", "depth": "deep"},
    {"group": "Oncology", "name": "glioblastoma", "depth": "deep"},
    {"group": "Oncology", "name": "multiple myeloma", "depth": "deep"},
    {"group": "Oncology", "name": "head and neck cancer", "depth": "deep"},
    {"group": "Cardiovascular", "name": "hyperlipidemia", "depth": "deep"},
    {"group": "Cardiovascular", "name": "peripheral artery disease", "depth": "deep"},
    {"group": "Cardiovascular", "name": "venous thromboembolism", "depth": "deep"},
    {"group": "Infectious", "name": "COVID-19", "depth": "deep"},
    {"group": "Infectious", "name": "tuberculosis", "depth": "deep"},
    {"group": "Infectious", "name": "sepsis", "depth": "deep"},
    {"group": "Infectious", "name": "hepatitis B", "depth": "deep"},
    {"group": "Infectious", "name": "influenza", "depth": "deep"},
    {"group": "Neuro / Psych", "name": "multiple sclerosis", "depth": "deep"},
    {"group": "Neuro / Psych", "name": "epilepsy", "depth": "deep"},
    {"group": "Neuro / Psych", "name": "migraine", "depth": "deep"},
    {"group": "Neuro / Psych", "name": "schizophrenia", "depth": "deep"},
    {"group": "Neuro / Psych", "name": "anxiety disorder", "depth": "deep"},
    {"group": "Neuro / Psych", "name": "bipolar disorder", "depth": "deep"},
    {"group": "Neuro / Psych", "name": "amyotrophic lateral sclerosis", "depth": "deep"},
    {"group": "Immuno / Rheum", "name": "psoriasis", "depth": "deep"},
    {"group": "Immuno / Rheum", "name": "inflammatory bowel disease", "depth": "deep"},
    {"group": "Immuno / Rheum", "name": "systemic lupus erythematosus", "depth": "deep"},
    {"group": "Immuno / Rheum", "name": "ankylosing spondylitis", "depth": "deep"},
    {"group": "Metabolic / GI", "name": "NASH / MASH", "depth": "deep"},
    {"group": "Metabolic / GI", "name": "GERD", "depth": "deep"},
    {"group": "Metabolic / GI", "name": "osteoporosis", "depth": "deep"},
    {"group": "Metabolic / GI", "name": "anemia", "depth": "deep"},
    {"group": "Other", "name": "chronic pain", "depth": "deep"},
    # Tier-3 (2026-08-03): ~300 trials + ~150 papers each, prod-direct ingest (all verified deep by
    # landed blocks). Seven of these were previously bulk-ingested; eleven added in this pass.
    {"group": "Oncology", "name": "cervical cancer", "depth": "deep"},
    {"group": "Oncology", "name": "esophageal cancer", "depth": "deep"},
    {"group": "Oncology", "name": "gastric cancer", "depth": "deep"},
    {"group": "Oncology", "name": "sarcoma", "depth": "deep"},
    {"group": "Cardiovascular", "name": "pulmonary hypertension", "depth": "deep"},
    {"group": "Cardiovascular", "name": "valvular heart disease", "depth": "deep"},
    {"group": "Infectious", "name": "malaria", "depth": "deep"},
    {"group": "Infectious", "name": "HPV", "depth": "deep"},
    {"group": "Neuro / Psych", "name": "Huntington disease", "depth": "deep"},
    {"group": "Neuro / Psych", "name": "PTSD", "depth": "deep"},
    {"group": "Neuro / Psych", "name": "ADHD", "depth": "deep"},
    {"group": "Immuno / Rheum", "name": "Sjögren syndrome", "depth": "deep"},
    {"group": "Immuno / Rheum", "name": "vasculitis", "depth": "deep"},
    {"group": "Metabolic / GI", "name": "celiac disease", "depth": "deep"},
    {"group": "Metabolic / GI", "name": "gout", "depth": "deep"},
    {"group": "Respiratory", "name": "pulmonary fibrosis", "depth": "deep"},
    {"group": "Respiratory", "name": "cystic fibrosis", "depth": "deep"},
    {"group": "Renal", "name": "polycystic kidney disease", "depth": "deep"},
    # Acute / guideline-tier (2026-08-09): top-tier guideline + SR/MA coverage (not 300-trial depth) —
    # the conditions the warrant eval exercises; "medium" depth is the honest label.
    {"group": "Acute / guideline-tier", "name": "febrile neutropenia", "depth": "medium"},
    {"group": "Acute / guideline-tier", "name": "acute coronary syndrome", "depth": "medium"},
    {"group": "Acute / guideline-tier", "name": "preeclampsia", "depth": "medium"},
    {"group": "Acute / guideline-tier", "name": "neonatal fever", "depth": "medium"},
    {"group": "Acute / guideline-tier", "name": "anaphylaxis", "depth": "medium"},
    {"group": "Acute / guideline-tier", "name": "acute pancreatitis", "depth": "medium"},
    {"group": "Acute / guideline-tier", "name": "variceal bleeding / cirrhosis", "depth": "medium"},
    {"group": "Acute / guideline-tier", "name": "hyponatremia", "depth": "medium"},
    {"group": "Acute / guideline-tier", "name": "diabetic ketoacidosis", "depth": "medium"},
    {"group": "Acute / guideline-tier", "name": "immune thrombocytopenia", "depth": "medium"},
    {"group": "Acute / guideline-tier", "name": "giant cell arteritis", "depth": "medium"},
    {"group": "Acute / guideline-tier", "name": "septic arthritis", "depth": "medium"},
    {"group": "Acute / guideline-tier", "name": "community-acquired pneumonia", "depth": "medium"},
    {"group": "Acute / guideline-tier", "name": "delirium (older adults)", "depth": "medium"},
    {"group": "Acute / guideline-tier", "name": "acute vertigo", "depth": "medium"},
    {"group": "Acute / guideline-tier", "name": "acute angle-closure glaucoma", "depth": "medium"},
    {"group": "Acute / guideline-tier", "name": "asymptomatic bacteriuria", "depth": "medium"},
    # India programme conditions (curated national guidance, 2026-08-05 → 08-09)
    {"group": "India programme", "name": "dengue", "depth": "medium"},
    {"group": "India programme", "name": "enteric fever (typhoid)", "depth": "medium"},
    {"group": "India programme", "name": "visceral leishmaniasis (kala-azar)", "depth": "medium"},
    {"group": "India programme", "name": "rabies post-exposure prophylaxis", "depth": "medium"},
    {"group": "India programme", "name": "snakebite envenomation", "depth": "medium"},
    {"group": "India programme", "name": "gestational diabetes (DIPSI)", "depth": "medium"},
    {"group": "India programme", "name": "scrub typhus", "depth": "medium"},
    {"group": "India programme", "name": "leprosy", "depth": "medium"},
    {"group": "India programme", "name": "rheumatic fever / RHD prophylaxis", "depth": "medium"},
    {"group": "India programme", "name": "childhood diarrhoea (ORS + zinc)", "depth": "medium"},
    {"group": "India programme", "name": "anemia in pregnancy", "depth": "medium"},
    {"group": "India programme", "name": "TB preventive treatment", "depth": "medium"},
]

# Remaining work. Every roadmap CONDITION is now covered deep; what's left is cross-cutting DEPTH
# on the non-trial sources (not a condition gap) — the lever for effect sizes / eligibility /
# guideline-grade synthesis (see the clinical-synthesis answer work).
REMAINING_CONDITIONS = [
    {"group": "Depth work", "name": "Guideline FULL-TEXT expansion — per-society direct PDFs via the KDIGO/docling pattern (WHO needs new IRIS URLs)"},
    {"group": "Depth work", "name": "Licensed sources: Cochrane full text · NICE · NCCN · NEJM/JAMA (contracts needed)"},
    {"group": "Depth work", "name": "LactMed pregnancy/lactation + pediatric dosing connectors"},
    {"group": "Depth work", "name": "DailyMed bulk remainder + FAERS breadth beyond the top-76 drugs"},
    {"group": "Quality", "name": "Clinician review of the curated guideline registries (27 global + 18 India)"},
]


def coverage_plan() -> dict:
    return {
        "sources": SOURCE_INVENTORY,
        "covered": COVERED_CONDITIONS,
        "remaining": REMAINING_CONDITIONS,
    }
