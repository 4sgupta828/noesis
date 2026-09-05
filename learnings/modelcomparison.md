# Model Comparison — answer quality by LLM (decision record + method)

The running record of head-to-head model comparisons on the SAME pipeline, SAME corpus, SAME
questions. Every entry is reproducible from the named run files under `evals/realworld/runs/`
(Rule 11 provenance: model, judge, git SHA, timestamp are inside each file). Keep adding entries;
never overwrite one — a superseded conclusion stays visible with its date.

Related: `learnings/realworldqa.md` (harness + judge calibration rules), `learnings/evidencecontract.md`
and `learnings/fixanswerrefusal.md` (the earlier COMPOSE-model A/B, evidence held constant).

---

## 2026-09-04 — Claude Opus 5 vs DeepSeek chat (full pipeline, 5 K-QA questions)

**Why:** prod had run on DeepSeek for ~a week (`NOESIS_LLM_PROVIDER=deepseek`) and was switched
back to Claude (Sonnet 5) the same day; the question was whether Opus or DeepSeek is the better
answer model, or whether they are equivalent. Budget cap: $4.

**Method.** `evals/realworld/run.py` per arm with prod-parity env (Railway values + the arm's
`NOESIS_LLM_*` overrides), prod corpus, `--limit 5 --concurrency 2`, standard engine (`svc.ask`).
Judge: `evals/realworld/judge.py`, ONE Sonnet judge (`claude-sonnet-5`, the service default) grading
each answer against expert-written must-have facts (covered / missing / contradicted) + a failure
bucket. Same judge for both arms, so judge-family bias is constant across the comparison (not
absent — see caveats). Retrieval was identical across arms (the DF-driven lexical planner shipped
earlier that day), so the delta is planning + extraction + composition.

Run files:
- DeepSeek: `run-slice-kqa-dev-50-2026-08-11-env-20260905T032102Z.jsonl` → `judged-…032102Z-20260905T032129Z.json`
- Opus:     `run-slice-kqa-dev-50-2026-08-11-env-20260905T032447Z.jsonl` → `judged-…032447Z-20260905T032509Z.json`

**Result.**

| | Claude Opus 5 | DeepSeek chat |
|---|---|---|
| Must-have recall, mean | **0.52** | 0.35 |
| Answers with a contradiction | **0** | 1 |
| Verified (span-checked) claims per answer | 8–22 | 4–11 |
| Answer length | 2.9–5.5k chars | 1.5–3.2k chars |
| Wall-clock per answer | 56–86 s | 20–37 s |
| Cost per answer (approx.) | ~$0.60 | ~$0.03 |
| Failure buckets (judge) | missing_evidence 3, not_a_failure 1 | missing_evidence 2, wrong_evidence_selected 2 |

Per question (must-have recall, Opus / DeepSeek):

| id | question | Opus | DeepSeek | note |
|---|---|---|---|---|
| kqa-141 | Could Bactrim cause a yeast infection? | 1.00 | 0.00 | DeepSeek **contradicted** the gold — the safety-relevant miss |
| kqa-99 | Is it common to have an abscess with no pain? | 0.75 | 0.50 | |
| kqa-23 | Can I take NyQuil and Benadryl together? | 0.50 | 0.25 | |
| kqa-45 | Does bronchitis turn into pneumonia? | 0.33 | 0.00 | |
| kqa-147 | Is prednisone a cortisone-type medication? | 0.00 | 1.00 | one-fact gold ("derives from cortisone"); Opus wrote "synthetic glucocorticoid, cortisone-like" — judge strictness, both answers clinically correct |

**Read (decision of record).** Opus is the better answer model on this sample: it binds roughly twice
the verified evidence per answer, covers more gold facts on 4/5 questions, and produced no
contradiction. DeepSeek is ~3× faster and ~20× cheaper; its failures were evidence selection
(missing / wrong evidence), not writing. The single Opus miss is a judge-strictness artifact on a
one-fact gold, which is also why n=5 is suggestive, not conclusive (one flipped question moves the
mean by 0.2). Prod stays on **Sonnet 5** (untested here) unless/until a larger run justifies Opus's
cost; switching is `NOESIS_LLM_MODEL=claude-opus-5` + redeploy.

**Caveats — read before quoting these numbers.**
- n=5, consumer-style K-QA questions, standard engine — this measures grounding breadth and gold
  coverage, NOT the clinical-decision (reasoned) format or the differential engine.
- One judge family (Anthropic) graded an Anthropic arm; `--double-grade 2` was requested but
  `judge_agreement_double_grade` came back null (OpenAI fallback judge not configured in this env), so
  judge calibration (realworldqa.md B5) is NOT satisfied for this entry.
- Cost figures are projections from the per-answer token profile (Sonnet run: ~29k in / 8k out over
  the 5 logged calls of ~14), not billed amounts. Total spend for the entry ≈ $3.3.

**Next step that would settle it (~$12):** 20 questions mixing K-QA gold with the ddx-clinical slice,
reasoned engine on (`NOESIS_EVAL_REASONED=1`), both judge families, Sonnet 5 as a third arm (the
model actually in prod).

**Reproduce**
```bash
NOESIS_LLM_PROVIDER=deepseek NOESIS_LLM_MODEL=deepseek-chat \
  .venv/bin/python evals/realworld/run.py --slice slices/slice-kqa-dev-50-2026-08-11.jsonl --limit 5 --concurrency 2 --confirm-spend
NOESIS_LLM_MODEL=claude-opus-5 \
  .venv/bin/python evals/realworld/run.py --slice slices/slice-kqa-dev-50-2026-08-11.jsonl --limit 5 --concurrency 2 --confirm-spend
cd evals/realworld && ../../.venv/bin/python judge.py runs/<run>.jsonl --double-grade 2 --confirm-spend
```
Note: `--slice` is resolved relative to `evals/realworld/`, not the repo root.
