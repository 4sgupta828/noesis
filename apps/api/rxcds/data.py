"""Illustrative India drug-safety knowledge — SEED DATA for the MVP.

⚠️  THIS IS AN ILLUSTRATIVE SEED SET, NOT A LICENSED CLINICAL DATABASE. ⚠️
Production requires a licensed drug-interaction chemistry source (DrugBank / Lexicomp /
First Databank — India has no domestic equivalent) plus a hardened Indian brand normaliser
(60k-100k+ brands, FDC-heavy, no central registry). Every entry below carries a `basis`
citation so the engine can enforce its congruence rule; the citations name the KIND of
source a production system would bind to, and a few are paraphrased — verify against the
live source before any clinical use. See learnings/cds-epic-plan.md Part II.

Molecule names are lowercase canonical strings. Classes (e.g. "nsaid", "penicillin") let
allergy and drug-disease rules match a family without listing every member.
"""
from __future__ import annotations

from typing import Dict, List, Tuple

# --- Molecule classes ---------------------------------------------------------
# molecule -> classes it belongs to (used by allergy + drug-disease matching)
MOLECULE_CLASSES: Dict[str, List[str]] = {
    "ibuprofen": ["nsaid"],
    "diclofenac": ["nsaid"],
    "aceclofenac": ["nsaid"],
    "naproxen": ["nsaid"],
    "aspirin": ["nsaid", "salicylate", "antiplatelet"],
    "amoxicillin": ["penicillin", "betalactam"],
    "clavulanic acid": ["betalactam"],
    "ramipril": ["acei"],
    "enalapril": ["acei"],
    "atorvastatin": ["statin"],
    "clarithromycin": ["macrolide"],
    "azithromycin": ["macrolide"],
    "ciprofloxacin": ["fluoroquinolone"],
    "sertraline": ["ssri", "serotonergic"],
    "tramadol": ["opioid", "serotonergic"],
    "spironolactone": ["potassium-sparing-diuretic"],
    "furosemide": ["loop-diuretic"],
    "clopidogrel": ["antiplatelet"],
    "glimepiride": ["sulfonylurea"],
    # cardiometabolic / GDMT classes (used by the ambient care-gap engine)
    "lisinopril": ["acei"],
    "losartan": ["arb"],
    "sacubitril/valsartan": ["arni"],
    "metoprolol": ["beta-blocker", "gdmt-betablocker"],
    "carvedilol": ["beta-blocker", "gdmt-betablocker"],
    "bisoprolol": ["beta-blocker", "gdmt-betablocker"],
    "empagliflozin": ["sglt2"],
    "dapagliflozin": ["sglt2"],
    "eplerenone": ["potassium-sparing-diuretic", "mra"],
    "insulin glargine": ["insulin"],
    # anticoagulation / antiplatelet (afib, VTE, ASCVD)
    "warfarin": ["anticoagulant", "vka"],
    "apixaban": ["anticoagulant", "doac"],
    "rivaroxaban": ["anticoagulant", "doac"],
    "dabigatran": ["anticoagulant", "doac"],
    # respiratory controllers
    "budesonide/formoterol": ["ics-laba", "inhaled-controller"],
    "fluticasone/salmeterol": ["ics-laba", "inhaled-controller"],
    "tiotropium": ["lama", "inhaled-controller"],
    "albuterol": ["saba"],
    # psych / bone
    "escitalopram": ["ssri", "serotonergic"],
    "alendronate": ["bisphosphonate"],
}
# spironolactone is also an MRA (GDMT pillar) in addition to its class above
MOLECULE_CLASSES.setdefault("spironolactone", []).append("mra")

