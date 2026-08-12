# Noesis IN — the India mode (sub-vertical launch spec)

**Status:** SPEC v2 — panel-reviewed (Codex + Gemini Pro + code-grounded subagent,
2026-08-12; all returned). Where the D-series amendments at the end conflict with the v1
body, the AMENDMENTS WIN (esp.: NFI dropped pending license · CDSCO as curated registry ·
brand resolver strength/FDC-aware and question-side only · tier-aware boost · clinician-
authored eval with paired IN-on/off gate). · **Goal:** launch an INDIA MODE for Indian
doctors — public-and-legal content only. · **Companions:** `learnings/improvementloop.md`,
`learnings/knowledgegraph.md`, CLAUDE.md kernel/vertical split.

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

---

# Panel Amendments (v2, D-series) — these override the v1 body above

Panel per Rule 17 (Codex GPT-5.5 + Gemini Pro + code-grounded subagent, all returned,
2026-08-12). Convergence was near-total on legality, brand safety, and ranking math.

## D-0 — Live bug found and FIXED during review

`_country_boost()` crashed (TypeError: set over a list of dicts) whenever countries were
passed with `NOESIS_COUNTRY_BOOST` on — IN mode's core mechanism was broken before it began.
Fixed + committed same day.

## D-1 — Legal re-scope: verify per artifact; NFI likely OUT (all three)

NDSAP covers open-data portals, NOT ministry PDFs by default. CDSCO gazette-type FDC-ban
notifications are firmer public-record ground; the **National Formulary of India is IPC
copyright — verify or DROP from P0**. Substitute the explicitly-open sources the spec
missed: **MoHFW/NHM Standard Treatment Guidelines and ICMR Standard Treatment Workflows**
(+ FOGSI/IAP society guidance where terms allow). HARD INGEST GATE: a per-artifact legal
manifest (exact URL, license basis, allowed use, attribution, reviewed-by, date) — nothing
ingests on an assumed license. EPMC packs are legally fine but will be abstract-heavy for
Indian society journals (honesty note, not a blocker).

## D-2 — CDSCO connector re-scoped (subagent: "same pattern" was false)

`india_guidelines` is a static curated registry — it cannot discover documents. CDSCO's
ASP.NET portal + scanned-image PDFs break both discovery and parsing. **P0 = curated
registry ENTRIES** (consolidated FDC-ban list + current approved list, hand-registered,
legal-checked); live crawling + OCR hardening is P1 with a named maintenance owner.

## D-3 — Brand mapping: strength/FDC-aware, question-side only, abstaining (all three)

India's market is FDC-dominated (>100k brands); 300–500 singles will feel broken and —
worse — mapping "Augmentin 625" to bare "amoxicillin/clavulanate" and letting the LLM
infer strength is a CLINICAL HAZARD. Redesign: table rows are
`{brand, generic(s), strength, form, combination components}` including top FDCs; the
resolver returns `{generic, strength, form, ambiguity}` and ABSTAINS on unknowns/ambiguity
(never an LLM guess of strength or ingredient). **Answer-side parentheticals are CUT from
P0** — brand mapping ships as question understanding only. Feasibility correction
(subagent): the existing LLM topic-mapping feeds GRAPH LEGS only; brand→generic needs a
NEW pre-retrieval rewrite seam, and no alias table exists yet (new schema) — priced as
build, not config. De-circularize the launch bar: hit rate is measured on HELD-OUT
brand-phrased questions the curators never saw.

## D-4 — Ranking safety: the boost must be tier-aware (all three; verified math)

As built, `country_boost` is a flat +0.12 at compose-cap claim selection while the whole
evidence-tier range is worth ≤0.15 — an IN-stamped case report can displace a global
systematic review. Fixes: (a) tier-gate or tier-scale the country boost (apply only at/
above a rank floor, or × rank/6); (b) held-out eval case: a global guideline MUST beat an
IN case report; (c) code-guard that the HARD `country_scope` filter can never combine with
the IN default (accidental evidence-blinding); (d) spec language corrected: the boost acts
at final claim selection, NOT retrieval — if IN evidence doesn't survive retrieval+
extraction, the boost lifts nothing (which is why D-6 matters).

## D-5 — IN-stamping precision (subagent)

Blanket-stamping every block of a `"<condition> India"` EPMC job as `source_country=IN`
poisons the boost signal (such queries return plenty of non-India papers). Stamp by
journal allowlist or LLM affiliation judgment; fail-safe = UNSTAMPED.

## D-6 — Indian web domains (cheap P0 the spec missed entirely — subagent)

