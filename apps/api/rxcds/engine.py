"""Deterministic, sub-second prescription-safety engine (Tier-1, LLM-free).

Given a prescription + patient context, returns typed findings. Contract:
  - Every Finding carries a non-empty `basis` (congruence rule — enforced in __post_init__).
  - Missing context becomes an explicit `coverage.unverifiable` gap — never silent clearance.
  - Findings are anchored to rule/guideline/label sources, never to peer-prescribing frequency.
  - Output is advisory; the prescriber retains authority.

Pure standard library (runs on 3.9+), so the whole thing is unit-testable with zero external
services and zero API spend.
"""
from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from itertools import combinations
from typing import Dict, List, Optional, Tuple

from . import data

logger = logging.getLogger("noesis.rxcds")

# Severity ordering (higher = more serious). "unverifiable" is a coverage gap, ranked with
# major so a genuine blind spot is never buried below minor noise.
_SEVERITY_RANK = {
    "contraindicated": 5,
    "major": 4,
    "unverifiable": 3,
    "moderate": 2,
    "minor": 1,
    "info": 0,
}


@dataclass
class Component:
    molecule: str
    strength: Optional[float] = None
    unit: Optional[str] = None
    form: Optional[str] = None


@dataclass
class NormalizedItem:
    """Result of resolving one written prescription line."""
    raw: str
    components: List[Component] = field(default_factory=list)
    resolved: bool = False
    ambiguity: Optional[str] = None      # populated when the resolver ABSTAINS
    dose_mg: Optional[float] = None       # mg per administration, if the caller supplied it
    frequency_per_day: Optional[float] = None

    def molecules(self) -> List[str]:
        return [c.molecule for c in self.components]

    def to_dict(self) -> Dict:
        return {
            "raw": self.raw,
            "resolved": self.resolved,
            "ambiguity": self.ambiguity,
            "components": [
                {"molecule": c.molecule, "strength": c.strength, "unit": c.unit, "form": c.form}
                for c in self.components
            ],
            "dose_mg": self.dose_mg,
            "frequency_per_day": self.frequency_per_day,
        }


@dataclass
class PatientContext:
    age_years: Optional[float] = None
    weight_kg: Optional[float] = None
    sex: Optional[str] = None                 # "male" / "female" / other
    pregnant: Optional[bool] = None
    egfr: Optional[float] = None              # mL/min/1.73m2
    hepatic_impairment: Optional[str] = None  # none/mild/moderate/severe/unknown
    allergies: List[str] = field(default_factory=list)   # molecules or classes, lowercase
    conditions: List[str] = field(default_factory=list)  # comorbidities, free text lowercased
    current_meds: List[str] = field(default_factory=list)  # already-active meds (brands or molecules)


@dataclass
class Finding:
    severity: str
    category: str
    title: str
    detail: str
    basis: Dict
    molecules: List[str] = field(default_factory=list)
    management: Optional[str] = None

    def __post_init__(self) -> None:
        # CONGRUENCE RULE: a finding with no cited basis cannot exist.
        if not self.basis or not self.basis.get("citation"):
            raise ValueError(f"Finding without a basis is forbidden: {self.title!r}")
        if self.severity not in _SEVERITY_RANK:
            raise ValueError(f"Unknown severity {self.severity!r}")

    def to_dict(self) -> Dict:
        return {
            "severity": self.severity,
            "category": self.category,
            "title": self.title,
            "detail": self.detail,
            "management": self.management,
            "molecules": self.molecules,
            "basis": self.basis,
        }


# --- Normalisation ------------------------------------------------------------

_MOLECULES_CACHE: Optional[set] = None


def _known_molecules() -> set:
    """All molecule names the engine knows (from brand components + class map). Cached."""
    global _MOLECULES_CACHE
    if _MOLECULES_CACHE is None:
        mols = set(data.MOLECULE_CLASSES.keys())
        for entry in data.BRANDS.values():
            for c in entry["components"]:
                mols.add(c["molecule"])
        _MOLECULES_CACHE = mols
    return _MOLECULES_CACHE


