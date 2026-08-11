# Real-World Q&A Harness (plan: `learnings/realworldqa.md` v2, amendments B1–B9)

Measure Noesis against real-world medical Q&A, route classified failures to the right
subsystem, and (later, P2, conditional on KG-P1) grow the graph from our own grounded answers.

## Layout

- `fetch.py` — license-verified downloads (HealthBench main/hard/consensus, K-QA) into
  `data/` (git-ignored) + `data/manifest.json` recording URL, sha256, license, fetch date.
- `slices.py` — build FROZEN, versioned slices (`slices/slice-<set>-<n>-<date>.jsonl`).
  Stratified by the dataset's own metadata (HealthBench theme/axis tags, K-QA has none) —
  per amendment B1, NO keyword condition-matching; the cached LLM condition classifier is a
  separate explicit step (`classify.py`, costs 1 small call per NEW question, cached forever
  in `data/topic_cache.json`).
- `run.py` — kernel-direct runner (`build_default_service().ask`, the
  `record_medical_baseline.py` pattern — NO session rows, NO gap side-effects). Prod-parity
  env pulled from Railway at run time (secrets never written to disk). Records Rule-11
  provenance per answer: git SHA, model, flags, corpus DSN host, timestamps.
- `score.py` — T0 STRUCTURAL scorecard (free): grounded rate, claims/answer, atoms,
  abstention, stopped_reason mix, graph-leg fire/merge rates, evidence-tier mix.
  T2 (LLM rubric judging) is deliberately NOT here yet — per amendment B5 it requires the
  judge-calibration protocol and a signed-off budget first.

## Split discipline (Rule 5 / amendment B1)

Each fetched set is split once: `dev` (iterate freely) / `test` (frozen, run sparingly,
never inspected per-question). Slices record which split they draw from. No eval question
ever appears in any prompt, few-shot, or fixture visible at inference time.

## Cost honesty (amendment B2)

Answering dominates: ~10–20 LLM calls per question (ReAct steps + compose + extraction).
A 50-question slice ≈ 500–1000 calls PER ARM before any grading. Every `run.py` invocation
prints its projected call budget and requires `--confirm-spend` to proceed.

## Licenses (verified at fetch, echoed into manifest)

HealthBench: MIT (openai/simple-evals). K-QA: MIT (Itaymanes/K-QA). BioASQ: registration +
non-commercial — NOT fetched here (legal check pending, amendment B4).
