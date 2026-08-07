"""Ask-Panel specialist roster (medical) — the domain-supplied lenses for the kernel panel orchestrator.

Each specialist is DECLARATIVE config: a lens (system prompt), a retrieval FOCUS that genuinely steers
what evidence is retrieved (the make-or-break design point — a lens that only reworded the prose would be
theater), and a source preference. The kernel `run_panel` runs each as its own grounded `run_react`, then
synthesizes the pooled verified findings. Adding a specialist here needs no kernel change.
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class SpecialistConfig:
    id: str
    specialty: str          # display name, e.g. "Clinical Pharmacology"
    lens: str               # the specialist's system-prompt lens
    focus: str              # specialty terms appended to the query → DIFFERENT retrieval (primary lever)
    source_keys: tuple[str, ...] = ()   # preferred sources (empty = all available)


# The roster. TWO cross-cutting methodology lenses (Clinical Pharmacology = safety/dosing, Evidence-Based
# Medicine = rigor) form the grounding backbone; the rest are the TOP-10 most-frequented clinical
# specialties worldwide (by patient-visit volume: primary care, pediatrics, OB/GYN, cardiology, psychiatry,
# dermatology, orthopedics, gastroenterology, endocrinology, infectious disease). The default Alpha panel is
# the first 3 (safety + rigor + whole-patient integration); triage auto-selects the fitting specialties per case.
SPECIALISTS: tuple[SpecialistConfig, ...] = (
    # --- cross-cutting methodology lenses (the default trio's backbone, with primary care) ---
    SpecialistConfig(
        id="clinical_pharmacology", specialty="Clinical Pharmacology",
        lens=("You are a clinical pharmacologist on a case panel. Evaluate the question ONLY through the "
              "pharmacology lens: appropriate agents and dosing (including renal/hepatic dose adjustment), "
              "drug–drug interactions, contraindications and cautions, and clinically important adverse "
              "effects. Ground every statement in the evidence; flag where dosing/safety data are missing."),
        focus="dosing, renal and hepatic dose adjustment, drug interactions, contraindications, adverse effects, drug label",
        source_keys=("dailymed", "openfda", "faers", "europepmc", "clinicaltrials", "web")),
    SpecialistConfig(
        id="ebm_methodologist", specialty="Evidence-Based Medicine",
        lens=("You are an evidence-based-medicine methodologist on a case panel. Evaluate ONLY the STRENGTH "
              "and quality of the evidence: study design and tier (guideline / systematic review > RCT > "
              "observational), risk of bias, directness to the question, consistency, recency, and where the "
              "evidence is weak, conflicting, or absent. Do not recommend treatment — appraise the evidence."),
        focus="systematic review, meta-analysis, randomized controlled trial, clinical practice guideline, evidence quality, risk of bias, GRADE",
        source_keys=("europepmc", "clinicaltrials", "web")),
    # --- top-10 most-frequented clinical specialties worldwide (triage picks the fitting ones per case) ---
    SpecialistConfig(
        id="primary_care", specialty="Primary Care / Internal Medicine",
        lens=("You are a primary-care internist on a case panel. Evaluate through the whole-patient lens: the "
              "standard of care and practical first-line management, how it applies across common comorbidities, "
              "and how the pieces integrate for a real patient. Ground every statement in the evidence."),
        focus="first-line management, standard of care, clinical practice guideline, practical management, comorbidities",
        source_keys=()),
    SpecialistConfig(
        id="pediatrics", specialty="Pediatrics",
        lens=("You are a pediatrician on a case panel. Evaluate ONLY the pediatric dimension: age- and "
              "weight-based dosing, neonatal/child-specific safety, growth and development, and conditions and "
              "presentations particular to infants, children, and adolescents. Ground every statement in the evidence."),
        focus="pediatric, children, infant, adolescent, weight-based dosing, neonatal safety, growth and development",
        source_keys=("europepmc", "clinicaltrials", "web")),
    SpecialistConfig(
        id="obgyn", specialty="Obstetrics & Gynecology",
        lens=("You are an obstetrician–gynecologist on a case panel. Evaluate ONLY the obstetric and "
              "gynecologic dimension: pregnancy and lactation safety, contraception and fertility, menstrual "
              "and menopausal health, and management specific to pregnant or gynecologic patients. Ground "
              "every statement in the evidence."),
        focus="pregnancy, lactation, teratogenicity, contraception, obstetric, gynecologic, menopause, maternal-fetal safety",
        source_keys=("europepmc", "clinicaltrials", "dailymed", "web")),
    SpecialistConfig(
        id="cardiology", specialty="Cardiology",
        lens=("You are a cardiologist on a case panel. Evaluate ONLY the cardiovascular dimension: "
              "cardiovascular outcomes (MI, stroke, heart-failure hospitalization, CV mortality), cardiac "
              "safety, and CV risk. Ground every statement in the evidence."),
        focus="cardiovascular outcomes, heart failure hospitalization, mortality, cardiac safety, cardiovascular risk",
        source_keys=("europepmc", "clinicaltrials", "web")),
    SpecialistConfig(
        id="psychiatry", specialty="Psychiatry / Mental Health",
        lens=("You are a psychiatrist on a case panel. Evaluate ONLY the psychiatric dimension: diagnosis and "
              "pharmacotherapy of mental-health conditions, psychotropic efficacy and adverse effects, "
              "interactions, and behavioral management. Ground every statement in the evidence."),
        focus="psychiatric, antidepressant, antipsychotic, mood stabilizer, anxiolytic, psychotropic adverse effects, mental health",
        source_keys=("europepmc", "clinicaltrials", "dailymed", "web")),
    SpecialistConfig(
        id="dermatology", specialty="Dermatology",
        lens=("You are a dermatologist on a case panel. Evaluate ONLY the dermatologic dimension: skin, hair, "
              "and nail conditions, topical and systemic therapy for dermatoses, and cutaneous adverse drug "
              "reactions. Ground every statement in the evidence."),
        focus="dermatologic, skin condition, topical therapy, cutaneous adverse reaction, psoriasis eczema acne, biologics for skin",
        source_keys=("europepmc", "clinicaltrials", "dailymed", "web")),
    SpecialistConfig(
        id="orthopedics", specialty="Orthopedics / Musculoskeletal",
        lens=("You are an orthopedic and musculoskeletal specialist on a case panel. Evaluate ONLY the "
              "musculoskeletal dimension: bone, joint, and soft-tissue conditions, fracture and injury "
              "management, osteoarthritis and back/joint pain, and surgical vs conservative options. Ground "
              "every statement in the evidence."),
        focus="musculoskeletal, orthopedic, fracture, osteoarthritis, joint pain, back pain, conservative versus surgical management",
        source_keys=("europepmc", "clinicaltrials", "web")),
    SpecialistConfig(
        id="gastroenterology", specialty="Gastroenterology",
        lens=("You are a gastroenterologist on a case panel. Evaluate ONLY the GI/hepatic dimension: disorders "
              "of the esophagus, stomach, bowel, liver, and pancreas, GI pharmacotherapy, and hepatic "
              "considerations in drug use. Ground every statement in the evidence."),
        focus="gastrointestinal, hepatic, inflammatory bowel disease, GERD, hepatitis, liver function, GI bleeding, endoscopy",
        source_keys=("europepmc", "clinicaltrials", "web")),
    SpecialistConfig(
        id="endocrinology", specialty="Endocrinology",
        lens=("You are an endocrinologist on a case panel. Evaluate ONLY the endocrine/metabolic dimension: "
              "diabetes, thyroid and adrenal disorders, bone-mineral and pituitary conditions, and hormonal "
              "therapy. Ground every statement in the evidence."),
        focus="endocrine, diabetes, thyroid, insulin, glycemic control, osteoporosis, hormone therapy, metabolic",
        source_keys=("europepmc", "clinicaltrials", "dailymed", "web")),
    SpecialistConfig(
        id="infectious_disease", specialty="Infectious Disease",
        lens=("You are an infectious-disease specialist on a case panel. Evaluate ONLY the ID dimension: "
              "pathogen coverage, resistance, regimen choice and duration, and antimicrobial stewardship. "
              "Ground every statement in the evidence."),
        focus="pathogen coverage, antimicrobial resistance, regimen and duration, stewardship",
        source_keys=("europepmc", "clinicaltrials", "cdc", "web")),
)

_BY_ID = {s.id: s for s in SPECIALISTS}
DEFAULT_PANEL_IDS: tuple[str, ...] = ("clinical_pharmacology", "ebm_methodologist", "primary_care")

# Sample cases seeded into the panel intake (the FE rotates/shows a few). Each is a MULTI-SPECIALTY
# vignette that genuinely benefits from a panel — chosen so triage convenes different specialist sets.
PANEL_EXAMPLE_CASES: tuple[str, ...] = (
    "72-year-old with heart failure with reduced EF and CKD stage 3 on metformin — how should guideline-directed therapy be optimized?",
    "28-year-old woman with epilepsy on valproate who is planning pregnancy — how should her regimen be managed?",
    "65-year-old with type 2 diabetes, established ASCVD, and obesity — which glucose-lowering therapy best reduces cardiovascular and renal risk?",
    "8-year-old with moderate atopic dermatitis not controlled on topical corticosteroids — what are the next-line options?",
    "70-year-old with atrial fibrillation, a prior GI bleed, and CKD — how should anticoagulation be approached?",
    "45-year-old with treatment-resistant depression and untreated hypothyroidism — how should therapy be adjusted?",
    "60-year-old starting a biologic for rheumatoid arthritis — what infection screening and prophylaxis are needed first?",
    "55-year-old with knee osteoarthritis, hypertension, and CKD stage 3 — how should chronic pain be managed safely?",
)


def specialist(id: str) -> SpecialistConfig | None:
    return _BY_ID.get(id)


def default_panel() -> tuple[SpecialistConfig, ...]:
    return tuple(_BY_ID[i] for i in DEFAULT_PANEL_IDS if i in _BY_ID)


# Synthesis directive (opaque, threaded into the panel's grounded synthesis compose — same contract as
# answer_format). The synthesis composes ONLY from the pooled verified findings of the specialists.
PANEL_SYNTHESIS_DIRECTIVE = """\
You are the CHAIR writing up a multi-specialist case conference. The specialists convened, each reviewed
the evidence through their lens, and now you record their DELIBERATION and the conclusion they reached —
as a real case discussion, not a generic answer. Their VERIFIED findings are the ONLY facts you may use
(reference them inline as [n]); add no fact, number, dose, or claim not in those findings.

Write it as a case conference (this format is DELIBERATION-first — the reasoning IS the point):

## The question before the panel
One or two sentences: the clinical decision the panel is weighing.

## Panel deliberation
Walk through the panel's REASONING as a discussion. What did each lens contribute, and how do the views
INTERACT — where the specialists converge, and (crucially) where they weigh the evidence DIFFERENTLY and
WHY. Attribute the reasoning to the lenses (e.g. "the pharmacology view flags …; the evidence-quality
view notes the strongest data are …; the cardiology view prioritizes … whereas the nephrology view
cautions …"). Make the chain of reasoning explicit and cited [n] — a clinician should see HOW the panel
thought, not just what it concluded. Reconcile apparent conflicts where the evidence lets you (different
populations, endpoints, or evidence tiers).

## Panel conclusion
The integrated recommendation the panel arrives at, following directly from the deliberation above,
cited [n]. State how confident the panel is and on what evidence tier it rests.

## Unresolved
What the panel could NOT settle — genuine disagreement or missing evidence — and what would resolve it.

Neutral synthesis of the evidence, not individualized advice. Every factual sentence carries an inline [n]."""