def _classes_of(molecule: str) -> List[str]:
    return data.MOLECULE_CLASSES.get(molecule, [])


def _matches_token(molecule: str, token: str) -> bool:
    """token may be a molecule name or a class name."""
    token = token.strip().lower()
    if not token:
        return False
    if token == molecule:
        return True
    return token in _classes_of(molecule)


def normalize(raw: str) -> NormalizedItem:
    """Resolve a written brand/line to components. ABSTAINS (resolved=False) on unknowns and
    on known-but-strength-ambiguous brands — it never guesses a molecule or strength."""
    key = " ".join(raw.strip().lower().split())
    entry = data.BRANDS.get(key)
    if entry is None:
        # try a strength-stripped fallback ("dolo 650" -> "dolo") only to report ambiguity
        base = key.split()[0] if key else ""
        if base in data.BRANDS:
            e2 = data.BRANDS[base]
            item = NormalizedItem(raw=raw)
            item.components = [Component(**c) for c in e2["components"]]
            item.resolved = False
            item.ambiguity = ("recognised brand family but the exact strength/formulation is not in "
                              "the table — not resolved (no strength guess).")
            return item
        # generic molecule name (e.g. "spironolactone", "warfarin") — resolve to the molecule itself.
        # Strength is legitimately absent for a bare molecule name; interaction/contraindication
        # screening needs the molecule, not the strength (dose checks simply abstain without a dose).
        if key in _known_molecules():
            item = NormalizedItem(raw=raw, resolved=True)
            item.components = [Component(molecule=key)]
            return item
        return NormalizedItem(raw=raw, resolved=False,
                              ambiguity="brand not in the normaliser table — could not resolve to a molecule.")
    item = NormalizedItem(raw=raw)
    item.components = [Component(**c) for c in entry["components"]]
    if entry.get("ambiguous_strength"):
        item.resolved = False
        item.ambiguity = "brand maps to a molecule but strength is ambiguous (multiple strengths marketed)."
    else:
        item.resolved = True
    return item


def _normalize_meds(raws: List[str]) -> List[NormalizedItem]:
    return [normalize(r) for r in raws if r and r.strip()]


# --- The checks ---------------------------------------------------------------

def _mol_index(items: List[NormalizedItem]) -> List[Tuple[str, NormalizedItem]]:
    """Flatten to (molecule, source_item) pairs for items that resolved to >=1 molecule."""
    out: List[Tuple[str, NormalizedItem]] = []
    for it in items:
        for m in it.molecules():
            out.append((m, it))
    return out


def _check_allergies(new_items: List[NormalizedItem], ctx: PatientContext, findings: List[Finding]) -> None:
    for mol, _ in _mol_index(new_items):
        for allergen in ctx.allergies:
            if _matches_token(mol, allergen):
                findings.append(Finding(
                    severity="contraindicated", category="drug-allergy",
                    title=f"Allergy conflict: {mol} vs documented allergy '{allergen}'",
                    detail=f"The patient has a documented allergy to '{allergen}', which matches {mol}.",
                    management="Do not prescribe; select an alternative from a different class.",
                    molecules=[mol],
                    basis={"source": "Patient allergy record", "citation": f"Documented allergy: {allergen}."},
                ))


def _check_banned_fdc(new_items: List[NormalizedItem], findings: List[Finding]) -> None:
    for it in new_items:
        mols = frozenset(it.molecules())
        for banned in data.BANNED_FDCS:
            if banned["components"].issubset(mols):
                findings.append(Finding(
                    severity="major", category="banned-fdc",
                    title=f"Banned fixed-dose combination: {it.raw}",
                    detail=banned["reason"],
                    management="Do not prescribe this combination product; prescribe the individual agents only if clinically indicated.",
                    molecules=sorted(banned["components"]),
                    basis=banned["basis"],
                ))


