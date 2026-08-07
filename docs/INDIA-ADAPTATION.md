# Noesis for the India market

> Strategy + technical plan for adapting Noesis to India (Indian journals, guidelines, drugs,
> endemic diseases). India is the "underserved market OpenEvidence isn't saturating" wedge from
> `docs/GTM-AND-US-LAUNCH.md`. **Not legal advice** — confirm Indian regulatory points with counsel.

## Thesis
Noesis is vertical-agnostic and corpus-driven, so "make it work for India" = **feed it Indian
sources + teach the authority tiers to rank them + scope retrieval to India**. The
retrieval/grounding/panel machinery is unchanged. The defensible moat is **India-native evidence
(Indian guidelines + Indian brands + cost-aware answers)** — which OpenEvidence isn't building.

## The content work (the actual moat)
- **Journals:** JAPI, IJMR, Indian Pediatrics, Indian J. Endocrinology & Metabolism, Indian Heart
  Journal, JPGM, NMJI, Indian J. Pharmacology. Many are in PubMed/EuropePMC (existing connector
  reaches them); some live only in **IndMED / medIND / society sites** → need new connectors.
- **Guidelines (top tier for India):** **ICMR**, national programmes (**NTEP** TB, **NACO** HIV,
  **NVBDCP** dengue/malaria), societies (**RSSDI** diabetes, **API**, **CSI** cardiology). Must be
  ingested and ranked at guideline-tier.
- **Drugs (hardest, highest-value):** **NLEM** + **CDSCO** approved list; **Indian brand mapping**;
  **fixed-dose combinations** (ubiquitous, many irrational/banned); **pricing** (DPCO/NPPA caps,
  **Jan Aushadhi** generics). Cost is a first-class clinical factor in India.
- **Epidemiology / standard-of-care differ:** TB, dengue, typhoid (fluoroquinolone-resistant),
  falciparum (chloroquine-resistant), kala-azar, snakebite, rabies, RHD, very high T2D/anaemia
  prevalence, resource-constrained pathways. India guidelines must OUTRANK US ones when India-scoped.

## Architecture seams already present
- **`source_country` facet + `NOESIS_COUNTRY_SCOPE`** (`app.py:country_scope_enabled`,
  `_country_facets` → `{"source_country": picked + ("global",)}`) — region scoping is built.
  `ask(..., facets=...)` applies it as a hard filter. **Caveat (in code):** don't enable the flag
  until every block is tagged with `source_country`, or a scoped query returns empty.
- **Ingest stamping** — `runtime/ingest.py` `facet_overrides` stamps every block, e.g.
  `{"source_country": "IN"}`; `/admin/corpus/ingest` is the ingestion endpoint.
- **Evidence-fitness / authority tiers** (`evidence_kind`) — extend so ICMR/national-programme
  guidance ranks guideline-tier and Indian journals are graded.
- **Tenant isolation** — run India as its own tenant (or an `india-medical` vertical): its own
  corpus, examples, panel roster, clean from the US demo.
- **Specialist panel** — add India-relevant lenses/practice patterns (TB/dengue-tuned ID; cost-aware
  primary care). Roster is declarative config.

## Regulatory (India — different regime; generally lighter than FDA)
- **CDSCO** (not FDA); **Medical Device Rules 2017** classify SaMD by risk (A/B/C/D). A cited,
  HCP-facing evidence tool is low-risk — confirm with Indian regulatory counsel.
- **DPDP Act 2023** (Digital Personal Data Protection) — India's privacy law; build to it.
- **NMC + Telemedicine Practice Guidelines 2020** — keep HCP-facing, decision-support not directive.
- **ABDM** (Ayushman Bharat Digital Mission) — India's health-data stack; a future distribution
  advantage, not a launch requirement.

## GTM for India
- **Individuals:** ₹ pricing, far lower; the big lever is **medical education** (MBBS/MD, NEET-PG prep
  — enormous, willing to pay).
- **Institutions:** hospital chains (Apollo, Fortis, Manipal, Max), medical colleges, government/public-health.
- **Pharma:** Indian pharma is huge; med-affairs pays for evidence tooling.
- **Wedge:** "the evidence engine that knows Indian guidelines, Indian brands, and Indian costs."

## Build sequence
1. Ingest a lighthouse slice (ICMR + national-programme guidelines + top Indian journals), tagged
   `source_country=IN`.
2. Build the **Indian drug connector** (NLEM + CDSCO + brand/FDC map) — highest value, hardest.
3. Extend authority tiers so India guidelines rank top for India queries.
4. Stand up an `india` tenant/vertical (own corpus, examples, panel roster).
5. Tag everything with `source_country`, then enable `NOESIS_COUNTRY_SCOPE` + `countries=["IN"]`.
6. Measure with the India clinical-gold eval (below), like the US top-50.

---

## Implementation status (started)
- **India benchmark:** `packages/vertical_medical/.../eval_india_gold.py` — `INDIA_CLINICAL_GOLD`,
  **18 held-out cases** (11 high-risk endemic): NTEP TB, dengue (NSAID/aspirin + prophylactic-platelet
  traps), fluoroquinolone-resistant typhoid, chloroquine-resistant falciparum, snakebite
  (tourniquet trap), rabies PEP, RHD prophylaxis, kala-azar, NACO ART, T2D/HTN/anaemia (Indian
  guidance), GDM screening, leptospirosis, COPD, and an irrational-FDC absence case. Contamination-safe
  (graded output only); grades forbidden overclaims + evidence_floor + absence + risk weighting.
- **Baseline runner:** `scripts/run_india_baseline.py` — runs the set against a deployment (`/research`),
  scores deterministically. `COUNTRIES=IN` scopes retrieval once the flag + tagging are in place.
  Against the current global corpus it will EXPOSE the India evidence gap — that gap is the ingest target.

### Immediate next steps
- [ ] Run `scripts/run_india_baseline.py` against prod to get the **current-corpus India baseline**
      (shows how much of India the global corpus already covers, and where the gaps are).
- [ ] Build the ICMR / national-programme guideline connector; ingest tagged `source_country=IN`.
- [ ] Build the Indian drug/brand/FDC/NLEM connector (the moat).
- [ ] Extend `evidence_kind` authority tiers for Indian guideline sources.
- [ ] Enable `NOESIS_COUNTRY_SCOPE` for India once every block is `source_country`-tagged; re-run the
      eval to measure the lift.