# --- Indian brand -> components (the normaliser seed) -------------------------
# key: lowercase brand token (with or without strength). value: list of components
#   {molecule, strength, unit, form}. FDCs have >1 component.
# Unknown/ambiguous brands are ABSTAINED on by the resolver — never guessed.
BRANDS: Dict[str, Dict] = {
    "dolo 650": {"components": [{"molecule": "paracetamol", "strength": 650, "unit": "mg", "form": "tablet"}]},
    "dolo": {"components": [{"molecule": "paracetamol", "strength": 500, "unit": "mg", "form": "tablet"}], "ambiguous_strength": True},
    "calpol": {"components": [{"molecule": "paracetamol", "strength": 500, "unit": "mg", "form": "tablet"}], "ambiguous_strength": True},
    "crocin": {"components": [{"molecule": "paracetamol", "strength": 500, "unit": "mg", "form": "tablet"}], "ambiguous_strength": True},
    "augmentin 625": {"components": [
        {"molecule": "amoxicillin", "strength": 500, "unit": "mg", "form": "tablet"},
        {"molecule": "clavulanic acid", "strength": 125, "unit": "mg", "form": "tablet"}]},
    "clavam 625": {"components": [
        {"molecule": "amoxicillin", "strength": 500, "unit": "mg", "form": "tablet"},
        {"molecule": "clavulanic acid", "strength": 125, "unit": "mg", "form": "tablet"}]},
    "mox 500": {"components": [{"molecule": "amoxicillin", "strength": 500, "unit": "mg", "form": "capsule"}]},
    "glycomet 500": {"components": [{"molecule": "metformin", "strength": 500, "unit": "mg", "form": "tablet"}]},
    "glycomet gp1": {"components": [
        {"molecule": "metformin", "strength": 500, "unit": "mg", "form": "tablet"},
        {"molecule": "glimepiride", "strength": 1, "unit": "mg", "form": "tablet"}]},
    "pan 40": {"components": [{"molecule": "pantoprazole", "strength": 40, "unit": "mg", "form": "tablet"}]},
    "pan-d": {"components": [
        {"molecule": "pantoprazole", "strength": 40, "unit": "mg", "form": "capsule"},
        {"molecule": "domperidone", "strength": 30, "unit": "mg", "form": "capsule"}]},
    "warf 5": {"components": [{"molecule": "warfarin", "strength": 5, "unit": "mg", "form": "tablet"}]},
    "brufen 400": {"components": [{"molecule": "ibuprofen", "strength": 400, "unit": "mg", "form": "tablet"}]},
    "hifenac": {"components": [{"molecule": "aceclofenac", "strength": 100, "unit": "mg", "form": "tablet"}]},
    "voveran": {"components": [{"molecule": "diclofenac", "strength": 50, "unit": "mg", "form": "tablet"}]},
    "cardace 5": {"components": [{"molecule": "ramipril", "strength": 5, "unit": "mg", "form": "tablet"}]},
    "envas 5": {"components": [{"molecule": "enalapril", "strength": 5, "unit": "mg", "form": "tablet"}]},
    "amlong 5": {"components": [{"molecule": "amlodipine", "strength": 5, "unit": "mg", "form": "tablet"}]},
    "storvas 10": {"components": [{"molecule": "atorvastatin", "strength": 10, "unit": "mg", "form": "tablet"}]},
    "clarithro 500": {"components": [{"molecule": "clarithromycin", "strength": 500, "unit": "mg", "form": "tablet"}]},
    "azithral 500": {"components": [{"molecule": "azithromycin", "strength": 500, "unit": "mg", "form": "tablet"}]},
    "cifran 500": {"components": [{"molecule": "ciprofloxacin", "strength": 500, "unit": "mg", "form": "tablet"}]},
    "ultracet": {"components": [
        {"molecule": "tramadol", "strength": 37.5, "unit": "mg", "form": "tablet"},
        {"molecule": "paracetamol", "strength": 325, "unit": "mg", "form": "tablet"}]},
    "daxid 50": {"components": [{"molecule": "sertraline", "strength": 50, "unit": "mg", "form": "tablet"}]},
    "aldactone 25": {"components": [{"molecule": "spironolactone", "strength": 25, "unit": "mg", "form": "tablet"}]},
    "gabapin 300": {"components": [{"molecule": "gabapentin", "strength": 300, "unit": "mg", "form": "capsule"}]},
    "ecosprin 75": {"components": [{"molecule": "aspirin", "strength": 75, "unit": "mg", "form": "tablet"}]},
    "clopilet 75": {"components": [{"molecule": "clopidogrel", "strength": 75, "unit": "mg", "form": "tablet"}]},
    "lanoxin": {"components": [{"molecule": "digoxin", "strength": 0.25, "unit": "mg", "form": "tablet"}]},
    "lasix 40": {"components": [{"molecule": "furosemide", "strength": 40, "unit": "mg", "form": "tablet"}]},
    "thyronorm 50": {"components": [{"molecule": "levothyroxine", "strength": 50, "unit": "mcg", "form": "tablet"}]},
    # --- US generic names (molecule == "brand"); lets the ambient engine resolve US-mode meds.
    # Single-molecule generics resolve WITHOUT a strength (a transcript says "lisinopril", not a dose):
    # interaction/contraindication screening needs the molecule, not the strength. Dose-range checks
    # simply don't fire without dose_mg (that is correct — they abstain, surfaced as a coverage note).
    "lisinopril": {"components": [{"molecule": "lisinopril", "strength": None, "unit": "mg", "form": "tablet"}]},
    "losartan": {"components": [{"molecule": "losartan", "strength": None, "unit": "mg", "form": "tablet"}]},
    "metoprolol": {"components": [{"molecule": "metoprolol", "strength": None, "unit": "mg", "form": "tablet"}]},
    "carvedilol": {"components": [{"molecule": "carvedilol", "strength": None, "unit": "mg", "form": "tablet"}]},
    "bisoprolol": {"components": [{"molecule": "bisoprolol", "strength": None, "unit": "mg", "form": "tablet"}]},
    "empagliflozin": {"components": [{"molecule": "empagliflozin", "strength": None, "unit": "mg", "form": "tablet"}]},
    "jardiance": {"components": [{"molecule": "empagliflozin", "strength": None, "unit": "mg", "form": "tablet"}]},
    "dapagliflozin": {"components": [{"molecule": "dapagliflozin", "strength": None, "unit": "mg", "form": "tablet"}]},
    "farxiga": {"components": [{"molecule": "dapagliflozin", "strength": None, "unit": "mg", "form": "tablet"}]},
    "sacubitril/valsartan": {"components": [{"molecule": "sacubitril/valsartan", "strength": None, "unit": "mg", "form": "tablet"}]},
    "entresto": {"components": [{"molecule": "sacubitril/valsartan", "strength": None, "unit": "mg", "form": "tablet"}]},
    "eplerenone": {"components": [{"molecule": "eplerenone", "strength": None, "unit": "mg", "form": "tablet"}]},
    "metformin": {"components": [{"molecule": "metformin", "strength": None, "unit": "mg", "form": "tablet"}]},
    "atorvastatin": {"components": [{"molecule": "atorvastatin", "strength": None, "unit": "mg", "form": "tablet"}]},
    "furosemide": {"components": [{"molecule": "furosemide", "strength": None, "unit": "mg", "form": "tablet"}]},
    "insulin glargine": {"components": [{"molecule": "insulin glargine", "strength": None, "unit": "unit", "form": "injection"}]},
    "warfarin": {"components": [{"molecule": "warfarin", "strength": None, "unit": "mg", "form": "tablet"}]},
    "apixaban": {"components": [{"molecule": "apixaban", "strength": None, "unit": "mg", "form": "tablet"}]},
    "eliquis": {"components": [{"molecule": "apixaban", "strength": None, "unit": "mg", "form": "tablet"}]},
    "rivaroxaban": {"components": [{"molecule": "rivaroxaban", "strength": None, "unit": "mg", "form": "tablet"}]},
    "xarelto": {"components": [{"molecule": "rivaroxaban", "strength": None, "unit": "mg", "form": "tablet"}]},
    "dabigatran": {"components": [{"molecule": "dabigatran", "strength": None, "unit": "mg", "form": "capsule"}]},
    "clopidogrel": {"components": [{"molecule": "clopidogrel", "strength": None, "unit": "mg", "form": "tablet"}]},
    "plavix": {"components": [{"molecule": "clopidogrel", "strength": None, "unit": "mg", "form": "tablet"}]},
    "aspirin": {"components": [{"molecule": "aspirin", "strength": None, "unit": "mg", "form": "tablet"}]},
    "sertraline": {"components": [{"molecule": "sertraline", "strength": None, "unit": "mg", "form": "tablet"}]},
    "escitalopram": {"components": [{"molecule": "escitalopram", "strength": None, "unit": "mg", "form": "tablet"}]},
    "alendronate": {"components": [{"molecule": "alendronate", "strength": None, "unit": "mg", "form": "tablet"}]},
    "budesonide/formoterol": {"components": [{"molecule": "budesonide/formoterol", "strength": None, "unit": "mcg", "form": "inhaler"}]},
    "symbicort": {"components": [{"molecule": "budesonide/formoterol", "strength": None, "unit": "mcg", "form": "inhaler"}]},
    "fluticasone/salmeterol": {"components": [{"molecule": "fluticasone/salmeterol", "strength": None, "unit": "mcg", "form": "inhaler"}]},
    "advair": {"components": [{"molecule": "fluticasone/salmeterol", "strength": None, "unit": "mcg", "form": "inhaler"}]},
    "tiotropium": {"components": [{"molecule": "tiotropium", "strength": None, "unit": "mcg", "form": "inhaler"}]},
    "spiriva": {"components": [{"molecule": "tiotropium", "strength": None, "unit": "mcg", "form": "inhaler"}]},
    "albuterol": {"components": [{"molecule": "albuterol", "strength": None, "unit": "mcg", "form": "inhaler"}]},
    "gabapentin": {"components": [{"molecule": "gabapentin", "strength": None, "unit": "mg", "form": "capsule"}]},
    "tramadol": {"components": [{"molecule": "tramadol", "strength": None, "unit": "mg", "form": "tablet"}]},
    "ibuprofen": {"components": [{"molecule": "ibuprofen", "strength": None, "unit": "mg", "form": "tablet"}]},
    "naproxen": {"components": [{"molecule": "naproxen", "strength": None, "unit": "mg", "form": "tablet"}]},
    "clarithromycin": {"components": [{"molecule": "clarithromycin", "strength": None, "unit": "mg", "form": "tablet"}]},
    "spironolactone": {"components": [{"molecule": "spironolactone", "strength": None, "unit": "mg", "form": "tablet"}]},
    "ramipril": {"components": [{"molecule": "ramipril", "strength": None, "unit": "mg", "form": "tablet"}]},
    "amlodipine": {"components": [{"molecule": "amlodipine", "strength": None, "unit": "mg", "form": "tablet"}]},
    "levothyroxine": {"components": [{"molecule": "levothyroxine", "strength": None, "unit": "mcg", "form": "tablet"}]},
}