def _check_ddi(all_items: List[NormalizedItem], new_molset: set, findings: List[Finding]) -> None:
    idx = _mol_index(all_items)
    mols = sorted({m for m, _ in idx})
    seen = set()
    for a, b in combinations(mols, 2):
        # at least one side must be part of the NEW prescription (else it's a pre-existing pair)
        if a not in new_molset and b not in new_molset:
            continue
        for rule in data.DDI_PAIRS:
            pair = rule["pair"]
            hit = False
            if rule.get("is_class"):
                # pair holds molecule- or class-tokens; match either token against either drug
                toks = list(pair)
                hit = ((_matches_token(a, toks[0]) and _matches_token(b, toks[1])) or
                       (_matches_token(a, toks[1]) and _matches_token(b, toks[0])))
            else:
                hit = pair == frozenset({a, b})
            if hit:
                dedupe = (a, b, tuple(sorted(pair)))
                if dedupe in seen:
                    continue
                seen.add(dedupe)
                findings.append(Finding(
                    severity=rule["severity"], category="drug-drug-interaction",
                    title=f"Interaction: {a} + {b}",
                    detail=rule["mechanism"],
                    management=rule["management"],
                    molecules=[a, b],
                    basis=rule["basis"],
                ))


def _check_drug_disease(new_items: List[NormalizedItem], ctx: PatientContext, findings: List[Finding]) -> None:
    if not ctx.conditions:
        return
    conds = [c.strip().lower() for c in ctx.conditions if c.strip()]
    for mol, _ in _mol_index(new_items):
        for rule in data.DRUG_DISEASE:
            applies = (rule.get("match") == mol) or (
                rule.get("match_class") and rule["match_class"] in _classes_of(mol))
            if not applies:
                continue
            for cond in conds:
                if any(kw in cond for kw in rule["conditions"]):
                    findings.append(Finding(
                        severity=rule["severity"], category="drug-disease",
                        title=f"Comorbidity conflict: {mol} in patient with '{cond}'",
                        detail=rule["reason"],
                        management="Reconsider the agent given the comorbidity; choose a safer alternative or add monitoring.",
                        molecules=[mol],
                        basis=rule["basis"],
                    ))
                    break


def _check_renal(new_items: List[NormalizedItem], ctx: PatientContext, findings: List[Finding],
                 unverifiable: List[Dict]) -> None:
    for mol, _ in _mol_index(new_items):
        rules = data.RENAL_RULES.get(mol)
        if not rules:
            continue
        if ctx.egfr is None:
            # graceful degradation — do NOT assume normal renal function
            unverifiable.append({
                "molecule": mol,
                "why": f"{mol} needs renal dose assessment but eGFR/renal function was not provided — dose safety could NOT be confirmed.",
            })
            continue
        # fire the tightest matching threshold (rules sorted low->high eGFR ceiling)
        applicable = sorted([r for r in rules if ctx.egfr < r["max_egfr"]], key=lambda r: r["max_egfr"])
        if applicable:
            r = applicable[0]
            findings.append(Finding(
                severity=r["severity"], category="renal-dosing",
                title=f"Renal adjustment: {mol} at eGFR {ctx.egfr:g}",
                detail=f"{r['note']} {r['action']}",
                management=r["action"],
                molecules=[mol],
                basis=r["basis"],
            ))


def _check_hepatic(new_items: List[NormalizedItem], ctx: PatientContext, findings: List[Finding],
                   unverifiable: List[Dict]) -> None:
    impaired = ctx.hepatic_impairment in ("moderate", "severe")
    unknown = ctx.hepatic_impairment in (None, "unknown", "")
    for mol, _ in _mol_index(new_items):
        rule = data.HEPATIC_RULES.get(mol)
        if not rule:
            continue
        if impaired:
            findings.append(Finding(
                severity=rule["severity"], category="hepatic-dosing",
                title=f"Hepatic caution: {mol}",
                detail=rule["note"],
                management="Adjust dose or avoid given hepatic impairment; monitor liver function.",
                molecules=[mol], basis=rule["basis"],
            ))
        elif unknown:
            unverifiable.append({
                "molecule": mol,
                "why": f"{mol} carries a hepatic caution but hepatic status was not provided — safety could not be fully confirmed.",
            })


