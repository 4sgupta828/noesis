"""Medical relation vocabulary + curated edges for the Grounded Relationship Graph (spec P0).

Endpoints use the EXACT covered-condition registry labels (coverage.py) so C2 propagation and
A9 evidence legs land on canonical nodes — validated by test_graph_edges.py. Curated edges are
clinically ESTABLISHED relationships only (textbook-tier; the curator's trust substitutes for
per-edge evidence rows, per A4). `context_topic` carries the setting when the relationship is
context-bound (A6). `narrower_than` rows map composite registry topics onto their broad
subject so hierarchy traversal works from day one.
"""
from __future__ import annotations

GRAPH_RELATIONS = (
    "causes",              # A is an accepted etiology of B
    "increases_risk_of",   # A is an established risk factor for B
    "treats",              # A is an accepted treatment for B (curated only until harvester)
    "complication_of",     # A is a recognized complication of B
    "comorbid_with",       # established bidirectional association
    "narrower_than",       # topic hierarchy (A6) — never surfaced as a clinical relation
    # --- v3 hard-case relations (spec C-2). Direction: masquerader → cover-story.
    "mimics",                    # A masquerades as B clinically (distinguished_by on the edge)
    "underlies_presentation_of", # A is the hidden ETIOLOGY behind presentation B (amyloid→HFpEF)
    "precipitates",              # A acutely triggers/unmasks B (merged unmasks/precipitates)
    "manifests_as",              # A → finding (C4 intersection primitive; DARK until v3-P1)
)

_E = lambda s, r, o, ctx="", note="", dx="": {  # noqa: E731
    "subject": s, "relation": r, "object": o, "context_topic": ctx,
    "distinguished_by": dx, "label": "established", "confidence": 1.0, "note": note}

