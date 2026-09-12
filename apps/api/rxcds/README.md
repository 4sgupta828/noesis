# Rx-CDS — real-time prescription-safety sub-app (India, MVP)

Tier-1 of the India prescription-CDSS in `learnings/cds-epic-plan.md` (Part II): a **sub-second,
LLM-free** deterministic rules engine that checks a prescription at the point of prescribing.
Mounted as an additive, isolated router under **`/rx`** in the main noesis FastAPI app — it never
touches the research/answer path. Ships with the existing Railway deploy.

## What it does
Given a prescription + patient context, returns typed, severity-ranked findings across:
drug–allergy, banned FDCs (CDSCO), drug–drug interactions (incl. across current meds /
comorbidity polypharmacy), drug–disease contraindications, renal & hepatic dose adjustment,
pregnancy, pediatric/geriatric cautions, therapeutic duplication (incl. molecules hidden inside
FDCs), and maximum-daily-dose.

## The design discipline (why it's a Noesis product, not another alert box)
- **Congruence, not just provenance** — every finding carries a cited `basis`. A rule with no
  basis cannot produce a finding (enforced in `engine.Finding.__post_init__`).
- **Silence is never clearance** — missing context (unknown eGFR, no allergy list, unresolved
  brand) is surfaced as an explicit `coverage.unverifiable` gap, never as an all-clear.
- **Evidence-anchored, not peer-conformity** — findings anchor to guideline/label/rule sources,
  never to "what most prescriptions look like" (the India validity trap: the majority pattern is
  often the irrational one).
- **Abstaining normaliser** — the Indian brand→molecule resolver abstains on unknown/ambiguous
  brands (no strength/ingredient guessing).
- **Advisory** — the registered practitioner retains authority (CDSCO SaMD / NMC posture).

## Endpoints
- `GET  /rx` — mobile-friendly demo UI (verified at 390px).
- `POST /rx/check` — `{prescription:[{text,dose_mg?,frequency_per_day?}], patient:{...}}` → findings.
- `GET  /rx/formulary` — known brands + molecules (demo autocomplete).
- `GET  /rx/health`.

Flag: `NOESIS_RXCDS` (default ON). `NOESIS_RXCDS=0` is a true no-op.

## Run / test
```bash
python3 -m pytest apps/api/rxcds/tests -q          # 19 tests, no DB / no LLM / no network
```
The engine is pure standard library (runs on 3.9+), so it is fully unit-testable offline with
zero API spend.

## ⚠️ Seed data is ILLUSTRATIVE, not a licensed clinical database
`data.py` is a hand-built demonstration set. Production requires: a **licensed DDI chemistry
source** (DrugBank / Lexicomp / First Databank — India has no domestic equivalent), a hardened
**Indian brand normaliser** (60k–100k+ brands, FDC-heavy, no central registry — the real moat and
cost), **ABDM/FHIR R4** patient-context ingestion, **DPDP Act 2023** data-residency + consent, and
**CDSCO SaMD** licensing. See `learnings/cds-epic-plan.md` Part II §II.7–II.10.

## Not built yet (deliberately — see the plan)
Async Tier-2 evidence/guideline-appropriateness layer (where the Noesis reasoning engine plugs
in), the evidence-anchored divergence/anomaly layer (DPDP-gated, staged last), and real
brand/DDI/guideline data. This MVP proves the **Tier-1 architecture, latency, and the safety
discipline** end to end.
