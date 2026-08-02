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
]

# Tier-2: next high-research-volume conditions to ingest.
REMAINING_CONDITIONS = [
    {"group": "Oncology", "name": "pancreatic cancer"},
    {"group": "Oncology", "name": "ovarian cancer"},
    {"group": "Oncology", "name": "bladder cancer"},
    {"group": "Oncology", "name": "renal cell carcinoma"},
    {"group": "Oncology", "name": "glioblastoma"},
    {"group": "Oncology", "name": "multiple myeloma"},
    {"group": "Oncology", "name": "head and neck cancer"},
    {"group": "Cardiovascular", "name": "hyperlipidemia"},
    {"group": "Cardiovascular", "name": "peripheral artery disease"},
    {"group": "Cardiovascular", "name": "venous thromboembolism"},
    {"group": "Infectious", "name": "COVID-19"},
    {"group": "Infectious", "name": "tuberculosis"},
    {"group": "Infectious", "name": "sepsis"},
    {"group": "Infectious", "name": "hepatitis B"},
    {"group": "Infectious", "name": "influenza"},
    {"group": "Neuro / Psych", "name": "multiple sclerosis"},
    {"group": "Neuro / Psych", "name": "epilepsy"},
    {"group": "Neuro / Psych", "name": "migraine"},
    {"group": "Neuro / Psych", "name": "schizophrenia"},
    {"group": "Neuro / Psych", "name": "anxiety disorder"},
    {"group": "Neuro / Psych", "name": "bipolar disorder"},
    {"group": "Neuro / Psych", "name": "amyotrophic lateral sclerosis"},
    {"group": "Immuno / Rheum", "name": "psoriasis"},
    {"group": "Immuno / Rheum", "name": "inflammatory bowel disease"},
    {"group": "Immuno / Rheum", "name": "systemic lupus erythematosus"},
    {"group": "Immuno / Rheum", "name": "ankylosing spondylitis"},
    {"group": "Metabolic / GI", "name": "NASH / MASH"},
    {"group": "Metabolic / GI", "name": "GERD"},
    {"group": "Metabolic / GI", "name": "osteoporosis"},
    {"group": "Metabolic / GI", "name": "anemia"},
    {"group": "Other", "name": "chronic pain"},
]


def coverage_plan() -> dict:
    return {
        "sources": SOURCE_INVENTORY,
        "covered": COVERED_CONDITIONS,
        "remaining": REMAINING_CONDITIONS,
    }