CURATED_EDGES: tuple[dict, ...] = (
    # --- renal / metabolic core
    _E("chronic kidney disease", "increases_risk_of", "anemia", "anemia of CKD",
       "EPO deficiency + iron dysregulation"),
    _E("chronic kidney disease", "increases_risk_of", "osteoporosis", "CKD mineral-bone disorder"),
    _E("type 2 diabetes", "increases_risk_of", "chronic kidney disease", "diabetic kidney disease"),
    _E("hypertension", "increases_risk_of", "chronic kidney disease"),
    _E("polycystic kidney disease", "causes", "chronic kidney disease"),
    _E("multiple myeloma", "increases_risk_of", "chronic kidney disease", "myeloma cast nephropathy"),
    _E("multiple myeloma", "causes", "anemia"),
    _E("systemic lupus erythematosus", "increases_risk_of", "chronic kidney disease",
       "lupus nephritis"),
    _E("gout", "comorbid_with", "chronic kidney disease"),
    _E("obesity", "increases_risk_of", "type 2 diabetes"),
    _E("obesity", "increases_risk_of", "NASH / MASH"),
    _E("NASH / MASH", "causes", "variceal bleeding / cirrhosis", "progression to cirrhosis"),
    _E("hepatitis B", "causes", "variceal bleeding / cirrhosis"),
    _E("hepatitis C", "causes", "variceal bleeding / cirrhosis"),
    # --- cardiovascular core
    _E("atrial fibrillation", "increases_risk_of", "stroke", "cardioembolic"),
    _E("hypertension", "increases_risk_of", "stroke"),
    _E("hypertension", "increases_risk_of", "heart failure"),
    _E("coronary artery disease", "causes", "heart failure", "ischemic cardiomyopathy"),
    _E("type 2 diabetes", "increases_risk_of", "coronary artery disease"),
    _E("hyperlipidemia", "increases_risk_of", "coronary artery disease"),
    _E("atrial fibrillation", "comorbid_with", "heart failure"),
    _E("rheumatoid arthritis", "increases_risk_of", "coronary artery disease",
       "accelerated atherosclerosis"),
    _E("preeclampsia", "increases_risk_of", "hypertension", "later chronic hypertension"),
    _E("pulmonary hypertension", "complication_of", "COPD", "group 3 PH"),
    # --- oncology risk
    _E("HPV", "causes", "cervical cancer"),
    _E("HPV", "increases_risk_of", "head and neck cancer", "oropharyngeal"),
    _E("GERD", "increases_risk_of", "esophageal cancer", "Barrett esophagus pathway"),
    _E("inflammatory bowel disease", "increases_risk_of", "colorectal cancer"),
    _E("celiac disease", "increases_risk_of", "lymphoma", "enteropathy-associated T-cell"),
    # --- infectious / immuno / neuro-psych
    _E("HIV", "increases_risk_of", "tuberculosis"),
    _E("HIV", "increases_risk_of", "lymphoma"),
    _E("influenza", "increases_risk_of", "community-acquired pneumonia",
       "secondary bacterial pneumonia"),
    _E("sepsis", "complication_of", "community-acquired pneumonia"),
    _E("depression", "comorbid_with", "anxiety disorder"),
    _E("Parkinson disease", "comorbid_with", "depression"),
    _E("Alzheimer disease", "increases_risk_of", "delirium (older adults)"),
    # --- topic hierarchy (A6): composite registry topics → broad subject
    _E("anemia in pregnancy", "narrower_than", "anemia"),
    _E("TB preventive treatment", "narrower_than", "tuberculosis"),
    _E("acute coronary syndrome", "narrower_than", "coronary artery disease"),
    _E("giant cell arteritis", "narrower_than", "vasculitis"),
    # ================= v3-P0 MASQUERADE SET (spec C-7) =================
    # Hidden etiologies and mimics behind common cover-story presentations — the connections
    # a linear search never makes because the answer topic is absent from the question.
    # Direction: masquerader → cover-story; consumed via INCOMING edges of the asked subject.
    # --- cardiology
    _E("cardiac amyloidosis", "underlies_presentation_of", "heart failure", "HFpEF phenotype",
       dx="LVH on echo with LOW-voltage ECG; carpal tunnel history"),
    _E("cardiac sarcoidosis", "underlies_presentation_of", "heart failure",
       "non-ischemic cardiomyopathy", dx="AV block or ventricular arrhythmia in a young patient"),
    _E("hyperthyroidism", "underlies_presentation_of", "atrial fibrillation",
       "new-onset AF", dx="suppressed TSH"),
    _E("infective endocarditis", "underlies_presentation_of", "stroke", "embolic stroke",
       dx="fever, new murmur, positive blood cultures"),
    # --- resistant / secondary hypertension
    _E("primary aldosteronism", "underlies_presentation_of", "hypertension",
       "resistant hypertension", dx="hypokalemia; aldosterone-renin ratio"),
    _E("pheochromocytoma", "underlies_presentation_of", "hypertension",
       "paroxysmal or labile hypertension", dx="episodic headache, palpitations, diaphoresis"),
    _E("renal artery stenosis", "underlies_presentation_of", "hypertension",
       "resistant hypertension", dx="flash pulmonary edema; creatinine rise on ACE inhibitor"),
    _E("obstructive sleep apnea", "underlies_presentation_of", "hypertension",
       "resistant nocturnal hypertension", dx="snoring, daytime somnolence, obesity"),
    # --- endocrine masquerades of psych/neuro presentations
    _E("hypothyroidism", "underlies_presentation_of", "depression", "",
       dx="elevated TSH; cold intolerance, weight gain, bradycardia"),
    _E("adrenal insufficiency", "underlies_presentation_of", "depression",
       "fatigue-predominant", dx="hyponatremia, hyperpigmentation, orthostatic hypotension"),
    _E("hyperthyroidism", "underlies_presentation_of", "anxiety disorder", "",
       dx="suppressed TSH; tremor, heat intolerance, weight loss"),
    _E("Wilson disease", "underlies_presentation_of", "Parkinson disease",
       "young-onset parkinsonism", dx="Kayser-Fleischer rings; low ceruloplasmin"),
    # --- anemia with a hidden driver
    _E("colorectal cancer", "underlies_presentation_of", "anemia",
       "iron-deficiency anemia in older adults", dx="occult GI blood loss — colonoscopy"),
    _E("celiac disease", "underlies_presentation_of", "anemia",
       "iron-refractory iron-deficiency anemia", dx="tissue transglutaminase antibodies"),
    _E("multiple myeloma", "underlies_presentation_of", "osteoporosis",
       "fragility fractures", dx="monoclonal protein; hypercalcemia, renal impairment"),
    _E("hemochromatosis", "underlies_presentation_of", "type 2 diabetes",
       "bronze diabetes", dx="elevated ferritin and transferrin saturation"),
    # --- the great chest imitators
    _E("sarcoidosis", "mimics", "tuberculosis", "granulomatous lung disease",
       dx="NON-caseating granulomas; negative mycobacterial studies"),
    _E("tuberculosis", "mimics", "sarcoidosis", "granulomatous lung disease",
       dx="caseating granulomas; positive AFB/culture/NAAT"),
    _E("lung cancer", "mimics", "tuberculosis", "non-resolving infiltrate or mass",
       dx="no response to anti-TB therapy; biopsy"),
    _E("tuberculosis", "mimics", "lung cancer", "pulmonary nodule or mass",
       dx="AFB positivity; response to anti-TB therapy"),
    _E("lymphoma", "mimics", "tuberculosis", "fever, night sweats, lymphadenopathy",
       dx="excisional node biopsy"),
    _E("pulmonary embolism", "mimics", "COPD", "exacerbation-like acute dyspnea",
       dx="hypoxia disproportionate to wheeze; no sputum change"),
    # --- oncology / systemic imitators
    _E("IgG4-related disease", "mimics", "pancreatic cancer", "pancreatic mass",
       dx="elevated serum IgG4; diffuse sausage-shaped pancreas; steroid response"),
)

