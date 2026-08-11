# Real-World Q&A Learning Strategy — measure, learn, and grow the graph from real questions

**Status:** PLAN v2 — panel-reviewed (Codex GPT-5.5 + Gemini 3.1 Pro + code-grounded subagent,
2026-08-11; all three returned). Where the Panel Amendments at the end conflict with the v1
body, the AMENDMENTS WIN. · **Companions:** `learnings/knowledgegraph.md` (the graph this
feeds), `learnings/evidencepulse.md` (currency)

## Why (the gap this closes)

Our eval gates are small and internally authored (9-case synthesis-precision, 50-case clinical
benchmark, per-feature held-outs). They catch regressions; they cannot tell us where we stand
against the real distribution of questions clinicians and patients actually ask, and they
generate no new signal about what to fix next. Meanwhile the graph needs realistic question
traffic to grow harvested edges, and the corpus needs a demand signal for gap-filling. One
harness feeds all three: **measure quality on real-world Q&A → route failures to the right
subsystem → grow the graph from our own grounded answers to those questions.**

## The datasets (license-check before ANY download — standing habit)

| Set | Size / gold | What it tests for us | License |
|---|---|---|---|
| **HealthBench** (OpenAI 2025) | 5k realistic health conversations; physician-written per-question rubrics; `hard` subset | Long-form answer quality — the closest match to what Noesis produces | MIT (verify at fetch) |
| **K-QA** (K Health 2024) | 201 real patient questions with clinician answers decomposed into must-have statements (+1k unanswered) | Essential-fact recall + contradiction rate at claim granularity — matches our claim structure | verify (GitHub) |
| **BioASQ** (task B) | Questions + GOLD PubMed snippets | RETRIEVAL recall directly (did we fetch the right evidence), independent of composition | registration req'd |
| **MedQA (USMLE)** | 12.7k MCQ | Clinical-knowledge accuracy gate; closed-book vs corpus-grounded delta | MIT |
| **MedMCQA** | 194k MCQ + explanations (AIIMS/NEET-PG) | Same, with India-programme overlap | verify |
| **PubMedQA** | 1k expert-labeled yes/no/maybe | Evidence-interpretation calibration | MIT (verify) |
| **TREC LiveQA-Med / MedicationQA** | real consumer questions + curated answers | Patient-mode phrasing distribution | verify |

Priority: **HealthBench-hard + K-QA first** (long-form, rubric/statement graded — our actual
product shape), BioASQ second (retrieval-only, cheap), MCQ sets last (accuracy gates only).

## The harness (`evals/realworld/`)

1. **Fetch + filter (free):** downloader per set (license echoed into the manifest);
   condition-filter via structural containment against the covered-conditions registry;
   stratified sampler (condition group × question type × patient/clinician register).
   Every sampled slice is FROZEN and versioned (`slice-<set>-<n>-<date>.jsonl`).
2. **Split discipline (Rule 5):** each set splits once into `dev` (iterate freely) and
   `test` (frozen, run sparingly, never inspected per-question). No eval question ever
   appears in any prompt, few-shot, fixture, or scratchpad visible at inference time.
3. **Runner:** executes a slice against local or prod `/research` (engine, flags, git SHA,
   model, corpus snapshot date all recorded per Rule 11); saves full answers + citations +
   diagnostics (incl. `graph_legs`) per question.
4. **Grading tiers (cost-explicit):**
   - **T0 structural (free):** grounded-rate, citation count, abstention rate, evidence-tier
     mix, retrieval recall vs BioASQ gold snippets, graph-leg contribution rate.
   - **T1 accuracy (~1 call/q):** MCQ letter extraction on MedQA/MedMCQA slices; PubMedQA
     yes/no/maybe.
   - **T2 rubric (~2-3 calls/q):** HealthBench rubric grading / K-QA must-have + contradiction
     scoring via LLM judge. Sampled slices only (default 50/run).
5. **Report:** per-run scorecard + diff vs previous run on the same frozen slice.

## The learning loop (the actual point)

Every failed/weak answer is classified per the Rule 8 taxonomy — **missing corpus evidence ·
wrong evidence selected · bad ranking · reasoning/composition failure · abstention despite
evidence · question-understanding failure** — and routed:

- missing evidence → the gap queue (corpus ingest jobs), tagged with the question that exposed it
- wrong evidence / ranking → retrieval tuning cases + candidate graph edges (a multi-hop miss
  is a missing edge by definition — the CKD-fatigue pattern)
