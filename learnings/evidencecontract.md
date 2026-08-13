# Evidence Contract — design spec (draft v1, 2026-08-13)

Redesign of the answer pipeline's evidence model, motivated by the sitagliptin failure
(prod session c4afba43: renal-dosing quotes from non-antibiotic labels attributed to
"antibiotic labels"; every string-level check passed). Governing directive:
CLAUDE.md "Evidence Is Typed, Not Text." Panel findings that ground this spec:
`document_title` exists on `Atom` (atoms.py:22) but is rendered on ZERO LLM-visible
surfaces (react.py:642 planner obs; claims_first.py:92 extractor; claims_first.py:131
entailment; react.py:1007 compose findings; panel.py:189 panel synthesis); the span gate is
provenance-only (react.py:624-632); loop-emitted claims bypass entailment entirely;
`evidence_fitness` is a tier boost, not congruence (react.py:342,394,992); multi-query
fusion truncates all reformulations to one k=10 pool (retrieval/dispatch.py:47-68);
`MedicalGatingPolicy.coverage_gap` is a dead stub (always None); compose writes
`coverage_gaps` after the answer exists (react.py:1186-1189) with no re-entry;
claims-first LLM calls bypass BudgetState.

## 1. The design change in one sentence

Evidence stops being anonymous text: every piece of evidence carries an IDENTITY, every
question gets a CONTRACT describing the evidence shape it requires, claims must BIND to
congruent evidence, and COVERAGE (contract slots filled) steers retrieval — so
off-subject evidence is visible, non-bindable, and re-queried away instead of composed
around.

## 2. Core objects (kernel-generic; vertical supplies vocabulary)

### EvidenceIdentity (attached to every atom/claim surface)
```
{ document_title: str,      # verbatim from the doc record — never parsed/regexed
  source_key: str,          # connector ("dailymed", "epmc", ...)
  evidence_kind: str,       # one key from the VERTICAL's kind vocabulary (see 2.3)
  subject_hint: str }       # short LLM-written "what/who this document is about"
```
- `document_title`/`source_key`: already in the data path (Atom, BlockHit, VerifiedClaim)
  — rendering them is free.
- `evidence_kind` + `subject_hint`: LLM-judged ONCE per (document, vertical), cached in a
  new table `noesis_doc_identity(document_id, vertical, evidence_kind, subject_hint,
  judged_at)`. Judged lazily at retrieval time for candidate docs only (never a bulk
  850k-block ingest pass). Documents are immutable → cache never expires. Fail-safe: if
  the judge fails, identity = title + source only, and congruence (below) falls back to
  title-based judgment — never a keyword guess.

### QuestionContract (derived pre-retrieval, one small LLM call)
```
{ mode: "enumerative" | "exploratory",   # kernel-generic; ACT≈enumerative, DISCOVER≈exploratory
  entities: [str],          # candidates to enumerate (empty in exploratory mode)
  axes: [ {axis: str, acceptable_kinds: [str]} ],  # required dimensions + admissible evidence kinds
  population: str }         # "" when unconstrained
```
- The vertical manifest supplies the derivation prompt (naming axes like dosing/
  interactions/contraindications and its kind vocabulary); the kernel supplies mechanics
  only. Litmus: a legal vertical derives {statute, case-law, regulation} contracts with
  the kernel untouched.
- For the transplant question this yields: mode=enumerative; entities=[common candidate
  antibiotics]; axes=[{renal dosing, [label-dosing]}, {immunosuppressant interactions,
  [label-interactions, guideline]}]; population="kidney transplant, reduced eGFR".
- Piggybacks on the existing reasoned scaffold call where that engine is on
  (runtime/research.py:164-197); standalone small call otherwise.