# --- CDSCO banned fixed-dose combinations (illustrative) ----------------------
# frozenset of component molecules -> {reason, basis}. Verify against current CDSCO
# gazette notifications; the ban list churns (it is itself a Pulse change-event source).
BANNED_FDCS: List[Dict] = [
    {"components": frozenset({"nimesulide", "paracetamol"}),
     "reason": "Nimesulide + paracetamol dispersible combination — CDSCO-prohibited (irrational; hepatotoxicity concern).",
     "basis": {"source": "CDSCO", "citation": "FDC prohibition notification (2016 tranche) — illustrative; verify current list."}},
    {"components": frozenset({"cefixime", "azithromycin"}),
     "reason": "Cefixime + azithromycin FDC — CDSCO-prohibited (irrational antimicrobial combination; AMR concern).",
     "basis": {"source": "CDSCO", "citation": "FDC prohibition notification (2016 tranche) — illustrative; verify current list."}},
    {"components": frozenset({"chlorpheniramine", "codeine"}),
     "reason": "Chlorpheniramine + codeine syrup — restricted/prohibited FDC.",
     "basis": {"source": "CDSCO", "citation": "FDC prohibition notification — illustrative; verify current list."}},
]

# --- Drug-drug interactions ---------------------------------------------------
# key: frozenset({molA, molB}) -> {severity, mechanism, management, basis}
# 'classes' key means the pair matches on class membership (either side).
DDI_PAIRS: List[Dict] = [
    {"pair": frozenset({"warfarin", "nsaid"}), "is_class": True, "severity": "major",
     "mechanism": "Additive GI/systemic bleeding risk; NSAIDs also displace warfarin and impair platelets.",
     "management": "Avoid; if unavoidable, gastroprotection + close INR/bleeding monitoring.",
     "basis": {"source": "Drug interaction reference", "citation": "Warfarin–NSAID major interaction (Lexicomp/BNF class monograph) — illustrative."}},
    {"pair": frozenset({"warfarin", "macrolide"}), "is_class": True, "severity": "major",
     "mechanism": "Macrolides inhibit warfarin metabolism (CYP) → raised INR, bleeding.",
     "management": "Prefer a non-interacting antibiotic; if used, monitor INR closely.",
     "basis": {"source": "Drug interaction reference", "citation": "Warfarin–macrolide interaction (Stockley's / BNF) — illustrative."}},
    {"pair": frozenset({"warfarin", "ciprofloxacin"}), "severity": "moderate",
     "mechanism": "Fluoroquinolone potentiates warfarin effect → raised INR.",
     "management": "Monitor INR; anticipate dose reduction.",
     "basis": {"source": "Drug interaction reference", "citation": "Warfarin–ciprofloxacin interaction — illustrative."}},
    {"pair": frozenset({"warfarin", "tramadol"}), "severity": "moderate",
     "mechanism": "Reports of raised INR with tramadol.",
     "management": "Monitor INR if co-prescribed.",
     "basis": {"source": "Drug interaction reference", "citation": "Warfarin–tramadol interaction — illustrative."}},
    {"pair": frozenset({"acei", "potassium-sparing-diuretic"}), "is_class": True, "severity": "major",
     "mechanism": "Additive potassium retention → hyperkalemia (can be fatal).",
     "management": "Avoid in renal impairment; monitor serum potassium and renal function.",
     "basis": {"source": "Drug interaction reference", "citation": "ACEi–potassium-sparing-diuretic hyperkalemia (BNF) — illustrative."}},
    {"pair": frozenset({"acei", "nsaid"}), "is_class": True, "severity": "moderate",
     "mechanism": "NSAIDs blunt ACEi antihypertensive effect and add nephrotoxicity (part of the 'triple whammy' with a diuretic).",
     "management": "Avoid chronic co-use; monitor BP + renal function.",
     "basis": {"source": "Drug interaction reference", "citation": "ACEi–NSAID interaction (BNF) — illustrative."}},
    {"pair": frozenset({"clarithromycin", "atorvastatin"}), "severity": "major",
     "mechanism": "Clarithromycin (CYP3A4 inhibitor) raises statin levels → myopathy/rhabdomyolysis.",
     "management": "Suspend the statin during the macrolide course, or use a non-interacting antibiotic.",
     "basis": {"source": "Drug interaction reference", "citation": "Clarithromycin–atorvastatin CYP3A4 interaction — illustrative."}},
    {"pair": frozenset({"clarithromycin", "digoxin"}), "severity": "moderate",
     "mechanism": "Macrolide raises digoxin levels → toxicity risk.",
     "management": "Monitor digoxin level and for toxicity.",
     "basis": {"source": "Drug interaction reference", "citation": "Clarithromycin–digoxin interaction — illustrative."}},
    {"pair": frozenset({"tramadol", "ssri"}), "is_class": True, "severity": "major",
     "mechanism": "Additive serotonergic effect → serotonin syndrome; tramadol also lowers seizure threshold.",
     "management": "Avoid combination where possible; counsel on serotonin-syndrome signs.",
     "basis": {"source": "Drug interaction reference", "citation": "Tramadol–SSRI serotonin-syndrome risk — illustrative."}},
    {"pair": frozenset({"clopidogrel", "pantoprazole"}), "severity": "moderate",
     "mechanism": "PPI (CYP2C19) may reduce clopidogrel activation → reduced antiplatelet effect.",
     "management": "Prefer pantoprazole over omeprazole (lower effect) or an H2 blocker; reassess necessity.",
     "basis": {"source": "Drug interaction reference", "citation": "Clopidogrel–PPI CYP2C19 interaction — illustrative."}},
    {"pair": frozenset({"digoxin", "furosemide"}), "severity": "moderate",
     "mechanism": "Loop-diuretic-induced hypokalemia potentiates digoxin toxicity.",
     "management": "Monitor potassium and digoxin level; replace potassium as needed.",
     "basis": {"source": "Drug interaction reference", "citation": "Digoxin–diuretic hypokalemia interaction — illustrative."}},
    {"pair": frozenset({"arni", "acei"}), "is_class": True, "severity": "contraindicated",
     "mechanism": "Sacubitril/valsartan (ARNI) with an ACE inhibitor → additive bradykinin, angioedema risk.",
     "management": "Do not co-prescribe; allow a 36-hour washout when switching between ACEi and ARNI.",
     "basis": {"source": "Label / guideline", "citation": "ARNI contraindicated with ACEi (angioedema) — illustrative."}},
    {"pair": frozenset({"anticoagulant", "nsaid"}), "is_class": True, "severity": "major",
     "mechanism": "Anticoagulant + NSAID → substantially increased GI/systemic bleeding risk.",
     "management": "Avoid the NSAID; use acetaminophen/topical analgesia; if unavoidable, gastroprotection + close monitoring.",
     "basis": {"source": "Drug interaction reference", "citation": "Anticoagulant–NSAID bleeding risk — illustrative."}},
    {"pair": frozenset({"anticoagulant", "antiplatelet"}), "is_class": True, "severity": "major",
     "mechanism": "Anticoagulant + antiplatelet → additive bleeding; combine only with a clear indication and duration.",
     "management": "Confirm the indication for dual therapy; minimize duration; add gastroprotection.",
     "basis": {"source": "Drug interaction reference", "citation": "Anticoagulant–antiplatelet bleeding risk — illustrative."}},
    {"pair": frozenset({"ssri", "nsaid"}), "is_class": True, "severity": "moderate",
     "mechanism": "SSRI + NSAID → increased upper-GI bleeding risk (additive antiplatelet effect).",
     "management": "Prefer acetaminophen; add gastroprotection if an NSAID is needed.",
     "basis": {"source": "Drug interaction reference", "citation": "SSRI–NSAID GI-bleeding risk — illustrative."}},
    {"pair": frozenset({"ssri", "anticoagulant"}), "is_class": True, "severity": "moderate",
     "mechanism": "SSRI + anticoagulant → increased bleeding risk.",
     "management": "Counsel on bleeding signs; monitor.",
     "basis": {"source": "Drug interaction reference", "citation": "SSRI–anticoagulant bleeding risk — illustrative."}},
]

