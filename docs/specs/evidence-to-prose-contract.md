# The Evidence→Prose Contract — design spec

**Status:** proposal (not built)
**Date:** 2026-09-09
**Companion:** [`PIPELINE.md`](../../PIPELINE.md) — what the pipeline does today, with the gaps this spec closes
**Governing directives:** CLAUDE.md § *Evidence Is Typed, Not Text* (rules 1–6), Rule 18
(LLM owns meaning, code owns structure), Rule 20 (flag-gated, default OFF)

---

## 1. The problem in one sentence

**We typed evidence at the claim boundary and left the prose boundary string-checked** — so the
sitagliptin failure class (a real quote, honestly cited, meaning something else) has simply moved
one layer up, from claim→evidence to prose→claim, where nothing semantic is looking.

---

## 2. What is already built — do not re-spec

Stages 1–4 of `learnings/evidencecontract.md` landed and are working:

| Built | Flag | Effect |
|---|---|---|
| Evidence identity on every LLM-visible surface | `NOESIS_EVIDENCE_IDENTITY` | atoms render `⟨title — source⟩`; claims must attribute to the source's real subject |
| Unified binding judge across all three claim paths | `NOESIS_CLAIM_CONGRUENCE` | `entailed` / `on_subject` / `kind_ok`; off-subject drops, kind-mismatch demotes |
| QuestionContract + per-entity retrieval legs | `NOESIS_QUESTION_CONTRACT=shadow\|steer` | contract derived pre-retrieval; slot-aware compose seats; zero-claim entities → coverage gaps |
| Enumerative compose routing | `NOESIS_ANSWER_MODE_ROUTING` | enumerative questions get the vertical's enumerative framing |

This spec adds **nothing** to the claim layer. Every item below is downstream of a claim that has
already bound congruent evidence.

Overlap note: the failure taxonomy in [`answer-warrant-contract.md`](answer-warrant-contract.md)
(W1–W9) names *what* can be wrong in a shipped answer. This spec is the *where* — which pipeline
boundary each check sits at, and what object it needs to exist first. Mapping: P1 enforces
W2/W3/W7/W8, P2 enables W5/W6/W8, P3 addresses W1, P4 addresses W5, P5 addresses W6.

---

## 3. The five gaps, in priority order

### P1 — The prose layer has no semantic gate  *(the live correctness hole)*

**Today:** compose output is checked by `_refs_valid` (`react.py:433` — cites ≥1 `[n]`, all in
range) and `_unsupported_prose_tokens` (`react.py:1877` — new digits, **diagnostic only, never
drops**). Every non-numeric distortion ships: scope broadening, design stripping, association→
causation, non-significance→negative claim, negation flips, and an `[n]` that resolves to a real
but irrelevant finding.

**Proposed:** a **sentence-binding judge** — the `_BIND_SYSTEM` judge (`claims_first.py:66`) run one
layer up. Split the composed prose into sentences (code owns the split); for each factual sentence,
send the sentence plus **the findings it cites** and ask the same three-plus-one questions:

```
{"verdicts":[{"i":0,
  "entailed": true|false,     # the cited findings support this sentence
  "on_subject": true|false,   # the sentence's subject is the findings' subject
  "kind_ok": true|false,      # assertion kind matches evidence kind
  "scope_ok": true|false}]}   # NEW: the sentence does not broaden population,
                              # setting, timeframe, comparator or certainty
                              # beyond what its findings state
```

`scope_ok` is the new dimension and the one that catches §5's worked example: *"reduced kidney
function"* asserted from a finding scoped to *eGFR 30–45*.

- **Cost:** 1 batched call per answer (~15–25 sentences, chunked like `_ENTAIL_CHUNK`). Charged to
  `BudgetState`. Runs on `ENTAIL_MODEL`.
- **Enforcement (staged):**
  1. *shadow* — verdicts land in `diagnostics` only. Measure the base rate before enforcing.
  2. *repair* — a failing sentence triggers ONE targeted recompose carrying the specific verdict
     back to the composer ("sentence 4 broadens scope beyond finding [3]"), not a blind retry.
  3. *enforce* — a sentence that still fails is cut, and its content becomes a coverage gap.
