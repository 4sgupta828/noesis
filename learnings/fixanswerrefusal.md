# Fix: answer refusal / abstention (agent returns 0 claims despite good evidence)

**Date:** 2026-08-02 · **Area:** research loop (`packages/kernel/noesis_kernel/research/`)

## Symptom
Run-to-run, the research agent would return **`grounded=False`, 0 claims** on questions the corpus
clearly covers — then answer the *same* question fine on the next run. It was worst on
judgment/survey questions (e.g. *"Which criteria should our HPB team adopt … for biliary drain
removal timing after subtotal cholecystectomy?"* retrieved 18 relevant passages and grounded 0).

The tell: `rejected == 0`. The span-verifier wasn't rejecting bad claims — **the model emitted an
empty `claims` list on purpose** (pure abstention), so there was nothing to verify.

## Root cause (confirmed by judge panel + code-grounded subagent + factra's orchestrator)
Pure **model over-abstention**, not a retrieval or provenance bug:
- The atom↔verifier **data contract is sound** — the text the model sees (`atom.text = BlockHit.text`)
  is byte-identical to what the span gate checks against (`PostgresRetrievalSource` caches the same
  `r["text"]` for both search and the loader). So quotes copied from what it saw *do* verify.
- The agent's instructions **permitted** bailing: *"return an empty claims list ONLY if NONE of the
  evidence is relevant."* On hard questions the model rationalised "no single passage *states* the
  answer" and took that exit instead of reporting the partial facts it had evidence for.
- The one safety net (`_finalize_answer` extract-recovery) was **one-shot and reused the same
  permissive prompt** — so it re-made the same call and gave up. If the retry also came back empty
  (or chose to search again, which was silently dropped), the loop broke with 0 claims.
- Contributing: the ClinicalTrials corpus is registration-metadata-only (no results/efficacy prose),
  which tempts abstention on efficacy-shaped questions.

## The fix — 3 escalating layers so it stops giving up (all in `research/react.py`)
1. **Close the loophole.** A dedicated, forceful `mode="extract"` prompt that does NOT append the
   permissive discipline: *"relevant evidence exists → an empty answer is INVALID; extract ≥1
   supported fact per relevant atom; partial is expected; quotes VERBATIM,"* plus a generic
   (non-domain) JSON format example.
2. **Bounded retry loop, not one-shot.** `_finalize_answer` now retries the forceful extraction up
   to **3×** while `0 verified AND 0 rejected AND atoms exist AND budget remains`, and re-asks if the
   model tries to `action="search"` instead of answering.
3. **Second-model fallback grounder** (`research/fallback_grounder.py` + `providers/openai_llm.py`).
   If the Anthropic model *still* abstains, hand the gathered atoms to a **different model
   (OpenAI gpt-4o)** whose only job is to atomize them into claims — each citing an atom + a
   **verbatim quote**. This is factra's proven escalation (`app/research_system/.../fallback_grounder.py`):
   re-asking the *same* model is unreliable (their bake-off: Sonnet 0/8), a second model succeeds
   (gpt-5.5 8/8). Fires only in the already-abstaining path; fail-safe (no key / API error / nothing
   parseable → 0 claims and the original abstention stands).

## The invariant that stays intact (why this is safe)
**Provenance is unchanged.** Every claim — including anything the fallback model produces — is still
run through the exact same `BlockSpanVerifier`: the quote must appear (whitespace/case-normalized)
in a real cited atom, or the claim is **rejected**. So all we ever do is get the agent to *notice
facts it already had evidence for* — we never invent, loosen the gate, or accept a non-verbatim quote.
(This is provenance, not correctness — Rule 6. A future add: an entailment gate like factra's, to
also check the cited atom *supports* the claim, not just contains the quote.)

## Key lesson
When a model **refuses to extract** despite good evidence, don't just re-ask the same model harder —
**a second, different model does the extraction reliably**, and you can still enforce the same
verbatim provenance gate on its output. Learned the same way factra did.

## Validation
- Held-out gate: `scripts/eval_abstention.py` (LIVE — cassettes can't measure sampling variance).
  Runs corpus-provable survey questions + the HPB criteria anchor N times; asserts `grounded=True`,
  `rejected==0`, abstention rate `0/N`.
- Single-call check (credit-conscious): the HPB anchor that returned 0 claims now grounds
  (verified 9, rejected 0, `retried_empty=True`).
- **Cost/latency tradeoff:** the recovery + fallback add model calls and latency (~+30–60s) — but
  ONLY on the hard questions that would otherwise have refused.

## Files
- `packages/kernel/noesis_kernel/research/react.py` — forceful extract prompt + bounded retry loop + fallback wiring
- `packages/kernel/noesis_kernel/research/fallback_grounder.py` — second-model atomizer (new)
- `packages/kernel/noesis_kernel/providers/openai_llm.py` — async OpenAI JSON client (new)
- `scripts/eval_abstention.py` — held-out abstention-rate gate (new)
- Reference (factra, this same repo): `app/research_system/services/agents/research_orchestrator/fallback_grounder.py`