- reasoning/composition → candidates for a directive A/B (092dd35 discipline: rewrites need a
  held-out win first; additive-only ships dark)
- systematic patterns (≥3 same-mode failures) → a named workstream, not a per-case patch (Rule 10)

**Graph growout from eval traffic:** the chain harvester (KG spec P1) runs on every eval
answer — shadow edges from OUR span-verified claims (never from dataset answer text: no license
contamination, and the trust model stays intact). Question-topic co-occurrence across slices
feeds a curation queue of candidate edges. Eval runs thus double as graph-density bootstrap:
by the time real user traffic scales, the graph has already seen thousands of realistic
questions.

## Success metrics (public, comparable)

- HealthBench-hard rubric score (published frontier baselines exist — we can place ourselves)
- K-QA must-have recall + contradiction rate
- BioASQ snippet recall (retrieval only — isolates the search stack)
- MCQ accuracy delta: corpus-grounded vs closed-book (proves the corpus EARNS its keep)
- Trend lines per condition group → where to invest corpus/graph next

## Cost model (explicit, per run)

T0 free · T1 ≈ N calls · T2 ≈ 2-3×N calls (N = slice size, default 50). Baseline campaign:
K-QA 50 + HealthBench-hard 50 at T2, BioASQ 100 at T0, MedQA 100 at T1 ≈ modest bounded spend,
repeated only on change-gates (not per-commit). Cadence: baseline once → weekly small slice →
full re-run when a major subsystem lands.

## Phasing

- **P0:** harness + K-QA/HealthBench fetch (license-verified) + frozen slices + T0/T2 baseline
  on 50+50 → first scorecard + failure taxonomy.
- **P1:** routing loop live (gap queue + edge-curation queue + directive-candidate list);
  BioASQ retrieval gate; graph harvester on eval answers (shadow).
- **P2:** weekly cadence + regression gates on frozen slices + public scorecard page.

## Open questions for the panel (v1 — all answered below)

1. Dataset priority + gaps? 2. Slice sizes? 3. Judge validity? 4. Contamination?
5. Graph-growout risk? 6. Highest-leverage cut?

---

# Panel Amendments (v2) — these override the v1 body above

Three-member panel per Rule 17 (Codex, Gemini 3.1 Pro, code-grounded subagent; all returned).

## B1 — The condition filter as written is broken — replace it (subagent, load-bearing)

"Structural containment against the registry" fails twice: real questions don't name conditions
textbook-style (a vignette says "crushing substernal chest pain", a patient says "sugar"), so
recall is terrible AND the surviving slice is biased toward the easiest register — poisoning
every downstream number. It is also exactly the Rule 18 keyword-heuristic-for-semantics ban.
**Fix:** dataset-native topic metadata (MedMCQA `subject`, HealthBench theme tags) as a
structural pre-cut, then ONE cached cheap-LLM classification call per candidate question
(immutable input → cache forever). Read `COVERED_CONDITIONS` from the file at run time (the
count drifts — it is not "106").

## B2 — Cost model corrected: the ANSWER side dominates (subagent)

v1 priced only grading. Every answered question costs the full ReAct loop — roughly 10–20+ LLM
calls (planner per step ×8–16, compose, grounding-fix, claims-extraction batches — some not even
charged to BudgetState per the known governor undercount). The v1 baseline campaign ≈ 350
answer runs ≈ **4–7k LLM calls before any grading** — an order of magnitude above "modest".
**Fix:** restate budgets answer-side-inclusive; explicit sign-off on real spend before P0;
BioASQ runs the retrieval-only `/search` path (genuinely cheap) and says so.

## B3 — MCQ sets demoted to directional probes; kill the closed-book delta claim (unanimous)

MedQA/MedMCQA/PubMedQA are in every frontier model's pretraining; the closed-book-vs-grounded
delta measures memorization margins, not corpus value (and can go negative when retrieval
distracts from a memorized answer). Gemini's cut: drop them from P0 entirely and put the budget
into larger long-form slices. **Retrieval value is instead proven by**: temporal splits
(post-cutoff questions — newest BioASQ cycle, fresh guideline content e.g. KDIGO 2026),
paraphrase/entity-swap probes (brand↔generic), and BioASQ gold-snippet recall.

## B4 — Dataset corrections (Codex)

