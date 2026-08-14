# The Coverage Diagnostic — a route-the-next-dollar instrument (v1, 2026-08-14)

A cheap, repeatable method for answering "should we build X to improve answers?" with
buckets instead of opinions. First applied to the exploratory-coverage question
(harness: `evals/realworld/diag_axes.py`; slice: `slices/slice-explore-diag-8-*.jsonl`);
result: 57%→77% axis coverage for ~$4 of diagnosis + correctly split the fix between
ingestion and machinery. This doc is the method itself, kept evolving — add a dated
section per revision.

## The method

1. **Pick 8–12 REAL questions** of the kind under investigation (session store, not
   invented — distribution truth). Hold them out of all prompts.
2. **Write gold MUST-COVER AXES per question** (3–5 each): the dimensions a domain
   expert would demand any complete answer address. Axes are the unit of measurement —
   finer than "answer good/bad", coarser than sentences.
3. **Run the CURRENT system once** on the questions (prod-parity flags).
4. **Classify every axis into three buckets**, each demanding a different action:
   - `covered` — the answer addresses it → no build needed.
   - `uncovered_retrievable` — missed, AND a corpus probe finds usable evidence →
     a MACHINERY fix (retrieval/selection/compose) would help.
   - `uncovered_absent` — missed, AND the corpus holds nothing usable → an INGESTION
     fix; no machinery can retrieve what isn't there.
   Coverage is judged by one batched LLM call per question; the corpus probe embeds
   "axis + question", takes top-5 blocks, and an LLM judges usability (Rule 18: the
   model owns both judgments; code only orchestrates and counts).
5. **Route the fix by the dominant bucket.** Ship the cheap bucket first (ingestion is
   usually one admin call; machinery is a build).
6. **Re-run the SAME diagnostic** after each fix; the bucket deltas are the effect.
   Ship/park flags on the covered% delta.

Cost anatomy (the 2026-08-14 run): 8 answers ≈ $2–3, judging + probes ≈ $1,
re-measures ≈ same. The whole loop, both fixes measured: under $15.

## Known pitfalls (hit them all on day one)

- **The probe is weaker than the pipeline.** Pure cosine top-5 is a floor, not the
  system's ceiling (no BM25 fusion, no rerank, no legs). A pessimistic probe inflates
  `uncovered_absent`. Treat probe verdicts as routing signals; the END-TO-END re-run is
  the truth. (Observed: post-ingest probes still said "absent" for axes the full
  pipeline then covered.)
- **The absent bucket has a content-TYPE dimension.** Trials/papers structurally don't
  teach reference-grade content (warning signs, mechanisms-for-laypeople, drug-causes-
  symptom basics). If absent axes cluster there, the fix is a reference connector, not
  more of the same connectors. Read the axes, not just the counts.
- **Attribution blurs when fixes land together.** We shipped ingestion + legs and
  measured the combination (+20pt). Fine for a ship decision when one fix is permanent
  anyway; NOT fine for crediting a flag. If the flag decision is contested, run the
  legs-off/post-ingest arm too (one extra answer run).
- **Judge strictness wobbles at the bucket boundary** (a PRKN case report: usable or
  not?). Don't chase single-axis flips; read the aggregate and the notes.
- **Config drift**: eval arms must explicitly win over prod env (run.py's NOESIS_*
  override rule) — one arm silently measured prod's flags instead of the experiment's.

## Where it connects

- **House eval set (#46)**: gold axes written for diagnostic slices are reusable eval
  gold; promote good diagnostic questions into the frozen house slices.
- **Answer-schema registry (#47)**: per-schema axis lists × this diagnostic = the
  schema-coverage matrix (which question types our corpus serves poorly) — the
  principled ingestion shopping list.
- **Corpus-first**: `uncovered_absent` clusters are corpus-first tranche candidates
  with evidence attached (MedlinePlus-class reference connector: flagged by K-QA
  failure buckets, the ACT slice, AND this diagnostic — three independent signals).

## Evolution backlog (add here; date entries when done)

- **Bucket 4: `covered_but_wrong`** — an axis addressed with incorrect/miscited
  content is worse than uncovered; needs a correctness check on covered axes.
- **Pipeline-grade probe** — probe through the real retrieval stack (fusion + rerank +
  legs) instead of raw cosine; kills the probe-pessimism pitfall.
- **Attribution arms by default** — when two fixes are candidates, the harness should
  run the 2×2 (or at least 3 arms) automatically with patch-file reuse.
- **Axis provenance** — record WHICH retrieval path (planner query, contract leg,
  graph leg, explore leg) produced the evidence for each covered axis; tells us which
  machinery earns its cost.
- **Auto-derived axes** — bootstrap gold axes from the contract deriver + expert
  review, so building a new diagnostic slice costs minutes.
- **Recurring cadence** — re-run the standing diagnostic slices after major corpus or
  retrieval changes (the same way K-QA no-harm gates flag flips).