# --- Drug-disease contraindications (comorbidity concurrency) ------------------
# {molecule OR class, condition-keywords, severity, reason, basis}
DRUG_DISEASE: List[Dict] = [
    {"match_class": "nsaid", "conditions": ["ckd", "chronic kidney disease", "renal", "aki"], "severity": "major",
     "reason": "NSAIDs reduce renal perfusion and worsen kidney function in CKD.",
     "basis": {"source": "KDIGO / guideline", "citation": "Avoid NSAIDs in CKD — illustrative."}},
    {"match_class": "nsaid", "conditions": ["peptic ulcer", "gi bleed", "gastric ulcer", "pud"], "severity": "major",
     "reason": "NSAIDs cause and worsen peptic ulceration / GI bleeding.",
     "basis": {"source": "Guideline", "citation": "NSAID contraindicated in active peptic ulcer — illustrative."}},
    {"match_class": "nsaid", "conditions": ["heart failure", "chf", "hfref"], "severity": "moderate",
     "reason": "NSAIDs cause fluid retention and can precipitate heart-failure decompensation.",
     "basis": {"source": "Guideline", "citation": "NSAID caution in heart failure — illustrative."}},
    {"match_class": "acei", "conditions": ["hyperkalemia", "hyperkalaemia"], "severity": "major",
     "reason": "ACE inhibitors raise serum potassium.",
     "basis": {"source": "Label", "citation": "ACEi caution in hyperkalemia — illustrative."}},
    {"match": "metformin", "conditions": ["metabolic acidosis", "lactic acidosis"], "severity": "major",
     "reason": "Metformin risks lactic acidosis in acidotic states.",
     "basis": {"source": "Label", "citation": "Metformin contraindicated in metabolic acidosis — illustrative."}},
    {"match_class": "fluoroquinolone", "conditions": ["myasthenia", "myasthenia gravis"], "severity": "major",
     "reason": "Fluoroquinolones can exacerbate myasthenia gravis.",
     "basis": {"source": "Label", "citation": "Fluoroquinolone boxed warning — myasthenia — illustrative."}},
]