HealthBench-**hard** is a frontier stress set, not a distribution baseline — sample stratified
full HealthBench (or Consensus) beside it, or we optimize for pathological difficulty. Add
**HealthSearchQA** (3.2k real consumer search questions) for the patient distribution. K-QA is
kept but noted US-consumer-skewed. **BioASQ license is non-commercial/registration-gated —
legal check before any use** (Gemini flags it a trap). LiveQA-Med (2017) is stale — deprioritize.
**India gap is real and unserved by all of these**: adapt NEET-PG-style vignettes (stripped of
MCQ form) / build an internal India slice against the India-programme conditions and guidelines
— the corpus investment `coverage.py` already made deserves an eval slice.

## B5 — Judge calibration is a gate, not a nicety (unanimous)

Before ANY delta is trusted or published: pin judge model+version+prompt (Rule 11 provenance);
double-grade 20–50 answers with a second independent judge; human spot-check discordant items
(measure the judge's entailment-hallucination rate); grade HealthBench **per criterion**
(batching all criteria into one call breaks comparability with published baselines — pay
per-criterion or drop the "place ourselves vs frontier" claim); control verbosity bias
(rubric judges reward length); K-QA must-have and contradiction calibrated separately. Note:
the repo has ZERO LLM-judge infra today (`eval_clinical_gold.py` is deterministic smoke-grade)
— T2 is net-new machinery. A HealthBench score can rise while evidence-warrant quality falls —
keep our own span/warrant audit beside external rubrics.

## B6 — Failure routing needs named machinery + counterfactual probes (Gemini + Codex)

v1 never said WHO classifies failures. **Fix:** a trace-aware LLM classifier that sees the full
diagnostics (searched queries, graph_legs, candidate pools, verified/rejected claims) — final
text alone cannot distinguish a ranking miss from a span-gate drop; plus a human misroute audit
on a sample. Before a failure becomes corpus/graph/directive work, run the cheap counterfactual
probe that isolates the stage: oracle-evidence rerun (compose-only), expanded top-k rerun,
graph-shadow comparison. Route only what survives.

## B7 — Runner path + side-effect policy (subagent)

Default runner is **kernel-direct `svc.ask`** (the `record_medical_baseline.py` pattern): no
session rows, no gap side effects, no HTTP. Prod-`/research` runs are a deliberate second mode
behind a dedicated eval tenant (or a new no-persist flag on `ResearchIn`). Eval→gap-queue
enqueues are REVIEWED (not auto) and land only at run boundaries — mid-campaign corpus
mutation destroys frozen-slice reproducibility. The gap queue API exists (`gap_queue.enqueue`)
but is flag-gated (`NOESIS_GAP_HEALING`) — the plan must state that dependency.

## B8 — Graph growout demoted to P2, conditional (unanimous — v1's biggest false premise)

The chain harvester does NOT exist yet (only the schema's provenance/shadow support does); it
additionally needs the `engine` column on sessions, reasoned-engine answers (chains are that
engine's artifact), and session rows the kernel-direct runner never creates. And Gemini's
distribution warning stands: exam-style questions harvest zebra-trivia edges misaligned with
the high-prevalence registry. **Fix:** growout is P2, conditional on KG-P1 landing; harvest
only from realistic long-form slices (K-QA/HealthBench, never MCQ); edges born shadow with
dataset-provenance recorded; activation only through the A4 entailment gate + curation.

## B9 — Repo corrections (subagent)

`evals/` is EMPTY — real gates live in `scripts/eval_*.py` + `packages/*/eval_*` +
`noesis_kernel/eval/runner.py`. Build `evals/realworld/` but REUSE `run_qa_eval`'s scoring
conventions and result schema rather than inventing a parallel one.

## Revised phasing (supersedes v1)

- **P0:** harness (kernel-direct runner, frozen slices, Rule-11 provenance) + license-verified
  fetch of HealthBench (stratified + hard) and K-QA + LLM condition-classifier (cached) +
  judge-calibration protocol (B5) + T0 structural scorecard + first T2 baseline at 50+50
  (directional), with the REAL answer-side budget signed off first.
- **P1:** failure classifier + counterfactual probes + reviewed routing (gap queue / edge
  candidates / directive list); HealthSearchQA consumer slice; India internal slice; temporal/
  paraphrase retrieval-value probes; scale key long-form slices toward ≥200.
- **P2:** graph growout (conditional on KG-P1; long-form slices only, shadow + curation);
  weekly cadence + regression gates; public scorecard only after judge calibration passes.
