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
