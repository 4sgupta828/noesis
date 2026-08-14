# Answer Quality Overhaul — the Evidence Contract (2026-08-13/14)

The complete record of one comprehensive change: a prod quality failure, its root-cause
investigation, a panel-reviewed redesign, staged delivery with held-out gates, and the
A/B evidence that shipped each piece. Companion docs: `learnings/evidencecontract.md`
(the design spec + adversarial panel amendments), CLAUDE.md ("Evidence Is Typed, Not
Text" + "Never Normalize a Failing Test" — the standing rules this work earned).

## 1. Problem statement

**A prod answer attributed renal-dosing quotes from sitagliptin, gabapentin,
levetiracetam, montelukast, and rivaroxaban labels to "antibiotic labels"** — in an
answer about antibiotic safety for a kidney-transplant patient (session c4afba43,
externally reviewed at 5/10 vs ChatGPT's 8.4/10). Five distinct failures in one answer:

1. **Off-subject retrieval** — generic "dose adjustment in renal impairment" boilerplate
   matched from ANY drug's label; the right labels (cefepime, ceftriaxone, TMP-SMX) sat
   unqueried in our own corpus.
2. **Misattribution passing every check** — the claim said "antibiotic label"; the quote
   was verbatim-real; span-check and entailment both passed, because both verify STRINGS
   and neither could see whose label the quote came from.
3. **Internal contradiction** — "none of these agents is named" alongside a named
   amoxicillin citation.
4. **Intent misalignment with a safety inversion** — a safety/dosing question answered
   with a resistance study, framing aminoglycosides favorably without the nephrotoxicity
   caution.
5. **Self-diagnosed and shipped anyway** — the run's own coverage-gap note said the
   evidence was "generic/unnamed-drug label statements," written at the one point in the
   pipeline where nothing could act on it.

**The design flaw beneath all five: evidence was anonymous text.** Identity (source
document, subject, evidence kind) was stripped at the retrieval boundary and shown to no
model and no judge. The verification stack was maximally rigorous about text and blind
to meaning — and the evals shared the blind spot (they scored answer content, never
"does the cited document concern the claimed subject"), so a low-base-rate structural
failure hid behind good average scores.

## 2. Systematic solution — the Evidence Contract

Method first: **the eval precedes the fix** (the missing held-out case IS the bug), and
**an adversarial panel reviews the design before code** (two external models + a
code-grounded reviewer, each required to produce ≥3 substantive objections — the panel
refuted the spec's central slogan and cut its most dangerous component before a line
shipped). Every stage: flag-gated dark, byte-identical OFF path, subagent-implemented,
adversarially reviewed, measured before flipping.

**Stage 1 — identity on every surface** (`NOESIS_EVIDENCE_IDENTITY`). Every atom renders
`⟨document title — source⟩` on all six LLM-visible surfaces (planner, extractor,
entailment, compose, panel synthesis, fallback grounder) + one instruction: attribute
claims to the source's actual subject. Zero added calls. Kills misattribution and the
"contradiction" (which was two different drugs' facts misread as one subject).

**Stage 2 — the binding judge** (`NOESIS_CLAIM_CONGRUENCE`). One batched judge over ALL
claim paths (closing the loop-claim and fallback-grounder entailment bypasses):
off-subject → dropped; kind/population mismatch → demoted + annotated; judge failure →
annotate, never drop, never a keyword fallback. Plus BudgetState honesty: previously
uncounted call families charged, ceilings re-planned (40→80) to authorize no new spend.

**Stage 3 — question contracts + entity legs** (`NOESIS_QUESTION_CONTRACT`
shadow|steer). One small call derives the evidence SHAPE the question demands (mode,
candidate entities, required axes — vocabulary from the vertical manifest, mechanics in
the kernel). Enumerative contracts expand to per-entity/axis retrieval legs (axis-only
legs first — relationship evidence lives on the OTHER side's document; late-merged,
never through the fused-pool truncation), slot-aware selection reserves compose seats so
off-topic claims can never evict on-topic ones, and unfilled slots become loop-produced
honest gaps. Fixes: the right labels get queried by name; the tacrolimus axis exists.

**Stage 4 — enumerative answer format** (`NOESIS_ANSWER_MODE_ROUTING`). For questions
that enumerate candidates (decided from BOUND CLAIMS, never the pre-retrieval contract
alone): lead with the per-agent table (Agent | dosing facts | Cautions), safety cautions
in the same row/sentence as any favorable mention, population studies demoted to context.
Additive addendum — the validated base compose directive untouched.

Supporting fixes surfaced by the work: 8 antibiotic labels missing from the corpus
entirely (gentamicin/amikacin/pip-tazo…) ingested; the leg-starvation allocation bug;
a silent derivation-killer (temperature=0 rejected by thinking models inside a bare
except); the eval harness clobbering experiment flags with prod's; and — found during
final prod verification — **POST /research had been hijacked for days** (a helper
inserted between the route decorator and its handler; the two "known pre-existing" test
failures were the live bug).

## 3. The evidence — held-out gates and the A/B

**Held-out ACT slice** (5 cases encoding the failure taxonomy; baseline run FIRST and
failing, as required):
- Baseline: mean must-have recall **0.47**, index transplant case **0.0**.
- Stages 1+2: **0.60** — misattribution gone, but the index case stayed 0.0
  (`missing_evidence`): visibility can't retrieve what was never queried. This
  empirically settled the panel's one split (retrieval decomposition IS needed).
- Stages 1+2+3 (double-graded): **0.70**, index case **0.5**, failure bucket moved from
  `missing_evidence` to `reasoning_or_composition` — evidence in hand, framing wrong,
  which is precisely stage 4's territory.

**K-QA no-harm** (19 paired real consumer questions, ON vs banked baseline): **+4.3
points net** (0.537→0.580), contradiction rate unchanged — the congruence filter did not
tax ordinary questions.

**Stage-4 A/B — 30 real prod questions, stratified low/medium/high, paired arms,
order-flipped double pairwise judging (wins only on order-consistent agreement):**

| Stratum | B/A/tie | Δformat | Δcoverage | Δcoherence | Δhonesty | Routing |
|---|---|---|---|---|---|---|
| Low (8) | 0/1/7 | ≈0 | ≈0 | ≈0 | 0.00 | 0 false fires |
| Medium (10) | 4/0/6 | +0.90 | +0.60 | +0.25 | 0.00 | P/R 1.00 |
| High (12) | 5/1/6 | +0.33 | +0.33 | +0.25 | +0.33 | P/R 1.00 |

**Overall 9–2 (p=0.065)**, wins entirely where the feature targets, honesty
flat-or-better (BETTER on the hardest vignettes), routing surgical across all 30. The
low stratum doubled as an embedded A/A test (non-routed pairs = identical configs),
giving a live read of the judge noise floor. Shipped: prod runs
identity=1, congruence=1, contract=steer, routing=1.

An earlier 5-case absolute-rubric measurement had read stage 4 as 0.58-vs-0.70 — kept
dark on that number. The 30-case pairwise instrument overturned it. Both decisions were
correct AT THE TIME: ship on the number you have; build a better instrument when the
number's resolution is the bottleneck.

## 4. Learnings

**Design:**
- Provenance is never correctness; string-verification stacks are blind to meaning.
  Identity must ride WITH evidence to every model and judge surface.
- A self-congruent off-subject claim defeats subject-matching (the panel's killer
  objection) — congruence filters need slot-aware SELECTION behind them.
- Relationship evidence lives on the other party's document: entity×axis queries alone
  structurally miss it (axis-only legs).
- Checks and evals must not share assumptions — every gate needs a held-out case
  designed to fool it; correlated blind spots are found by outside red-teams, not from
  inside.

**Measurement:**
- LLM-judge noise is real (double-grade agreement 0.75); never chase single-run scores.
  Absolute rubrics on 5 cases cannot resolve ~0.1 deltas — pairwise, order-flipped,
  order-consistent-wins judging on 30 stratified cases can.
- Stratify by complexity AND include cases where the feature must NOT fire — routing
  precision is half the value; a low-stratum tie table is an embedded A/A calibration.
- Observability decided three debugging sessions in one look each (legs `hits: None` →
  env clobber; empty contract diag → the temperature bug; run-artifact contracts →
  derivation variance). Build the trace before you need it.

**Process:**
- Never normalize a failing test — two "known pre-existing failures" were a hijacked
  prod route the whole time.
- Incremental spend discipline (1-2 items → batches, patch-reuse of healthy rows) turned
  three timeout kills and one mid-eval credit exhaustion into ~$0 of lost work.
- Config drift bites experiments: once prod carries the flags, eval arms must explicitly
  win over pulled prod env.
- The adversarial panel earned its cost: it deleted a component that would have poisoned
  recall permanently (doc-level LLM identity cache) and correctly predicted both the
  off-subject-binding loophole and which stage the first eval round would prove
  insufficient.