def _check_pregnancy(new_items: List[NormalizedItem], ctx: PatientContext, findings: List[Finding],
                     unverifiable: List[Dict]) -> None:
    mols = [m for m, _ in _mol_index(new_items)]
    relevant = [m for m in mols if m in data.PREGNANCY_RULES]
    if ctx.pregnant is True:
        for mol in relevant:
            rule = data.PREGNANCY_RULES[mol]
            findings.append(Finding(
                severity=rule["severity"], category="pregnancy",
                title=f"Pregnancy risk: {mol}",
                detail=rule["note"],
                management="Select a pregnancy-appropriate alternative.",
                molecules=[mol], basis=rule["basis"],
            ))
    elif ctx.pregnant is None and relevant and (ctx.sex == "female"):
        unverifiable.append({
            "molecule": ", ".join(relevant),
            "why": "Pregnancy-risk drug(s) prescribed to a female patient but pregnancy status was not recorded — could not verify.",
        })


def _check_age(new_items: List[NormalizedItem], ctx: PatientContext, findings: List[Finding]) -> None:
    if ctx.age_years is None:
        return
    for mol, _ in _mol_index(new_items):
        ped = data.PEDIATRIC_RULES.get(mol)
        if ped and ctx.age_years < ped["below_age"]:
            findings.append(Finding(
                severity=ped["severity"], category="pediatric",
                title=f"Pediatric caution: {mol} at age {ctx.age_years:g}",
                detail=ped["note"], management="Choose an age-appropriate alternative.",
                molecules=[mol], basis=ped["basis"],
            ))
        for g in data.GERIATRIC_RULES:
            applies = (g.get("match") == mol) or (g.get("match_class") and g["match_class"] in _classes_of(mol))
            if applies and ctx.age_years >= g["min_age"]:
                findings.append(Finding(
                    severity=g["severity"], category="geriatric",
                    title=f"Older-adult caution: {mol} at age {ctx.age_years:g}",
                    detail=g["note"], management="Review necessity; consider a safer alternative or lower dose.",
                    molecules=[mol], basis=g["basis"],
                ))


def _check_duplication(all_items: List[NormalizedItem], findings: List[Finding]) -> None:
    # molecule appearing in >1 resolved item (e.g. paracetamol hidden inside an FDC) -> duplication
    where: Dict[str, List[str]] = {}
    for it in all_items:
        for m in it.molecules():
            where.setdefault(m, []).append(it.raw)
    for mol, sources in where.items():
        if len(sources) > 1:
            findings.append(Finding(
                severity="moderate", category="therapeutic-duplication",
                title=f"Duplicate therapy: {mol} appears in {len(sources)} items",
                detail=f"{mol} is present in: {', '.join(sources)} — cumulative-dose/overlap risk (often hidden inside FDCs).",
                management="Consolidate to a single source of the molecule; check the cumulative daily dose.",
                molecules=[mol],
                basis={"source": "Prescription analysis", "citation": f"{mol} duplicated across {len(sources)} prescribed items."},
            ))


def _check_max_dose(new_items: List[NormalizedItem], findings: List[Finding],
                    unverifiable: List[Dict]) -> None:
    # aggregate daily dose per molecule across items that carry dose+frequency
    daily: Dict[str, float] = {}
    have_dose = False
    for it in new_items:
        if it.dose_mg and it.frequency_per_day:
            have_dose = True
            for c in it.components:
                # if the item is a single-molecule line, attribute dose to it; FDCs are skipped
                # (per-component dose parsing is out of MVP scope)
                if len(it.components) == 1:
                    daily[c.molecule] = daily.get(c.molecule, 0.0) + it.dose_mg * it.frequency_per_day
    for mol, mg in daily.items():
        rule = data.MAX_DAILY_DOSE.get(mol)
        if rule and mg > rule["max_mg_per_day"]:
            findings.append(Finding(
                severity="major", category="overdose",
                title=f"Dose exceeds maximum: {mol} {mg:g} mg/day",
                detail=f"Calculated daily dose {mg:g} mg exceeds the maximum {rule['max_mg_per_day']:g} mg/day.",
                management="Reduce dose or frequency below the maximum.",
                molecules=[mol], basis=rule["basis"],
            ))