# New condition-kind nodes this curated set legitimately mints into the registry
# (masqueraders are real conditions; the stability contract applies — minted once).
NEW_CONDITION_NODES: tuple[str, ...] = (
    "cardiac amyloidosis", "cardiac sarcoidosis", "sarcoidosis", "IgG4-related disease",
    "infective endocarditis", "primary aldosteronism", "pheochromocytoma",
    "renal artery stenosis", "obstructive sleep apnea", "hypothyroidism", "hyperthyroidism",
    "adrenal insufficiency", "hemochromatosis", "Wilson disease", "pulmonary embolism",
)


def curated_edges() -> list[dict]:
    return [dict(e) for e in CURATED_EDGES]


# v3-P1 LLM topic-mapping (the semantic layer over structural containment — spec C-4/C-0
# noted containment misses synonyms/abbreviations by design: "parkinsonism", "HFpEF", "afib").
# Fires ONLY when containment finds nothing; the model maps into a CLOSED shown vocabulary
# and code validates verbatim membership (Rule 18: LLM owns the judgment, never mints).
MAP_QUESTION_TOPICS_PROMPT = """A clinical question needs to be mapped onto a fixed list of graph topics.

Return the topics from the list that are the question's PRINCIPAL clinical subject(s) — the
condition(s) the question is fundamentally about, including when the question uses a synonym,
abbreviation, or related phrasing ("afib" → atrial fibrillation; "parkinsonism" → Parkinson
disease; "sugar problems" → type 2 diabetes).

STRICT rules:
- Copy topics EXACTLY VERBATIM from the list. Never invent, reword, or add topics.
- Only subjects the question is ABOUT — not every condition it merely mentions.
- Max 2. Return an empty list when nothing in the list genuinely covers the subject."""


# v3 growth campaign (spec C-6/C-7): LLM-drafted masquerade candidates per cover-story
# condition. Drafts are CANDIDATES ONLY — every one is corpus-entailment-verified (kernel
# graph.verify) before activation, and activation is capped at label 'supported'.
# Medical flavor for the KERNEL-NEUTRAL edge verifier (graph.verify.domain_directive):
GRAPH_VERIFY_DIRECTIVE = (
    "'Notable' means clinically actionable knowledge a good clinician uses — a recognized "
    "pitfall, workup branch, or differential the presentation demands — not a case-report "
    "curiosity or zebra trivia.")


DRAFT_MASQUERADE_PROMPT = """You are drafting HIDDEN-DIAGNOSIS knowledge for a clinical evidence graph.

Given a common condition (a "cover story" clinicians see every day), list the conditions that
classically MASQUERADE behind it — hidden etiologies or mimics that a good clinician must
actively consider, especially when the presentation is refractory or atypical.

STRICT rules:
- Only CLASSIC, clinically established masquerades (taught-in-training tier). No zebra
  case-report trivia. Max 4; fewer is better than padding.
- relation = "underlies_presentation_of" when the hidden condition CAUSES the presentation
  (amyloidosis behind HFpEF); "mimics" when it merely resembles it (sarcoidosis vs TB).
- subject = the HIDDEN condition (standard clinical name); the cover story is the given
  condition.
- distinguished_by = the concrete discriminating finding/test a clinician uses (short).
- context = when this masquerade matters ("resistant", "young-onset", "non-responding"), or "".
Return an empty list if the condition has no classic masquerades."""