# --- Renal dose adjustment (eGFR mL/min/1.73m2) -------------------------------
# molecule -> list of {max_egfr, action, severity, note, basis}. Rule fires when eGFR is
# BELOW max_egfr. If eGFR is unknown and the molecule is renally-significant, the engine
# emits an explicit "cannot verify" coverage gap instead of assuming normal function.
RENAL_RULES: Dict[str, List[Dict]] = {
    "metformin": [
        {"max_egfr": 30, "severity": "contraindicated", "action": "Contraindicated — stop metformin.",
         "note": "Lactic-acidosis risk when eGFR < 30.",
         "basis": {"source": "Label / KDIGO", "citation": "Metformin contraindicated eGFR<30 — illustrative."}},
        {"max_egfr": 45, "severity": "moderate", "action": "Do not initiate; if continuing, reduce dose and monitor.",
         "note": "Caution when eGFR 30-45.",
         "basis": {"source": "Label / KDIGO", "citation": "Metformin caution eGFR 30-45 — illustrative."}},
    ],
    "gabapentin": [
        {"max_egfr": 30, "severity": "moderate", "action": "Reduce dose substantially.",
         "note": "Renally cleared — accumulation/sedation when eGFR < 30.",
         "basis": {"source": "Label", "citation": "Gabapentin renal dose reduction — illustrative."}},
    ],
    "ciprofloxacin": [
        {"max_egfr": 30, "severity": "moderate", "action": "Reduce dose / extend interval.",
         "note": "Renal clearance reduced when eGFR < 30.",
         "basis": {"source": "Label", "citation": "Ciprofloxacin renal dose adjustment — illustrative."}},
    ],
    "digoxin": [
        {"max_egfr": 50, "severity": "moderate", "action": "Reduce dose; monitor level.",
         "note": "Renally cleared — toxicity risk in impairment.",
         "basis": {"source": "Label", "citation": "Digoxin renal dosing — illustrative."}},
    ],
    "spironolactone": [
        {"max_egfr": 30, "severity": "major", "action": "Avoid — hyperkalemia risk.",
         "note": "Potassium retention worsens with poor renal function.",
         "basis": {"source": "Label", "citation": "Spironolactone caution in renal impairment — illustrative."}},
    ],
}
# molecules for which unknown eGFR is itself worth surfacing (renally significant)
RENAL_SIGNIFICANT = set(RENAL_RULES.keys())

