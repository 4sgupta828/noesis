# Real-World Q&A Learning Strategy — measure, learn, and grow the graph from real questions

**Status:** PLAN v1 (panel review pending) · **Companions:** `learnings/knowledgegraph.md`
(the graph this feeds), `learnings/evidencepulse.md` (currency), `evals/` (existing internal gates)

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

## Open questions for the panel

1. Dataset priority + anything better we're missing (esp. non-US/consumer distributions)?
2. Split sizes: is 50/run T2 enough signal to rank failure modes, or do we need 100+?
3. LLM-judge validity: HealthBench rubrics were built for a specific judge setup — do we need
   judge-calibration (e.g. double-grade 20 answers, human spot-check) before trusting deltas?
4. Contamination: MedQA/MedMCQA are in every frontier model's pretraining — does the
   closed-book-vs-grounded delta still measure what we want, or do we need decontamination?
5. Graph growout: is harvesting from eval answers (vs real user traffic) a distribution risk —
   edges biased toward exam-style relations?
6. What's the single highest-leverage P0 cut if we had to halve the scope?
