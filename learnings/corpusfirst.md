# Corpus-First Sourcing — download the downloadable universe

**Directive (2026-08-12):** everything public+legal+API-accessible gets DOWNLOADED into the
corpus; web retrieval is reserved for frequently-changing or non-downloadable content.

## Why corpus > web-at-answer-time
Internal blocks get: dense+keyword hybrid search · our relevance/authority/recency ranking ·
evidence-tier classification · Pulse currency (retraction/supersession tracking) · stable
citations · reproducible evals. Web hits get none of that durably.

## The downloadable universe (inventory, by channel)

| Source | Channel | License | Status |
|---|---|---|---|
| Europe PMC / PMC OA (abstracts) | `europepmc` connector | OA terms | IN USE (condition packs ~150/cond) |
| **PMC OA FULL TEXT** | `NOESIS_EPMC_FULLTEXT=1` flag exists | OA subset | **flip + re-pack top conditions** |
| **MMWR (both series)** | EPMC journal pack | public domain | **QUEUED 2026-08-12** |
| **Bulletin of the WHO** | EPMC journal pack | CC | **QUEUED 2026-08-12** |
| ClinicalTrials.gov | `clinicaltrials` connector | public | IN USE (300/cond cap — deepen) |
| DailyMed labels | `dailymed` connector | public domain | top-76 drugs done — **bulk remainder** |
| openFDA (labels/enforcement) | `openfda` connector | public | keyless rate-limited; API key = user action |
| FAERS | `faers` connector | public | top-76 — widen with DailyMed remainder |
| CDC open data catalog | `cdc` connector | public domain | metadata only; MMWR covers guidance |
| Society guideline FULL TEXT | KDIGO/docling pattern | per-society | 27+18 registries curated; full-text expansion backlog |
| ICMR STW / NHM STG PDFs | direct PDF (verify per doc) | GoI public | summaries in; full text pending terms |
| StatPearls (NCBI Bookshelf) | — | CC BY-NC-ND (NON-COMMERCIAL) | **EXCLUDED** — Noesis is commercial; NC license bars ingest |
| WHO IRIS PDFs | direct — iris.who.int verified 200 (2026-08-12) | WHO OA | connector work: needs per-guideline URL discovery (T5) |

## Web-leg-only (correctly so)
UpToDate/Merck/Mayo (licensed/bot-walled reference) · publisher-walled journals (NEJM/JAMA
full text) · living pages (drug shortage notices, outbreak dashboards) · CDSCO/MoHFW
(bot-walled; curated summaries + web) · anything license-unclear.

## Phased tranches (each = parsing+embedding only, no answer-LLM spend)
- **T1 (DONE 2026-08-12):** MMWR ~450 + WHO Bulletin ~200 queued.
- **T2 (QUEUED 2026-08-12):** DailyMed remainder — 114 generics × 15 labels; FAERS widened +40 drugs.
- **T3 (QUEUED 2026-08-12):** NOESIS_EPMC_FULLTEXT=1 flipped in prod; 24 deep conditions re-packed at 100 papers each (full text where OA).
- **T4 (PARTIAL 2026-08-12):** CT.gov raised to 400/condition on the 24 deep conditions (queued with T3); StatPearls EXCLUDED (NC license); WHO IRIS verified reachable — URL-discovery connector goes to T5.
- **T5:** society full-text expansion (per-society direct PDFs, the KDIGO pattern).
- **T-LIC (Tier-1 license-safe fallback, 2026-08-17):** past the OA ceiling. Flagship
  guidelines (ACC/AHA, ESC, ACR, full ADA, GINA) are paywalled/bot-walled, but a large body
  of society CPGs are OA **and commercially reusable**. Panel (Codex + code-grounded; Gemini
  down on billing) established: "free to read" ≠ "commercially reusable" — PMC OA mixes
  commercial-allowed (cc0/cc-by) with **cc-by-nc (NON-commercial, EXCLUDE)**. Enforcement is
  at the **EPMC query** (`LICENSE:"cc by"` filter → NC never ingested); the `license` facet
  (added a2b9b39) records it for audit. **cc-by guideline supply verified: 1,411** vs 691
  cc-by-nc traps. EXCLUDE ECRI/AAFP/MAGICapp (terms), StatPearls/WHO IRIS (NC).
  - Query template: `<topic> AND PUB_TYPE:"Guideline" AND OPEN_ACCESS:y AND LICENSE:"cc by" AND IN_EPMC:y`
    (IN_EPMC:y guarantees full-text XML, not thin abstracts; NOESIS_EPMC_FULLTEXT=1 in prod).
  - **Tranche-1 QUEUED 2026-08-17:** 16 core clinical topics (HF, AFib, ACS, dyslipidemia,
    T2DM, CKD, asthma, COPD, stroke, epilepsy, sepsis, CAP, RA, VTE, MDD, osteoporosis) ×
    15 cc-by full-text guidelines each. ~$0.20 OpenAI embeds (separate from Anthropic/Google
    answer pools). Verified in prod: fresh docs stamp `lic='cc by'`, 40-98 blocks each.
  - **GOTCHA (2026-08-17):** the license-facet prereq deploy from the *prior* session had
    **silently FAILED** (Railway build 9be4716d) — prod ran old code, so the first ingest
    landed 396 blocks with `license=None`. Always confirm `railway deployment list` shows
    SUCCESS (not just that `railway up` returned) before trusting a facet is live. Re-ingest
    backfills facets: block upsert is `ON CONFLICT DO UPDATE SET facets=EXCLUDED.facets`, and
    content-addressed block_id means unchanged text isn't re-embedded (near-zero re-cost).
  - **T-LIC next:** USPSTF (public domain — needs a connector/registry entry, not europepmc);
    Cochrane PLS/abstracts (cc-by-nc → exclude full, abstracts case-by-case); widen topic set
    after tranche-1 verifies retrieval improves.
Ordering rationale: T1-T2 are unambiguous public domain; T3 multiplies span quality on
already-proven demand; T4-T5 need per-source checks. Coverage board + improvement-loop
`missing_evidence` findings steer which conditions deepen first.

## Aggressive-execution status (2026-08-12, evening)
- openFDA API key SET in prod (rate caps lifted) — re-ingest widened labels/enforcement next drain.
- **DailyMed chunking bug FIXED**: fetch_artifact now pulls the FULL SPL .xml (was metadata
  .json truncated at 6k chars → 1 block/label); re-ingest of all ~190 drugs queued → labels
  become genuinely searchable (~40-80 blocks each).
- T5 journal-door guideline packs (20 jobs) + full-text wave 2 (100 jobs, 50 conditions) queued.
- **India full-text parity (QUEUED 2026-08-12 evening):** the earlier India packs were
  abstract-era — re-queued under full text: 16 Indian journals × 100 (IN-stamped incl.
  J Family Med & Primary Care, Indian Heart J, IJ Nephrology/Psychiatry/Dermatology/TB) +
  26 India condition packs × 50 (unstamped per D-5; adds chikungunya, JE, leptospirosis,
  oral cancer, sickle cell, thalassemia). ICMR STW full-PDF discovery remains with IRIS in T5.
- NEXT-SESSION QUEUE (in priority order): MedlinePlus topic-file connector (consumer-gap
  killer per K-QA findings) · WHO IRIS DSpace connector · RxNorm/RxNav brand-mapping feed ·
  full legacy-EPMC replay AFTER volume growth (+30-40GB needed vs 48.8GB cap — user decision) ·
  web-leg raw archiving to R2.