# --- Hepatic cautions ---------------------------------------------------------
HEPATIC_RULES: Dict[str, Dict] = {
    "atorvastatin": {"severity": "moderate", "note": "Statins can raise transaminases; caution/avoid in active liver disease.",
                     "basis": {"source": "Label", "citation": "Statin hepatic caution — illustrative."}},
    "warfarin": {"severity": "moderate", "note": "Hepatic impairment increases anticoagulant effect and bleeding risk.",
                 "basis": {"source": "Label", "citation": "Warfarin hepatic caution — illustrative."}},
    "paracetamol": {"severity": "moderate", "note": "Reduce maximum daily dose in significant hepatic impairment.",
                    "basis": {"source": "Label", "citation": "Paracetamol hepatic dose limit — illustrative."}},
}

# --- Pregnancy contraindications/cautions -------------------------------------
PREGNANCY_RULES: Dict[str, Dict] = {
    "warfarin": {"severity": "contraindicated", "note": "Teratogenic (warfarin embryopathy).",
                 "basis": {"source": "Label", "citation": "Warfarin contraindicated in pregnancy — illustrative."}},
    "ramipril": {"severity": "contraindicated", "note": "ACE-inhibitor fetopathy (2nd/3rd trimester).",
                 "basis": {"source": "Label", "citation": "ACEi contraindicated in pregnancy — illustrative."}},
    "enalapril": {"severity": "contraindicated", "note": "ACE-inhibitor fetopathy (2nd/3rd trimester).",
                  "basis": {"source": "Label", "citation": "ACEi contraindicated in pregnancy — illustrative."}},
    "atorvastatin": {"severity": "contraindicated", "note": "Statins contraindicated in pregnancy.",
                     "basis": {"source": "Label", "citation": "Statin contraindicated in pregnancy — illustrative."}},
    "diclofenac": {"severity": "major", "note": "NSAIDs — avoid, especially 3rd trimester (ductus closure).",
                   "basis": {"source": "Label", "citation": "NSAID caution in pregnancy — illustrative."}},
    "ciprofloxacin": {"severity": "moderate", "note": "Fluoroquinolone — generally avoided in pregnancy.",
                      "basis": {"source": "Label", "citation": "Fluoroquinolone caution in pregnancy — illustrative."}},
}

