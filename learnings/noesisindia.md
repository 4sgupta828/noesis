# Noesis IN — the India mode (sub-vertical launch spec)

**Status:** SPEC v1 (panel review pending) · **Goal:** launch an INDIA MODE for Indian
doctors — public-and-legal content only, brand mapping approximated by curation (no
commercial DB license in v1). · **Companions:** `learnings/improvementloop.md` (the eval
loop that proves it), `learnings/knowledgegraph.md` (graph), CLAUDE.md kernel/vertical split.

## The product in one paragraph

An Indian clinician gets answers that cite ICMR/national-programme guidance FIRST where it
governs, know Indian brands ("Dolo 650" → paracetamol), reflect India-specific drug
regulation (CDSCO approvals, FDC bans, NLEM/DPCO pricing context) and India-population
evidence (Indian journals/cohorts), and watch India-relevant movement (outbreak-season
Pulse). Same kernel, same medical vertical — IN is a CONFIGURATION PROFILE: sources +
facets + directives + aliases, switchable per account.

## What already exists (inventory — this is a content+config layer, not a build-out)

- `india_guidelines` connector (ICMR + national programmes + societies, `source_country=IN`).
- `source_country` block stamping · `countries` retrieval scope · `country_boost` ranking.
- 12 India-programme conditions in coverage; India gold cases in the internal eval.
- Accounts capture `country` at registration → the natural IN-mode default.
- Improvement-loop harness (frozen slices, judge, taxonomy) ready for an India slice.

## Content plan (public + legal ONLY — the v1 constraint)

1. **India journals & population evidence (P0, existing connector).** Europe PMC already
   indexes the serious Indian journals (IJMR, JAPI, Indian Pediatrics, JPGM, Neurology
   India, Lung India…). Ingest = QUERY PACKS on the existing `europepmc` connector:
   per covered condition `"<condition> India"` cohort/management queries + journal-scoped
   pulls; all stamped IN. License: EPMC open-access terms (already relied on). The
   non-PubMed long tail (IndMED/medIND) is P2 — new scraper + terms check.
2. **India drug regulation (P0, one new connector).** `cdsco` connector: approved-drug
   lists, FDC ban notifications, safety alerts (cdsco.gov.in PDFs → docling, the
   guideline-connector pattern). Plus **National Formulary of India** (IPC PDF — India
   dosing) and **NLEM** (essential medicines + DPCO price-control annexures). Legal basis:
   Indian government open-data norms (NDSAP); verify per-document at fetch and echo the
   basis into the ingest manifest like the eval fetcher does.
3. **Brand→generic mapping, APPROXIMATED (P0, curated).** No CIMS/MIMS license in v1 and
   NO scraping of commercial drug sites (1mg/Practo ToS). Instead: a curated alias table
   of the top ~300–500 Indian brands sourced from PUBLIC artifacts (CDSCO approved lists,
   Jan Aushadhi catalogue, NLEM annexures) — `{brand, generic, strength_hint?, note}` in a
   vertical data file. Consumed three ways, all structural or LLM-owned (Rule 18 clean):
   (a) question understanding — brand mentions map to generics before retrieval (feeds the
   existing LLM topic-mapping vocabulary and the graph alias design from KG amendment C-4);
   (b) drug-kind registry nodes with brand aliases (v3 `kind` machinery, kind-filtered away
   from Pulse prompts); (c) an IN-mode compose addendum: mention the Indian brand
   parenthetically ONLY when the mapping table knows it (a structural lookup appended
   after compose, never an LLM guess — grounding untouched).
4. **Patient cases.** Published Indian case reports arrive via (1). REAL user cases are
   OUT OF SCOPE for this launch — they require a DPDP Act 2023 consent/de-identification
   pipeline, which is its own spec with its own panel review.
5. **Outbreak currency (P1).** IDSP weekly outbreak bulletins as Pulse change events —
   the currency subsystem consumes them as-is (new detector, declared-confidence tier).

## IN mode (the product switch)

- **Server-authoritative profile**: account `country=IN` defaults the profile ON; an
  explicit per-user toggle overrides; the resolved profile echoes to the FE on every
  answer (Rule 20 — FE never derives it independently).
- What flips when ON: retrieval `country_boost={IN}` (boost, never filter — global
  evidence still answers); IN-guideline-priority compose ADDENDUM (additive directive,
  ships dark; the validated base directive is untouched); brand alias lookup in question
  mapping + answer parentheticals; IN-flavored suggested watches.
- Kernel/vertical discipline: kernel gets NOTHING India-specific. The profile is manifest/
  vertical data + app config. A future "Noesis BR" reuses the same seams.

## Eval (launch gate — the improvement loop applied to IN)

- **India frozen slice** (~40 questions, held out): de-MCQ'd NEET-PG-style vignettes +
  India-programme scenarios (dengue warning signs, RHD prophylaxis, DIPSI thresholds,
  snakebite ASV, TB-preventive regimens) + brand-phrased consumer questions ("can I take
  Dolo 650 with...").
- **Metrics**: must-have recall (judge as today) · IN-source citation share on
  India-governed questions · brand-mapping hit rate (structural) · no-harm on the global
  K-QA slice (IN mode must not degrade global answers).
- **Launch bar**: IN slice recall ≥ global baseline; brand hit rate ≥80% on the curated
  set; zero global regression; all provenance recorded.

## Costs (per credit discipline)

Ingest = parsing + embeddings (no answer-path LLM; cheap). Query-pack drafting: ~1 small
call per condition (batched). Brand-table curation: structural extraction from public PDFs
+ one LLM normalization pass over ~500 rows (small). Eval: the India slice through the
standard loop (~40 answers + judging per turn — same as a K-QA turn). All spend-gated.

## Phasing

- **P0 (launch):** EPMC India query packs · `cdsco` connector + NFI/NLEM ingest · curated
  brand table (300–500) + question-mapping + parenthetical lookup · IN profile switch
  (server-authoritative, dark until eval passes) · India frozen slice + first
  measure/fix/re-measure turn.
- **P1:** IDSP→Pulse outbreak events · India masquerade edges (undifferentiated fever:
  dengue/malaria/scrub typhus/enteric fever/leptospirosis) · drug-kind graph nodes with
  brand aliases · brand table growth loop (eval-miss driven).
- **P2:** IndMED long-tail connector · DPDP-gated real-case pipeline (own spec) ·
  vernacular/Hindi phrasing support · commercial drug-DB license decision revisited with
  usage data.

## Risks / honest unknowns

- Gov-site fetch fragility (cdsco.gov.in structure churn) — connector needs the same
  fetch-hardening as other gov connectors; failures must be visible, not silent.
- Brand ambiguity: one brand ↔ multiple formulations/strengths (the Dolo range) — v1 maps
  brand→generic only; strength disambiguation stays with the LLM in context.
- FDC ban list churns — that's a FEATURE for Pulse (ban notifications = change events) but
  the ingest must re-sweep, not one-shot.
- India-journal evidence quality varies — the existing evidence-tier classifier + authority
  pyramid must grade IN sources honestly (no artificial boost of weak evidence; the boost
  is for RELEVANCE, not authority).
- Legal review of NDSAP applicability per source is assumed, not verified — flag any
  source whose terms are unclear rather than ingesting by default.
