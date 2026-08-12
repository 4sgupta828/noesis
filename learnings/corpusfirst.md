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
| StatPearls (NCBI Bookshelf) | Bookshelf API | CC BY-NC-ND — CHECK commercial use | pending legal |
| WHO IRIS PDFs | direct (URLs churned) | WHO OA | re-verify URLs |

## Web-leg-only (correctly so)
UpToDate/Merck/Mayo (licensed/bot-walled reference) · publisher-walled journals (NEJM/JAMA
full text) · living pages (drug shortage notices, outbreak dashboards) · CDSCO/MoHFW
(bot-walled; curated summaries + web) · anything license-unclear.

## Phased tranches (each = parsing+embedding only, no answer-LLM spend)
- **T1 (queued):** MMWR ~400 + WHO Bulletin ~200.
- **T2:** DailyMed bulk remainder (drug list from NLEM generics + top prescriptions) + FAERS widening.
- **T3:** EPMC FULL-TEXT flag flip + re-pack the 24 deep conditions (bigger blocks, better spans).
- **T4:** CT.gov depth (raise caps on deep conditions), StatPearls (post legal check), WHO IRIS re-verify.
- **T5:** society full-text expansion (per-society direct PDFs, the KDIGO pattern).
Ordering rationale: T1-T2 are unambiguous public domain; T3 multiplies span quality on
already-proven demand; T4-T5 need per-source checks. Coverage board + improvement-loop
`missing_evidence` findings steer which conditions deepen first.
