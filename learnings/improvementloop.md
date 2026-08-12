# The Improvement Loop — how Noesis gets measurably better from real-world Q&A

**Status:** OPERATING STRATEGY (v1, 2026-08-12) — the loop is BUILT and has completed its
first full turn with a measured win. · **Companions:** `learnings/realworldqa.md` (the
panel-reviewed plan this executes), `learnings/knowledgegraph.md` (the graph it feeds),
CLAUDE.md standing directives (credit discipline · kernel/vertical split).

## The strategy in one paragraph

Take high-quality public Q&A whose answers were written by domain experts (real patient
questions with clinician-written must-have facts), run them through Noesis against FROZEN
question sets, grade every answer fact-by-fact, let a trace-aware classifier name each
failure's dominant cause from the engine's own internals, route each cause to the subsystem
that owns it (corpus / retrieval+graph / compose directive), apply the fix, and re-run the
IDENTICAL questions to prove the delta. Never guess what to fix; never fix without
re-measuring; never let the eval questions leak into any prompt. Each turn of the loop
improves three assets at once: the corpus (gap fills), the graph (harvested edges), and the
quality scorecard itself.

## The loop (one turn, end to end)

```
 ①  MEASURE          frozen slice (e.g. 25 K-QA questions) → kernel-direct runner
                     → answers + full trace (searches, evidence, graph legs) banked to disk
 ②  GRADE (T2)       LLM judge, per gold must-have fact: covered | missing | contradicted
                     → must-have RECALL per answer; judge double-graded vs an independent
                       model family (calibration reported, never assumed)
 ③  DIAGNOSE         for every under-covered answer, a TRACE-AWARE classifier picks the
                     dominant failure mode (it sees what was searched and retrieved, not
                     just the final text)
 ④  ROUTE            each bucket has an OWNER (table below); fixes are reviewed, tagged
                     with the eval finding that demanded them, and land between runs
 ⑤  RE-MEASURE       identical frozen slice, same judge, same prompt hash, git SHA recorded
                     → paired per-question deltas (the honest lens), not just the mean
```

## Failure buckets → owners (step ④'s routing table)

| Bucket | Owner / action |
|---|---|
| `missing_evidence` | Corpus: targeted connector ingests (tagged, e.g. `kqa-gap`), reviewed before enqueue |
| `wrong_evidence_selected` | Retrieval: ranking/rerank cases; candidate graph edges when the miss is a topic hop |
| `ranking_failure` | Retrieval: ranking work items |
| `reasoning_or_composition` | Compose: DIRECTIVE-REVIEW list only — the validated directive changes solely via held-out A/B (092dd35 discipline), never per-case patches |
| `abstained_despite_evidence` | Engine: abstention-guard cases |
| `question_misunderstood` | Engine: question-resolution cases |

## Proof it works — turn #1 (2026-08-12, frozen K-QA dev-25)

- Baseline: **55.1%** must-have recall; taxonomy said 12/19 failures = `missing_evidence`,
  clustered on CONSUMER-PRACTICAL medicine (OTC combos, drug timing, breastfeeding safety)
  — a corpus class gap, not a reasoning gap (0 wrong-evidence, 0 ranking failures).
- Fix: 13 reviewed ingests (8 DailyMed labels + 5 targeted literature pulls), tagged `kqa-gap`.
- Re-measure (identical questions): **59.3%** (+4.2pt); on the 12 TARGETED questions the
  paired sign is **6 improved vs 1 regressed** — the mechanism's clean signal. Honest noise
  note: two untargeted questions flipped 1.0→0.0 on answer nondeterminism; at n=25 the
  aggregate is suggestive, the targeted sign test is the evidence. Larger slices fix this.
- Instructive miss: "which doctor for vertigo" needs consumer care-navigation content — a
  content CLASS (consumer-health pages) for a future tranche, discovered by the loop.

## Standing disciplines (non-negotiable, from CLAUDE.md + plan amendments)

1. **Frozen, held-out slices** — dev/test split by deterministic hash; eval questions never
   appear in any prompt, fixture, or edge annotation (Rule 5). Slices are versioned files;
   re-runs are byte-comparable.
2. **Provenance per answer and per judgment** (Rule 11): git SHA, flags, model, judge prompt
   hash — every number is re-runnable.
3. **Credit discipline**: every spending script projects its budget and requires
   `--confirm-spend`; answers are BANKED and reused (`--patch` salvages brownout tails,
   `--off-from` reuses eval arms); pipelines validate on 1–2 items before batches; evals
   and prod share one API account, so an exhausted balance degrades prod (twice observed —
   consider a separate eval key / larger standing balance before scaling).
4. **Kernel/vertical split**: judge and classifier prompts are domain-neutral mechanics;
   medical flavor enters only as vertical-supplied directives; datasets are adapters. A
   legal/regulatory vertical reuses the whole loop by supplying its manifest.
5. **Judge before trust** (plan B5): deltas are reported WITH the double-grade agreement;
   public/comparable scores wait for per-criterion grading + human spot-check calibration.

## The compounding effects (why this loop > ad-hoc QA)

- Every eval answer can feed the graph harvester (shadow edges, entailment-gated) — eval
  traffic bootstraps graph density before user traffic scales.
- Every `missing_evidence` finding deepens the corpus with provenance ("which eval question
  demanded this document").
- Every turn re-validates the whole serving path (grounding rate, abstentions, latency)
  as a side effect — a standing regression net.

## Roadmap

- **Now proven:** K-QA dev-25, one full turn, +4.2pt / 6-vs-1 targeted sign.
- **Next:** 50-question K-QA + HealthBench-hard slices (noise ↓); consumer-health content
  class; directive-review A/B for the 5 reasoning failures; scoring refinement (count only
  CITED evidence, not answer prose); de-hint saturated masquerade cases.
- **Then:** weekly cadence on frozen slices as a regression gate; an admin EVAL CONSOLE in
  the UI (graph-console pattern) making each question → verdicts → routing → delta visible;
  public scorecard only after judge calibration passes (B5).

## Where everything lives

- Plan + panel review: `learnings/realworldqa.md` (amendments B1–B9 govern).
- Harness: `evals/realworld/` — `fetch.py` (license-verified) · `slices.py` (frozen,
  stratified) · `run.py` (kernel-direct, spend-gated, `--patch`) · `judge.py` (T2 +
  taxonomy + calibration) · `score.py` (T0 structural).
- Artifacts: `evals/realworld/slices/*.jsonl` (questions) · `runs/run-*.jsonl` (answers +
  traces) · `runs/judged-*.json` (verdicts, buckets, agreement).
- Graph hard-case eval: `evals/graph/` (masquerade set + campaign decision logs).
