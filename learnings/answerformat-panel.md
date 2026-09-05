# Answer-format panel — decision of record (2026-09-04)

Owner's observation: the reasoned "Do now / Do if" format is excellent on case questions but is
applied mindlessly to general ones ("what is a balanced diet"). Three independent lenses reviewed
the live directives (`reasoned.py`, `answer_format.py`, `understanding.py`), the engine routing
(`runtime/research.py`), and a real prod answer: clinician-reader, routing/eval, medical-writing/UX.
All three converged on the same diagnosis and the same shape of fix.

## Diagnosis — why every question became a decision plan

Four separate pulls, each sufficient on its own (file:line as of commit 893ad16):

1. **The UI forced it.** In the default "Clinical Decision" mode the FE sent `engine="reasoned"`
   (`apps/web/index.html` ~5054, comment: "a decision framework even for broad/benefit/overview
   questions"); `app.py` mapped that to `ask_reasoned(route=False)`, which runs the classifier and then
   **discards its verdict** (`research.py:230,234` gate lookup/understanding on `route`). The
   classifier call was paid for and ignored on every default-mode question.
2. **The classifier's default and fallback were both "management".** `kind: Literal[...] =
   "management"` (`research.py:203`); the scaffold `except Exception: pass` then set the reasoned
   format unconditionally (`research.py:269-271`). "Unsure" did not exist.
3. **The compose directive demanded it.** `REASONED_ANSWER_FORMAT`: "Answer as a clinical DECISION,
   not a literature review — even for 'benefits / options / what helps' questions"
   (`reasoned.py:127-128`), and the governing rule overrides the "omit headings that don't fit" clause.
4. **No good landing zone existed for general questions.** The only non-decision, non-mechanism
   format was `MEDICAL_ANSWER_FORMAT`, a trial-synthesis skeleton (Efficacy / Safety / Population /
   Evidence quality) — nearly as forced for "what is a balanced diet" as Do-now.

Secondary finding (reader + UX): even the good case echoes the retrieval coverage brief back as a
"Question coverage" checklist on a single-question ask (`answer2.md`), which the directive forbids;
`explicit_asks` is over-filled by the scaffold.

## Decision

**Route by question shape, with a non-directive default.** The single scaffold call (no new LLM
spend) classifies into six kernel-neutral kinds; the vertical maps kinds to directives; anything
uncertain or failed falls to the adaptive standard synthesis, never to the decision plan.

| kind | example | format |
|---|---|---|
| management (± diagnostic) | metformin dose at eGFR 30–45 · 62M T2DM+HFrEF, add SGLT2i? | REASONED / DIFFERENTIAL (unchanged) |
| understanding | how does metformin work | UNDERSTANDING (unchanged) |
| overview | what is a balanced diet · what is prediabetes | **new OVERVIEW**: In brief · What it is · What the evidence supports · Nuances · Not covered |
| comparison | apixaban vs warfarin in CKD | **new COMPARISON**: Bottom line · Head-to-head table · When each is preferred · Not established |
| update | what's new in HFpEF this year | **new UPDATE**: What changed (dated) · Key new evidence · What hasn't changed · Not covered |
| lookup | what did EMPA-REG show · is sertraline safe in pregnancy | MEDICAL_ANSWER_FORMAT (unchanged) |

Rules:
- `kind` has **no management default**: unparsed → `lookup`. `confidence="low"` → standard adaptive
  synthesis. Scaffold exception → standard (not reasoned) unless the caller forced the arm.
- Management requires a case, a value, or an explicit "should I / which / how much"; a question with
  no subject and no decision is never management (prompt rule + tie-break toward the other kind).
- The UI's "Clinical Decision" mode becomes **auto** (the question picks); only "Research" forces
  standard; `route=False` remains for the A/B duel arm and the explicit hop chips.
- `REASONED_ANSWER_FORMAT` loses "even for benefits / options / what helps" and gains a SCOPE clause:
  no patient and no decision → no Do now / Do if / Watch for.
- `explicit_asks` = only sub-questions present in the user's text; empty is the normal case, so the
  Question-coverage checklist disappears for single asks.
- Kernel/vertical split holds: the kernel owns the kind names and the routing; the vertical supplies
  `answer_formats: {kind: directive}` in its manifest.

## Eval (held-out; designed to expose wrong-format application, not to confirm the router)

| # | question | trap | pass |
|---|---|---|---|
| 1 | What is a balanced diet? | owner's case | no Do now/Do if/Watch for |
| 2 | What should a balanced diet include? | "should" reads as action | same as 1 |
| 3 | My patient asked what a balanced diet is — what do I tell them? | mentions a patient, still a primer | overview, not decision |
| 4 | Metformin dose at eGFR 30–45? | no patient → over-correction bait | decision; numbered Do now with the mg/day figure; no Question coverage |
| 5 | How does metformin lower glucose? | "lower" reads as action | understanding; no Do now |
| 6 | Compare apixaban vs warfarin in CKD 4 | real decision inside a comparison | table with both sides cited; no "Do now: start apixaban" |
| 7 | What's new in HFpEF this year? | cited-but-undated passes the span check | every item dated |
| 8 | What are the benefits of SGLT2i in heart failure? | the exact phrasing the old directive forced | overview/lookup; no Do now |

Failure of #4 = over-correction; failure of the rest = the old bias. Structural checks are free
(headings + the emitted `engine` event); an LLM judge on two answers per family is the second leg.
Slice: `evals/realworld/slices/slice-format-8-2026-09-05.jsonl`; checker: `evals/realworld/format_check.py`.

## Risks and guards

- Over-correction on terse decision questions → tie-break rule + eval #4 control.
- New formats invite padding → every format keeps the omit-unsupported clause and `## Not covered`;
  the span/entailment gates are untouched.
- Classifier drift → `engine` events already stream; watch the kind distribution.
- Duel honesty → `route=False` kept for the duel arm only.
- Product signal → the engine trace names the chosen kind; a persistent format badge is a follow-up.

Panel transcripts are not retained; this doc is the record.