`TRUSTED_WEB_DOMAINS` contains ZERO Indian domains — in IN mode the web leg structurally
cannot surface icmr.nic.in / mohfw.gov.in / tbcindia.gov.in / cdsco.gov.in / society sites.
Add them + their `WEB_DOMAIN_FACETS` tiers in P0.

## D-7 — Profile plumbing priced honestly + the conflict protocol (Codex + subagent)

`/research` has no token auth and no per-user settings store — "server-authoritative IN
profile" is REAL BUILD (auth on research, account resolution, per-user preference storage),
not config; the v1 "content+config layer" framing under-priced it. The compose-addendum
seam DOES exist as claimed (`extra_directive`). The addendum gets an explicit DISAGREEMENT
PROTOCOL: when Indian programme guidance conflicts with global guidance, PRESENT BOTH and
label which governs for practice in India — never silently suppress either. Account
country ≠ patice jurisdiction: expose the resolved profile + a per-question
"practice context: India/global" override.

## D-8 — Eval gate redesign (all three)

- NO NEET-PG-derived questions (copyright + pretraining contamination + exam-trivia
  distribution): clinician-authored vignettes built from public guidelines.
- Launch bar replaced: paired **IN-mode ON vs OFF on the SAME India slice** (sign test,
  not means — n≈40 with known nondeterminism) + the K-QA global no-harm gate. Strict
  superiority on India-governed questions, not cross-slice non-inferiority.
- Adversarial cases required: an India-vs-global CONFLICT question; a banned-FDC question;
  an unknown-brand question that must degrade gracefully (abstain, not hallucinate).
- **Launch dependency**: Indian-clinician review of the 18 existing `india_guidelines`
  curated summaries (their own docstring says review is pending) before they serve as
  launch evidence.

## D-9 — Revised P0 (the launchable core)

1. Legal-manifest gate + per-artifact verification (D-1).
2. MoHFW/NHM STG + ICMR STW registry entries · CDSCO ban/approved lists as curated
   entries (D-2) · NLEM (single public PDF).
3. EPMC India query packs with PRECISION stamping (D-5).
4. Indian web domains + facets (D-6).
5. Tier-aware country boost + scope/boost mutual exclusion (D-4).
6. Brand resolver v1: strength/FDC-aware table, question-side only, abstaining (D-3).
7. Profile plumbing: /research auth + per-user IN toggle, server-authoritative echo (D-7)
   + conflict-protocol compose addendum (dark until eval passes).
8. India frozen slice (clinician-authored) + paired IN-on/off turn of the improvement loop.
CUT from P0: answer parentheticals · NFI · CDSCO crawler · IDSP/Pulse · IN-flavored
watches · drug-kind graph aliases (P1, after the alias schema exists).

---

# ⏸ PAUSED (2026-08-12) — resume state

**Everything below is BUILT, tested, deployed DARK (`NOESIS_IN_MODE` off in prod):**
tier-aware country boost + scope⊥boost guard · 17 Indian web domains + IN facets ·
india_brands.py (~97 strength/FDC rows incl. FabiFlu, abstaining resolver, planner-only
context via kernel `question_context`) · per-user prefs + /me/settings + server-authoritative
profile on /research(+stream) · completeness-first conflict addendum (REWRITTEN after gate
run #1) · 4 legal-gated registry entries (STW/CDSCO-FDC/NLEM/schemes — live and ranking) ·
~25 EPMC India jobs ingested (journal packs stamped IN, condition packs unstamped) ·
24-vignette India slice + paired gate runner with per-arm checkpointing.

**Gate run #1 verdict: NOT PASSED** (OFF 0.667 → ON 0.652, paired 4↑/6↓/11=; contradictions
4→2). Root causes fixed: the old addendum NARROWED answers (in-21 regression) — rewritten;
FabiFlu unmapped — added. OFF arm banked at `evals/india/india-arm-off.json` (23/24 healthy);
ON checkpoint deliberately cleared (old addendum).

**TO RESUME:** (1) `evals/india/run_india.py --confirm-spend` → gate run #2 (~25 answers:
fresh ON arm under the fixed addendum + 1 OFF gap + judging; OFF reused). (2) If paired sign
flips positive + K-QA no-harm → set `NOESIS_IN_MODE=1` + prod-verify via a signed-in IN
account. (3) Launch dependencies still open: Indian-clinician review of the 24 vignettes,
the ~97 brand rows, and the 18+4 registry summaries. (4) P1 backlog: boost-crowding guard
(in-23), IDSP→Pulse, India masquerade edges, brand growth loop, IndMED.