- **Fail-safe:** judge unavailable or unruled → annotate `unjudged`, never drop, never a keyword
  fallback (Rule 18). Identical to the claim-layer policy.
- **Kernel litmus:** the judge names "document", "subject", "kind of finding", "scope" — no domain
  nouns. Kind labels arrive as data on the SOURCE line, exactly as at the claim layer. A legal
  vertical reuses it untouched.
- **Flag:** `NOESIS_PROSE_BINDING` = `""` | `shadow` | `repair` | `enforce`.

**Held-out eval cases (CLAUDE.md rule 3 — must exist before enforcement):** every case below is
*designed to pass `_refs_valid` + `_unsupported_prose_tokens`* while being wrong.
- a sentence that drops a population qualifier present in its finding;
- a sentence that turns `p>0.05` into "does not increase";
- a sentence that cites a real, on-topic, but non-supporting finding;
- a sentence whose claim contradicts a *different* finding in the same block;
- a sentence that converts a descriptive observation into a normative recommendation (W2).

---

### P2 — A Finding is a filter, not a fold

**Today:** `verified_claims` is a flat list of `(text, atom_id, quote, source)`, relevance-ranked
and capped at 30 (`react.py:47`). Two documents asserting the same proposition are two unrelated
rows; two documents *contradicting* each other are also two unrelated rows, and the composer
reconciles them silently with no record. `panel.py`'s dedup keys on `(atom_id, normalized quote)` —
lens convergence, not cross-source agreement.

**Proposed:** introduce the missing object.

```python
@dataclass
class Finding:
    proposition: str                  # LLM-written, the thing being asserted
    supporting: list[VerifiedClaim]   # claims that assert it
    contradicting: list[VerifiedClaim]# claims that assert its negation
    agreement: str                    # "corroborated" | "single-source" | "contested"
    sources: list[str]                # distinct document_ids behind `supporting`
```

- **Fold step:** one batched LLM call groups the verified-claim pool into propositions and labels
  each claim `supports` / `contradicts` / `unrelated` for its group. Grouping is *meaning*, so the
  LLM owns it; the dataclass, the ids, and the dedup key are code's (Rule 18).
- **Cost:** 1 batched call per answer, same chunking discipline.
- **What it unlocks, none of which is expressible today:**
  - the findings block renders `[2] … (corroborated: dailymed label + guideline_org guideline)`;
  - **`contested` findings are rendered as contested**, so the composer must state the conflict
    instead of silently picking a side;
  - ranking can prefer corroborated over single-source evidence (a fitness signal we currently lack);
  - the cap counts *propositions*, not claims — 30 findings stop meaning "possibly 30 restatements
    of one fact".
- **Flag:** `NOESIS_FINDING_FOLD`. OFF → the flat list, byte-identical.

---

### P3 — Claims are single-atom by construction, so synthesis is ungrounded by design

**Today:** `claims_first.py:45` mandates *"one specific factual sentence supported by the SINGLE
atom you cite."* Comparative, aggregate, trend and absence-of-evidence statements therefore cannot
exist as claims. They enter at compose, uncited and unjudged — and they are usually the most
decision-relevant sentences in the answer.

**Proposed:** a **derived-claim tier**.

```python
@dataclass
class DerivedClaim:
    text: str
    basis: list[int]        # indices into the finding list — NOT an atom id
    kind: str               # "comparison" | "aggregate" | "trend" | "absence" | "implication"
```

- Judged on **inference validity over its basis**, not on span containment: *"does this statement
  follow from these findings together, adding nothing?"* Same batched judge shape.
- `absence` is the special case worth building deliberately: *"no head-to-head trial exists"* is
  grounded in the **retrieval record**, not in any document, so its basis is the contract's slot
  grid plus the executed legs. This is the one claim type whose warrant is a fact about our own
  search, and it should be typed as such rather than improvised in prose.
- The shape already exists and is validated: `InterpretationItem.basis_findings` +
  `_validate_interpretation` (`react.py:154`, `react.py:385`). **Generalize it out of the Reasoning
  Read** instead of building a second mechanism.
