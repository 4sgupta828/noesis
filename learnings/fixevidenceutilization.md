# Fix: low evidence utilization (agent grounds only a tiny subset of retrieved evidence)

**Date:** 2026-08-02 · **Area:** research loop (`packages/kernel/noesis_kernel/research/`) ·
**Flag:** `NOESIS_CLAIMS_FIRST` (default off; enabled in prod for A/B)

Companion to [[fixanswerrefusal.md]] — that fixed the *abstention* tail (0 claims); this fixes the
opposite tail: the agent answers but grounds only 2 claims from 18 good passages.

## Symptom
"What treatments exist for obesity in adults?" retrieved **18** atoms (web 8, europepmc 6,
clinicaltrials 4) but CITED only **2** (web **0/8**), rejected 2. Utilization ~11%. The answer was
thin. Same pattern on any broad/survey question.

## Root cause (panel: Codex + Gemini + code-grounded subagent, all agreeing)
1. **Extraction is under-enforced.** The SAME ReAct model both plans searches AND emits the final
   `claims` list in ONE `AgentStep`; `_apply_answer` verifies only what it emitted. "Report EVERY
   fact" is a soft prompt string, not a mechanism → the model synthesizes 2–4 claims regardless of
   how many atoms exist. Nothing systematically atomizes all evidence.
2. **The abstention fallback doesn't help thin answers.** `fallback_grounder` fires ONLY on TOTAL
   abstention (`0 verified AND 0 rejected`). A 2-verified/2-rejected answer bypasses it — so the
   low-utilization tail got no help.
3. **Web is effectively unquotable.** Each web result was ONE ~4000-char block (Exa `maxCharacters`),
   never chunked like corpus paragraphs (`corpus/splitter.py`). Finding a *verbatim* span in a 4000-
   char blob is far harder than in a clean trial paragraph → web ~0/8.
4. Compose is only as rich as the verified claims → thin extraction = thin prose.
5. The verbatim span gate (`provenance.py`) is a **fabrication guard, not a relevance check** — its
   own docstring says so. So more aggressive extraction risks a false-pass (a real-but-irrelevant
   quote stapled to a synthesis sentence).

## The fix — claims-first pipeline (NOT patchwork triggers)
The user's framing: don't add utilization thresholds/top-up hacks; separate the jobs that were mashed
into one terse step. GATHER → EXTRACT → VERIFY(+entail) → MERGE → COMPOSE (`research/claims_first.py`,
wired in `react.py` after the loop, before compose):

1. **EXTRACT — comprehensive, MULTI-LENS, batched.** After GATHER, mine ALL atoms with a cheap model,
   10 atoms/call, lenses passed as a **CHECKLIST inside ONE prompt** (NOT fanned out per lens — that's
   5–90× the calls for duplicates). Lenses are **vertical-supplied** (`manifest.extraction_lenses`;
   medical = interventions/outcomes/comparisons/population/safety/mechanism) — kernel stays domain-free.
2. **Chunk web bodies** into ~900-char length-bounded blocks (`web.py::_chunk_text`, interleaved
   breadth-first so every result stays quotable). The paragraph splitter won't cut break-less HTML.
3. **VERIFY — two gates.** The UNCHANGED verbatim span gate, PLUS an independent **ENTAILMENT gate**
   (the quote must SUPPORT the claim, not just contain the words). The entailment gate is the
   correctness safeguard and is **load-bearing**, not optional — without it, extraction/rescue become
   laundering vectors against the fabrication-only span gate.
4. **MERGE** — dedup vs the loop's already-verified claims (by `(atom_id, normalized quote)`); cap 30.

Deferred (documented, not built): rescue/downgrade-before-reject (re-locate a span or downgrade to an
attributed weaker claim) — safe only if bolted to entailment; deferred for cost/complexity.

## Model tiering (cost-optimized — user priority)
- **Extraction:** `gpt-4o-mini` (bulk, constrained, and span-gate-protected — a bad quote is rejected,
  so cheap is safe). Env: `NOESIS_EXTRACT_MODEL`.
- **Entailment judge:** **`gpt-4o`** (the safety gate deserves the stronger model; one batched call →
  small cost bump). Ideally a DIFFERENT model family than the extractor to decorrelate errors. Env:
  `NOESIS_ENTAIL_MODEL`.
- **Compose:** unchanged (Anthropic).
- Key insight: this moves heavy extraction OFF the expensive Anthropic loop onto cheap OpenAI —
  so thorough grounding can actually LOWER Anthropic (the constrained resource) spend.

## The invariant (unchanged)
Provenance is not weakened. A claim ships only if its quote **verbatim-verifies** AND an independent
judge says the quote **supports** it. Coverage is earned by real, supported spans — never by relaxing
the gate. Verified in isolation: extractor 4/4 verbatim; entailment REJECTED a real-quote-but-false
stapled claim.

## Validation (1 live query, credit-conscious)
Obesity question, claims-first ON:

| | before | after |
|---|---|---|
| grounded claims | 2 | **11** |
| utilization (cited/retrieved) | 11% | **55%** (11/20) |
| web cited | 0/8 | **4/10** |
| rejected | 2 | 0 |

Trace: agent abstained → fallback grounded 5 → extraction added +6 (14 candidates → 6 after dedup +
entailment) → 11. Latency ~135s on this run (it hit all three layers); typical case adds only the
extraction pass (~10–20s). Held-out gate: `scripts/eval_utilization.py` (cited/retrieved ≥ threshold
+ web floor, provenance active — score can't be gamed by unverified claims).

## Key lessons
- Don't let the *reasoning* model also be the *exhaustive extractor* — it will emit a terse few.
  Run a dedicated, comprehensive, multi-lens extraction over all evidence.
- The verbatim span gate is provenance, NOT relevance. Comprehensive extraction MUST be paired with an
  independent entailment gate, or you buy utilization with laundered paraphrases.
- Tier models: cheap for span-gate-protected extraction, strong for the entailment safety gate.
- Chunk web/large sources; a wall-of-text block is unquotable.
- Prefer architecture (always-comprehensive extraction) over patchwork (utilization thresholds/top-up).

## Files
- `packages/kernel/noesis_kernel/research/claims_first.py` — extract + entailment pipeline (new)
- `packages/kernel/noesis_kernel/research/react.py` — wired after the loop (flag-gated)
- `packages/kernel/noesis_kernel/retrieval/web.py` — `_chunk_text` + chunked web blocks
- `packages/kernel/noesis_kernel/contract/manifest.py` + medical manifest — `extraction_lenses` slot
- `packages/kernel/noesis_kernel/runtime/research.py`, `apps/api/app.py` — flag/lens threading
- `scripts/eval_utilization.py` — held-out utilization gate (new)
- `packages/kernel/noesis_kernel/providers/openai_llm.py` — async OpenAI JSON client (shared w/ [[fixanswerrefusal]])
- Reference (factra, same repo): `app/research_system/services/agents/research_orchestrator/claims_first/`
