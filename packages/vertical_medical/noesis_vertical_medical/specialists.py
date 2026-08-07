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


# The full roster. The default Alpha panel is the first 3 (cross-cutting, question-agnostic: safety +
# rigor + integration). Condition specialists below can be swapped in from the UI.
SPECIALISTS: tuple[SpecialistConfig, ...] = (
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
    SpecialistConfig(
        id="primary_care", specialty="Primary Care / Internal Medicine",
        lens=("You are a primary-care internist on a case panel. Evaluate through the whole-patient lens: the "
              "standard of care and practical first-line management, how it applies across common comorbidities, "
              "and how the pieces integrate for a real patient. Ground every statement in the evidence."),
        focus="first-line management, standard of care, clinical practice guideline, practical management, comorbidities",
        source_keys=()),
    # --- condition specialists (swappable from the UI; not in the default set) ---
    SpecialistConfig(
        id="cardiology", specialty="Cardiology",
        lens=("You are a cardiologist on a case panel. Evaluate ONLY the cardiovascular dimension: "
              "cardiovascular outcomes (MI, stroke, heart-failure hospitalization, CV mortality), cardiac "
              "safety, and CV risk. Ground every statement in the evidence."),
        focus="cardiovascular outcomes, heart failure hospitalization, mortality, cardiac safety, cardiovascular risk",
        source_keys=("europepmc", "clinicaltrials", "web")),
    SpecialistConfig(
        id="nephrology", specialty="Nephrology",
        lens=("You are a nephrologist on a case panel. Evaluate ONLY the renal dimension: effects on kidney "
              "function (eGFR, CKD progression, albuminuria), renal dose adjustment, and nephrotoxicity. "
              "Ground every statement in the evidence."),
        focus="kidney function, eGFR decline, CKD progression, albuminuria, renal dose adjustment, nephrotoxicity",
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


def specialist(id: str) -> SpecialistConfig | None:
    return _BY_ID.get(id)


def default_panel() -> tuple[SpecialistConfig, ...]:
    return tuple(_BY_ID[i] for i in DEFAULT_PANEL_IDS if i in _BY_ID)


# Synthesis directive (opaque, threaded into the panel's grounded synthesis compose — same contract as
# answer_format). The synthesis composes ONLY from the pooled verified findings of the specialists.
PANEL_SYNTHESIS_DIRECTIVE = """\
You are the chair synthesizing a multi-specialist case panel into ONE coherent answer for the clinician.
Each specialist independently reviewed the evidence through their lens; their VERIFIED findings are the
ONLY facts you may use (reference them inline as [n]). Do NOT add any fact, number, dose, or claim not in
those findings.

Structure the answer:
## Panel consensus
Where the specialists AGREE — the integrated bottom line, with [n] citations.
## Specialist perspectives
The distinct, decision-relevant point each lens contributed (pharmacology: dosing/interactions/safety;
evidence quality: how strong the evidence is; primary care: practical first-line integration; and any
condition specialist). One tight line per lens, cited.
## Disagreement or tension
Where the specialists diverge or the evidence conflicts — name both sides and, where the evidence lets
you, why (different populations/endpoints/evidence tiers). If they fully agree, say so.
## What the evidence does not settle
Decision-relevant gaps the panel could not resolve.

Neutral synthesis, not individualized advice. Every factual sentence carries an inline [n]."""