- **Flag:** `NOESIS_DERIVED_CLAIMS`.

---

### P4 — A diagnosed gap does not trigger work

**Today:** under `steer`, contract legs are computed up front and executed speculatively; entities
that end with zero claims are reported as coverage gaps. There is **no re-retrieval between
noticing an unfilled slot and composing**. `gap_planner.py` plans corpus *ingestion*, offline — it
never fires during an answer. So the loop can diagnose its own deficiency and then write the answer
around it, which CLAUDE.md rule 4 explicitly forbids.

**Proposed:** a **gap-triggered re-query round**, once, before compose:

```
after claim binding, before ranking:
  unfilled = contract slots with zero bound claims
  if unfilled and budget.remaining_calls >= reserve:
      run ONE round of targeted legs, one per unfilled slot (k=4, concurrent)
      re-bind the new atoms through the unchanged gates
  remaining unfilled slots  -> honest coverage_gaps
```

- **Bounded by construction:** one round, never recursive; a per-answer reserve is held back from
  `BudgetState` so the round can never starve compose (which is already un-gated on the loop budget
  for exactly this reason).
- Distinct from the speculative legs: those ask *"what might we need?"* before evidence exists; this
  asks *"what did we demonstrably fail to find?"* after.
- **Flag:** `NOESIS_GAP_REQUERY`.

---

### P5 — Selection is an unaudited editorial act

**Today:** compose sees ≤30 of a pool that can be far larger. Which 30 is decided by relevance
ranking plus optional tier boost and slot reservation. **Nothing checks that the survivors are
representative.** Thirty confirming findings selected from a pool that contained a contradiction
pass every gate we have, and diagnostics show only a tier histogram.

**Proposed (cheap, deterministic, no LLM call):** once P2 exists, the fold already knows which
claims contradict which. At cap time, emit:

```json
"selection_audit": {
  "pool": 214, "selected": 30,
  "dropped_contradicting_a_selected_finding": 3,
  "propositions_dropped_entirely": 11
}
```

Surface a non-zero `dropped_contradicting_a_selected_finding` as a **coverage gap**, not a log line:
the answer is resting on a selection that discarded its own counter-evidence, and the reader is
entitled to know. Structural, Rule-18-clean, costs nothing.

---

## 4. Phasing

| Phase | Work | New LLM calls / answer | Gate to proceed |
|---|---|---|---|
| 1 | P1 in `shadow` | +1 batched | measure the base rate of prose-layer failures on real answers |
| 2 | P1 `repair`, then `enforce`; held-out evals first | +1, +1 on repair | eval suite from §3-P1 passes; no regression in answer usefulness |
| 3 | P2 fold + P5 audit | +1 batched | contested findings render correctly on real questions |
| 4 | P3 derived claims | +0 (rides the P1 batch) | inference-validity judge agrees with human review on a held-out set |
| 5 | P4 gap re-query | +0 LLM, +retrieval | slot fill rate improves without a latency blowout |

**Spend discipline (CLAUDE.md § API-Credit Discipline):** phase 1 is measured on *banked* prod
answers re-judged offline — no new answer generation — so it costs one batched judge call per
banked answer and nothing on the answer side. Phases 2–5 need a projected budget and an explicit go
before any batch; validate on 1–2 questions before any tranche.

---

## 5. What this spec deliberately does not do

- **Does not weaken the span gate.** Every check here is *additional*; G1 stays immovable.
- **Does not add a numeric score anywhere.** Every judgment above is a semantic one and belongs to
  the LLM; code owns the split, the ids, the dedup, the caps and the fail-safe (Rule 18).
- **Does not put a domain noun in the kernel.** Kind vocabularies, axis names and directives keep
  arriving as vertical-supplied data. Litmus: a legal vertical gets prose-scope checking, contested
  findings and absence-claims by supplying its own manifest entries, kernel untouched.
- **Does not turn compose into a multi-pass pipeline by default.** Everything is flag-gated and OFF
  is byte-identical, per Rule 20.