### Binding (claims must be congruent, not just quoted)
A claim binds evidence only if the congruence judge affirms:
- subject match (claim's named subject ↔ evidence identity/subject_hint/title),
- kind match (what the claim asserts ↔ evidence_kind: a safety/dosing claim cannot bind
  resistance-surveillance or efficacy evidence),
- population compatibility (soft: mismatch → demote + annotate, not drop).
Unbindable claim ⇒ the claim does not exist (dropped pre-compose, logged in diag trace).
LLM-owned judgment (Rule 18); implemented INSIDE the existing batched entailment call
(claims_first.py) extended with question + identity per item — and loop-emitted claims go
through the same batch (closing the bypass at react.py:624-632). All these calls are
charged to BudgetState (fixing the standing undercount).

### Coverage (the loop's steering signal)
`coverage = axes × entities` slot grid; a slot is filled when ≥1 bound claim (or
explicitly judged "no evidence found after targeted query"). Before compose, if unfilled
slots remain AND budget remains: ONE bounded re-query round targeting exactly the
unfilled slots (per-slot retrieval legs). Remaining unfilled slots become the honest
`coverage_gaps` — same output field as today, but now produced by the loop where it is
actionable, not by compose where it is a footnote. The dead
`MedicalGatingPolicy.coverage_gap` stub is deleted.

## 3. Retrieval: per-entity/axis legs (not fused-away)

Enumerative contracts expand to one retrieval leg per (entity × axis) — capped (default
12 legs) — executed like graph legs (react.py:739-778 seam; the `[:2]` cap at react.py:743
becomes a parameter). CRITICAL: legs are separate RetrievalRequests whose results merge
into the atom pool with per-leg quotas — they must NOT go through `multi_query_retrieve`'s
single fused k=10 truncation (dispatch.py:65), which would silently starve most entities.
Exploratory contracts skip legs (today's behavior).

## 4. Staged delivery (flags, all default OFF; each stage gated on evals)

| Stage | What | Flag | Added cost |
|---|---|---|---|
| 1 | Identity rendered at ALL 5 surfaces (planner, extractor, entailment, compose, panel synthesis); claim writer must name its source's subject | `NOESIS_EVIDENCE_IDENTITY` | 0 calls, ~10 tok/atom |
| 2 | Congruence binding in the extended entailment batch; loop-claim bypass closed; BudgetState charging | `NOESIS_CLAIM_CONGRUENCE` | 0–1 batched call |
| 3 | QuestionContract + per-entity/axis legs + doc-identity cache + coverage-steered single re-query | `NOESIS_QUESTION_CONTRACT` | +1 small call, +N retrievals, +≤10 cached doc judgments, ≤1 re-query round |
| 4 | Enumerative compose directive variant (practical table) | `NOESIS_ANSWER_MODE_ROUTING` | 0 (mode from contract) — 092dd35 protected: ships only through compose A/B |

Stages are independently shippable; 1→2→3 strictly ordered (each makes the next's inputs
meaningful). Observability: per-claim identity + congruence verdict + slot grid in the
diag trace (NOESIS_DIAG_TRACE), so a wrong answer is debuggable without a rerun.

## 5. Eval gates (all held-out; spend-gated)

- Baseline FIRST on `evals/realworld/slices/slice-act-heldout-5-2026-08-13.jsonl` (must
  fail today); re-run per stage. Ship gate: transplant case 4/4 must-haves, zero
  contradictions, zero claims citing a document whose identity mismatches the claimed
  subject.
- No-harm: frozen K-QA + HealthBench slices (recall + contradiction rate must not
  regress) — guards against the main risk, congruence over-filtering true claims.
- Gate-fooling cases (CLAUDE.md rule 3): add one case per new gate designed to pass it
  while wrong (e.g. right drug, wrong population; right kind, wrong subject in a
  same-class sibling drug).
- Stage 4 additionally through `evals/realworld/compose_ab.py`.

## 6. Explicitly not building

Regex/keyword drug-class matchers anywhere (Rule 18); bulk identity ingest over the full
corpus; kernel-level domain vocabulary (kinds/axes live in the manifest); unbounded
iteration (exactly one re-query round); a wholesale compose-directive rewrite; per-claim
unbatched verification calls.

## 7. Open questions (for panel)

1. Identity attachment point: retrieval-time doc-level cache (proposed) vs block-level vs
   answer-time only — is doc-level identity ever misleading (multi-subject docs: reviews,
   comparative trials)?
2. Contract derivation failure mode: misclassified mode/entities steers retrieval wrong —
   is the fallback (exploratory mode = today's behavior) safe enough?
3. Congruence recall risk: how much true-claim loss is acceptable before the no-harm gate
   fails; should population mismatch demote or annotate only?
4. Legs budget: 12-leg cap × embeddings — right ceiling? Interaction with graph legs?
5. Does stage 2 need the question in the entailment batch, or is identity alone enough
   (cost/precision tradeoff)?

---

# v2 — PANEL AMENDMENTS (2026-08-13; codex + gemini 3 pro + code-grounded seat, adversarial protocol)

All 11 checkable premises verified by all three seats (several understated in the spec's
favor: the fallback grounder and frame-repair calls ALSO bypass entailment/budget;
evidence_fitness only fires when verified > compose cap). The spec's diagnosis stands; its
design needed surgery. Binding rulings:

**A1 (code seat's killer objection): "off-subject evidence is non-bindable" is FALSE as
written.** A correctly-attributed off-subject claim ("Sitagliptin requires dose adjustment
at eGFR<45", citing the sitagliptin label) is self-congruent — it binds, fills no slot, and
can even EVICT slot-filling claims from the 30-claim compose cap via question-global cosine
ranking (react.py:992-997). Fix: slot-aware selection into the compose cap (slot-filling
claims reserved first), and enumerative-mode policy for off-contract bound claims (demote
below all slot-fillers; never evict one).

**A2 (all seats): CUT the LLM doc-identity judgments + noesis_doc_identity cache +
subject_hint from v1.** Doc-level subject on multi-subject documents (reviews, comparative
trials, combo labels) poisons recall permanently; cold-cache cost (30-120 judgments/run)
bankrupts BudgetState (ceiling 40-60). v1 identity = document_title + source_key + the
EXISTING structural evidence-kind classifier (authority.py vocabulary, evidence_kind.py:81,
already wired onto VerifiedClaim — the spec wrongly introduced a second incompatible kind
vocabulary). Add LLM identity later ONLY if the slice shows title-based congruence missing,
and then versioned (judge/prompt/vocab) with a re-stamp path, block-level for multi-subject
docs.

**A3 (all seats): stages 1+2 ship modified; stage 3 does NOT ship as specced.**
- Stage 1: render title (length-capped) + source_key + structural evidence_kind on ALL
  surfaces INCLUDING the fallback grounder and panel synthesis. No new semantics.
- Stage 2: ONE unified batched binding judge covering loop + claims-first + fallback-grounder
  claims (closing all three bypasses). Verdicts: subject mismatch → hard drop (the
  sitagliptin fix); kind + population mismatch → demote + annotate (recall-safe start;
  tighten only on eval evidence). Population wording comes from the vertical-supplied
  contract param — never kernel prompt (litmus). Judge-didn't-run (budget/flag/keys) →
  annotate-not-drop. All calls charged to BudgetState with an explicit ceiling re-plan
  (also charge the fallback grounder + frame-repair calls the spec missed).
- Stage 3 rebuilt as "slot grid + shadow first": contract derived (scaffold piggyback where
  it runs; NOTE the scaffold is SKIPPED on follow-ups — research.py:153-158 — so the
  standalone call is the common path, price it as such). Contract legs run in SHADOW
  (logged, not steering) with baseline retrieval mandatory; a confident-wrong contract must
  be observable before it may steer (a missing slot is never created — coverage can lie).
  Slot grid + honest loop-produced gaps ship; the re-query round is funded only after
  shadow data shows unfilled slots persist post-1+2 (its true cost = re-extract +
  re-entail, not "+N retrievals"). Legs: unified cap WITH graph legs, global k_total spread
  across legs (not 12×k=10 → 120 atoms, which blows planner_atom_window=60 /
  claims_first atom_cap / compose cap), executed concurrently, SSE progress events.
- Stage 4: unchanged (A/B via compose_ab.py, last, never bundled with retrieval changes);
  re-derive mode from BOUND CLAIMS at compose time rather than trusting the pre-retrieval
  contract.

**A4 (codex): the transplant contract example needs an explicit safety/nephrotoxicity
axis** — renal-dosing + interactions alone can still pass the aminoglycoside trap.
Axis vocabularies and kind-compatibility live ENTIRELY in the manifest-driven derivation
(the axes' acceptable_kinds ARE the compatibility rule); the kernel judge takes them as
caller-supplied data.

**A5 (codex): genuine same-subject contradictions remain out of scope** — stage 1
dissolves the OBSERVED contradiction (different-subject claims misread as one subject),
but no cross-claim contradiction check exists or is added here; noted as future work.

**Sequencing ruling (code seat's null hypothesis, adopted):** 4 of the 5 original failures
fall to stages 1+2 alone. Order: baseline slice run (fails today) → stage 1 → stage 2 →
re-run slice + K-QA/HealthBench no-harm (bar: must-have recall drop ≤2pt absolute,
contradiction rate not worse) → fund stage-3 pieces only if the data demands them.
