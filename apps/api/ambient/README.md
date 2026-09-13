# Ambient CDS — encounter-intelligence sub-app (US + India, MVP)

The differentiated layer that rides **on top of** an ambient scribe (see `learnings/cds-epic-plan.md`
Part III). It is **not** the note-taker — it is the **safety-and-correctness brain** over the encounter.
Mounted at **`/ambient`** in the main Noesis app; two modes (US / India) on one core; reuses the shipped
Rx-CDS safety engine (`api.rxcds`). Flag `NOESIS_AMBIENT` (default ON); `=0` is a no-op.

## The three phases (from a transcript + patient context)
- **Pre-visit** — detects conditions (transcript + chart), shows which guideline therapies are already
  present, and surfaces **evidence-anchored care gaps** (e.g. HFrEF missing a beta-blocker / MRA / SGLT2
  pillar; a doubly-indicated SGLT2i in HF+diabetes) plus actions (tobacco cessation, med reconciliation).
- **Encounter** — medications *heard in the conversation* (linked to the transcript span) run through the
  **real-time Rx-CDS safety engine** (interactions / dosing / contraindication / allergy), plus the
  care-gap prompts.
- **Post-visit** — **US:** DEFENSIBLE ICD-10 coding (only where the encounter supports it — MEAT — each
  code quotes its evidence) + an advisory E/M complexity hint. **India:** a patient summary (no HCC).

## The discipline (why it's a Noesis product, not a scribe)
- **Double grounding:** facts link to the **transcript span** they came from (Linked-Evidence parity);
  guideline recommendations are labelled clinical inference; every finding/gap/code carries a **cited basis**.
- **Congruence, not conformity:** care gaps are anchored to **guidelines**, never to "what most
  prescriptions look like" (the India validity trap).
- **Silence is never clearance:** missing data (unknown eGFR for an SGLT2i/MRA, no conditions detected,
  an unresolved drug name) is surfaced as an explicit "could not verify".
- **Defensible, not maximal, coding:** never suggests a code the encounter doesn't support (survives payer
  downcoding — the anti-"coding arms race" posture).
- **Advisory:** reviewable options + basis, clinician retains authority (FDA Criterion-4 posture US;
  CDSCO/NMC advisory posture India).

## Two modes, one core
The extraction + safety + care-gap engine is identical. Modes differ only in vocabulary (US generics vs
Indian brands — handled by the shared Rx-CDS resolver), guideline flavour, the post-visit output
(coding vs summary), and the regulatory disclaimer. See `modes.py`.

## Endpoints
- `GET  /ambient` — mobile demo UI (mode toggle + example cases incl. the "Alyssa" HF case).
- `POST /ambient/analyze` — `{transcript, patient:{...}, mode:"US"|"IN", recent_hospitalization}` → the
  three-phase result.
- `GET  /ambient/health`.

## Run / test
```bash
python3 -m pytest apps/api/ambient/tests apps/api/rxcds/tests -q   # 31 tests, no DB/LLM/network
```

## ⚠️ Seed data is ILLUSTRATIVE + deliberately NOT the note-taker
Care-gap rules and coding hints in `data.py` are a demonstration set, not a licensed guideline/coding
database; production binds care-gaps to the Noesis evidence engine and coding to a licensed grouper.
The **ambient capture itself (ASR + diarization + prose note)** is a **buy/partner** component and is out
of scope here — and **evaluating/correcting a third-party note-taker's output** is the planned next layer
(Part III §III.7, Option A).