# --- Age-based cautions -------------------------------------------------------
# Pediatric: molecule -> {below_age, severity, note, basis}
PEDIATRIC_RULES: Dict[str, Dict] = {
    "aspirin": {"below_age": 16, "severity": "contraindicated",
                "note": "Avoid in children/adolescents (Reye's syndrome risk).",
                "basis": {"source": "Guideline", "citation": "Aspirin contraindicated <16y — illustrative."}},
    "ciprofloxacin": {"below_age": 18, "severity": "moderate",
                      "note": "Fluoroquinolones — caution in children (musculoskeletal effects).",
                      "basis": {"source": "Label", "citation": "Fluoroquinolone pediatric caution — illustrative."}},
}
# Geriatric (>= age): matched by molecule or class (Beers-style, illustrative)
GERIATRIC_RULES: List[Dict] = [
    {"match_class": "nsaid", "min_age": 65, "severity": "moderate",
     "note": "Avoid chronic NSAIDs in older adults (GI bleed, renal, CV).",
     "basis": {"source": "Beers criteria", "citation": "AGS Beers — NSAIDs in older adults — illustrative."}},
    {"match": "tramadol", "min_age": 65, "severity": "minor",
     "note": "Use caution in older adults (CNS effects, hyponatremia, seizure threshold).",
     "basis": {"source": "Beers criteria", "citation": "AGS Beers — tramadol — illustrative."}},
]

# --- Maximum daily dose (for the dose-range check) ----------------------------
# molecule -> {max_mg_per_day, adult_only, basis}
MAX_DAILY_DOSE: Dict[str, Dict] = {
    "paracetamol": {"max_mg_per_day": 4000,
                    "basis": {"source": "Label", "citation": "Paracetamol adult max 4 g/day — illustrative."}},
}


def all_molecules() -> List[str]:
    mols = set()
    for b in BRANDS.values():
        for c in b["components"]:
            mols.add(c["molecule"])
    return sorted(mols)