# --- Orchestration ------------------------------------------------------------

def check_prescription(items_raw: List[str], ctx: PatientContext,
                       item_meta: Optional[List[Dict]] = None) -> Dict:
    """Run all deterministic checks. `items_raw` are the NEW prescription lines; `item_meta`
    optionally carries {dose_mg, frequency_per_day} per line (same order)."""
    t0 = time.perf_counter()
    new_items = _normalize_meds(items_raw)
    if item_meta:
        for it, meta in zip(new_items, item_meta):
            it.dose_mg = meta.get("dose_mg")
            it.frequency_per_day = meta.get("frequency_per_day")
    current_items = _normalize_meds(ctx.current_meds)
    all_items = new_items + current_items
    new_molset = {m for m, _ in _mol_index(new_items)}

    findings: List[Finding] = []
    unverifiable: List[Dict] = []

    _check_allergies(new_items, ctx, findings)
    _check_banned_fdc(new_items, findings)
    _check_ddi(all_items, new_molset, findings)
    _check_drug_disease(new_items, ctx, findings)
    _check_renal(new_items, ctx, findings, unverifiable)
    _check_hepatic(new_items, ctx, findings, unverifiable)
    _check_pregnancy(new_items, ctx, findings, unverifiable)
    _check_age(new_items, ctx, findings)
    _check_duplication(all_items, findings)
    _check_max_dose(new_items, findings, unverifiable)

    # unresolved items are a coverage gap, not a pass
    for it in new_items:
        if not it.resolved:
            unverifiable.append({
                "molecule": it.raw,
                "why": f"'{it.raw}' could not be normalised ({it.ambiguity}) — it was NOT screened for interactions/dosing.",
            })

    findings.sort(key=lambda f: (-_SEVERITY_RANK[f.severity], f.category))

    # coverage: what we could and could not evaluate. Silence != clearance.
    context_present = {
        "age": ctx.age_years is not None,
        "weight": ctx.weight_kg is not None,
        "egfr/renal": ctx.egfr is not None,
        "hepatic": ctx.hepatic_impairment not in (None, "unknown", ""),
        "pregnancy": ctx.pregnant is not None,
        "allergies": bool(ctx.allergies),
        "comorbidities": bool(ctx.conditions),
        "current_meds": bool(ctx.current_meds),
    }
    latency_ms = round((time.perf_counter() - t0) * 1000, 2)

    max_sev = max((f.severity for f in findings), key=lambda s: _SEVERITY_RANK[s], default="info")
    logger.info(
        "rxcds check: items=%d resolved=%d findings=%d unverifiable=%d max_severity=%s latency_ms=%.2f",
        len(new_items), sum(1 for it in new_items if it.resolved), len(findings),
        len(unverifiable), max_sev if findings else "none", latency_ms,
    )

    return {
        "findings": [f.to_dict() for f in findings],
        "normalization": [it.to_dict() for it in new_items],
        "coverage": {
            "context_present": context_present,
            "unverifiable": unverifiable,
            "evaluated": [
                "drug-allergy", "banned-fdc", "drug-drug-interaction", "drug-disease",
                "renal-dosing", "hepatic-dosing", "pregnancy", "age", "therapeutic-duplication",
                "max-daily-dose",
            ],
        },
        "summary": {
            "finding_count": len(findings),
            "max_severity": max_sev if findings else "none",
            "has_coverage_gaps": bool(unverifiable),
        },
        "latency_ms": latency_ms,
        "disclaimer": (
            "Advisory decision support only. Deterministic checks against an ILLUSTRATIVE seed "
            "knowledge base (not a licensed clinical database). The registered practitioner "
            "retains full responsibility for the prescription. Absence of a finding is not a "
            "guarantee of safety — review the coverage gaps."
        ),
    }
