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
    {"key": "europepmc", "label": "Europe PMC", "kind": "literature", "tier": "open", "status": "live", "note": "abstracts; OA full-text TODO"},
    {"key": "faers", "label": "openFDA FAERS", "kind": "adverse events", "tier": "open", "status": "partial", "note": "thin — a few drugs so far"},
    {"key": "cdc", "label": "CDC (data.cdc.gov)", "kind": "public health", "tier": "open", "status": "partial", "note": "thin"},
    {"key": "dailymed", "label": "DailyMed", "kind": "SPL labels", "tier": "open", "status": "connector", "note": "connector built; not bulk-ingested"},
    {"key": "rxnorm", "label": "RxNorm", "kind": "drug normalization", "tier": "open", "status": "connector", "note": "utility; not wired into ingest facets"},
    {"key": "licensed", "label": "Cochrane · NICE · NCCN · NEJM · JAMA", "kind": "reviews / guidelines / journals", "tier": "licensed", "status": "planned", "note": "needs contracts / API access"},
]

# Conditions already ingested (deep = ~300 trials + 150 papers; ref/medium/shallow as noted).
COVERED_CONDITIONS = [
    {"group": "Oncology", "name": "lung cancer", "depth": "deep"},
    {"group": "Oncology", "name": "prostate cancer", "depth": "deep"},
    {"group": "Oncology", "name": "colorectal cancer", "depth": "deep"},
    {"group": "Oncology", "name": "leukemia", "depth": "deep"},
    {"group": "Oncology", "name": "lymphoma", "depth": "deep"},
    {"group": "Oncology", "name": "melanoma", "depth": "deep"},
    {"group": "Oncology", "name": "breast cancer", "depth": "medium"},
    {"group": "Cardiovascular", "name": "coronary artery disease", "depth": "deep"},
    {"group": "Cardiovascular", "name": "atrial fibrillation", "depth": "deep"},
    {"group": "Cardiovascular", "name": "stroke", "depth": "deep"},
    {"group": "Cardiovascular", "name": "hypertension", "depth": "shallow"},
    {"group": "Cardiovascular", "name": "heart failure", "depth": "shallow"},
    {"group": "Infectious", "name": "HIV", "depth": "deep"},
    {"group": "Infectious", "name": "hepatitis C", "depth": "deep"},
    {"group": "Respiratory / Immuno", "name": "asthma", "depth": "deep"},
    {"group": "Respiratory / Immuno", "name": "rheumatoid arthritis", "depth": "deep"},
    {"group": "Respiratory / Immuno", "name": "COPD", "depth": "medium"},
    {"group": "Neuro / Psych", "name": "Alzheimer disease", "depth": "deep"},
    {"group": "Neuro / Psych", "name": "depression", "depth": "deep"},
    {"group": "Neuro / Psych", "name": "Parkinson disease", "depth": "deep"},
    {"group": "Metabolic / Renal", "name": "type 2 diabetes", "depth": "reference"},
    {"group": "Metabolic / Renal", "name": "obesity", "depth": "medium"},
    {"group": "Metabolic / Renal", "name": "chronic kidney disease", "depth": "shallow"},
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
]

# Tier-3 / long tail + depth work still to do.
REMAINING_CONDITIONS = [
    {"group": "Oncology", "name": "cervical cancer"},
    {"group": "Oncology", "name": "esophageal cancer"},
    {"group": "Oncology", "name": "gastric cancer"},
    {"group": "Oncology", "name": "sarcoma"},
    {"group": "Cardiovascular", "name": "pulmonary hypertension"},
    {"group": "Cardiovascular", "name": "valvular heart disease"},
    {"group": "Infectious", "name": "malaria"},
    {"group": "Infectious", "name": "HPV"},
    {"group": "Neuro / Psych", "name": "Huntington disease"},
    {"group": "Neuro / Psych", "name": "PTSD"},
    {"group": "Neuro / Psych", "name": "ADHD"},
    {"group": "Immuno / Rheum", "name": "Sjögren syndrome"},
    {"group": "Immuno / Rheum", "name": "vasculitis"},
    {"group": "Metabolic / GI", "name": "celiac disease"},
    {"group": "Metabolic / GI", "name": "gout"},
    {"group": "Respiratory", "name": "pulmonary fibrosis"},
    {"group": "Respiratory", "name": "cystic fibrosis"},
    {"group": "Renal", "name": "polycystic kidney disease"},
    {"group": "Depth work", "name": "deepen hypertension / heart failure / CKD to ≥300 trials"},
    {"group": "Depth work", "name": "DailyMed bulk labels + FAERS breadth + Europe PMC full-text"},
]


def coverage_plan() -> dict:
    return {
        "sources": SOURCE_INVENTORY,
        "covered": COVERED_CONDITIONS,
        "remaining": REMAINING_CONDITIONS,
    }
