# Design spec: reasoning-coverage + claim→evidence audit layer

**Status:** proposal (for judge-panel review before any build)
**Author:** Sandeep + Claude
**Context:** external critique argued Noesis behaves as "RAG with exceptionally good provenance"
rather than "evidence-grounded clinical reasoning," and that answers are built by accumulating
citations instead of by reasoning first and retrieving to validate. This spec is the *scoped* response.

---

## 1. Problem statement

Noesis's grounding invariant proves **the quote exists in its cited source** (provenance). It does
**not** prove:
- the source **entails the clinical inference** being drawn (only that the span is real);
- the source's **population / setting / purpose is applicable** to the question;
- a **descriptive** statement ("patient X received a CT") isn't being used to justify a **normative**
  recommendation ("obtain CT in this patient");
- retrieval **covered the clinically important branches** rather than over-weighting whatever topic
  happened to return the most documents (evidence-volume bias).

This is not a new observation — it is exactly the gap our own operating rules already name (CLAUDE.md
Rule 6: "audit-pass is provenance, not correctness"; Rule 7: adversarial boundary cases). The critique
is validating a known-but-unbuilt TODO. The goal here is to add a **reasoning-coverage + claim-audit
layer on top of the grounding engine** — NOT to replace retrieval-first grounding, and NOT to turn the
evidence research engine into a bedside DDx tool.

**Non-negotiables (must survive):** the verbatim-quote grounding invariant; LLM-owns-meaning /
code-owns-structure (Rule 18 — no numeric scoring formulas or keyword heuristics for semantic
judgments); flag-gated + default-OFF (Rule 20); bounded LLM cost.

---

## 2. Current architecture (grounded in code)

- **ReAct loop** `run_react` (`research/react.py:443`): planner-driven **search → span-verify →
  compose**. Verified claims are minted in `_mk_verified` (`react.py:531`); compose in `_compose`
  (`react.py:836`). Retrieval is the driver; there is no explicit clinical **decision structure**
  built before retrieval.
- **Grounding = span existence.** A claim survives if its quote is located in the source. Correctness /
  applicability / entailment are **not** checked. Reasoning-Read adds a post-hoc interpretation +
  confidence layer (`react.py:960`, `_validate_interpretation:249`, `_frame_grounded:239`) — it reads
  the evidence *after* retrieval; it does not steer retrieval.
- **Panel** (`research/panel.py`): `plan_panel` (`panel.py:38`) already does **coverage-first**
  specialist selection ("convene a lens for EVERY clinically important dimension"). `run_panel`
  (`panel.py:122`) runs each specialist as its own `run_react` (`_SPECIALIST_MAX_STEPS=4`,
  `_SPECIALIST_MAX_CALLS=12`), pools VerifiedClaims, and the chair synthesizes under
  `PANEL_SYNTHESIS_DIRECTIVE` (`specialists.py:226`) — which already emits a clinical container
  (Bottom line / Key recommendations / Safety / Uncertainties).
- **Evidence tiers exist:** `MedicalAuthorityPolicy.rank` (`authority.py:29`) + `evidence_kind.classify`
  (`evidence_kind.py:81`) drive the `evidence_fitness` tier boost into the compose window. There is **no
  applicability dimension** (authority alone, not authority × applicability).

So ~4 of the critique's points ("evidence hierarchy," "coverage-first differential," "executable
output," "confidence decomposition") are **already partially present** and only need extension.

---

## 3. Proposed changes (scoped, prioritized)

All four are LLM-owned, fail-safe (weaken/abstain, never fabricate), flag-gated default-OFF, and
validated by the eval in §5. They target the **case-shaped / panel path** first, not global Quick Q&A.

### C1 — Claim→evidence AUDITOR (highest leverage; extends span-verify into the correctness layer)
A post-compose adversarial pass over each **recommendation-bearing** claim. For each, an LLM judge
returns a typed verdict:
- **entailment**: does the cited source actually *entail* this claim, or merely mention the topic?
- **applicability**: does the source's population / setting / purpose match the question? (the
  "CAR-T guideline for a delirium patient" failure)
- **evidence-type**: NORMATIVE (recommends action) · DIAGNOSTIC-PERFORMANCE · ASSOCIATIONAL ·
  MECHANISTIC · DESCRIPTIVE · CASE. Enforce the **descriptive→normative firewall**: a
  descriptive/case source alone cannot license a routine recommendation.
- **tier-expectation**: is a higher-tier source reasonably expected for this kind of claim?

On any material fail → **downgrade the language** ("reported/observed" not "should"), **re-attribute**,
or **drop** the recommendation. This is the "citation auditor" done right; it directly implements the
Rule-6 correctness layer we already said we owe. Runs on the final synthesis (panel chair output), not
per-specialist, to bound cost. Structured output, cached by (claim, source) since a filed source is
immutable.

### C2 — Reasoning-coverage SCAFFOLD + per-branch evidence budget (panel/case path)
Before/alongside retrieval, decompose a *case-shaped* question into the **branches/decisions to
cover** — differential dimensions, can't-miss, tests-to-consider, treatment decisions — as a
**retrieval + coverage plan, NOT a set of conclusions** (this preserves grounding: the scaffold says
what to *search for and cover*, it never pre-commits the answer). Then:
- steer retrieval to cover each branch;
- **cap evidence per branch** (e.g. 2–3 strong sources per claim before moving on) to kill
  volume bias — a topic with more retrievable docs no longer dominates;
- a final **coverage critic**: "what materially plausible, actionable branch is uncovered?" (catches
  the missing-seizure-pathway class).
Reuses/extends `plan_panel`'s coverage-first framing; the budget is a *structural* cap (code owns
structure), the branch selection and coverage judgment are *LLM-owned*.

### C3 — Conditionality + executable output contract (prompt-level, cheap)
Extend `PANEL_SYNTHESIS_DIRECTIVE` so recommendations are emitted as **Action → Trigger → Reason** and
grouped **Do now / Do if X / If initial workup unrevealing**, with priority framed by *probability ×
severity-if-missed × actionability* **as qualitative guidance, NOT a computed matrix or formula**
(Rule 18). Mostly a directive change on top of the existing clinical container.

### C4 — Extend confidence decomposition (small)
Reasoning-Read already splits confidence into factual / causal / generalization. Add
**recommendation-confidence**, **applicability**, and **urgency** dimensions so a "low-probability,
high-consequence, high-test-evidence, conditional-recommendation" case reads truthfully. Extends the
existing `confidence` structured field; no new pipeline.

---

## 4. Explicit NON-goals (what we are NOT doing, and why)

- **No global "reason-first" rewrite of Quick Q&A.** For evidence-research questions ("what does the
  evidence show for X"), comprehensive evidence accumulation is *correct*; a patient decision graph is
  mismatched. Scope C2 to case-shaped/panel questions (triage already routes these).
- **No hard-coded scoring formulas / 1–10 ranks / info-gain equations** (Rule 18). The critique's
  `Test value ≈ info-gain × impact × urgency − cost` and numeric hierarchy are the wrong
  implementation; these are LLM-owned qualitative judgments if built at all.
- **No parametric "reason before retrieving" that pre-commits conclusions** — grounding hazard. The
  scaffold plans retrieval; it does not answer from memory.
- **No full DDx / decision-graph engine** (that's Glass Health's product, a scope/strategy decision,
  not a bug fix).
- **Cost guard:** C1+C2 add LLM calls on top of N-specialist panels. Keep C1 on the final synthesis
  only; keep C2's scaffold a single call + a bounded coverage critic. Measure the added spend.

---

## 5. Eval-first plan (build this BEFORE the fixes — Rule 4/7)

We are re-thinking on a single anecdote. Before building, construct a **held-out eval** of case-shaped
questions graded for the specific failure modes, and measure the *rate*:
- descriptive/case source used to justify a routine recommendation (normative firewall);
- low-applicability source cited (population/setting mismatch);
- evidence-volume domination (one topic crowds out the differential);
- missing can't-miss / actionable branch;
- conditional test presented as routine; recommendation contradicts a stated safety warning.
Each fix (C1–C4) must move its target metric on held-out cases without regressing the grounding
invariant or blowing the cost budget. If a failure mode is rare in the eval, deprioritize its fix.

---

## 6. Open questions for the judge panel

1. Is the scoped "audit + coverage layer on top of grounding" the right call vs. the critique's fuller
   reasoning-first rearchitecture — given our provenance moat, Rule 18, and cost envelope?
2. C1 vs C2: which is higher-leverage to build first? (hypothesis: C1, the auditor.)
3. Does C2's "scaffold plans retrieval, never pre-commits" actually preserve grounding, or does it
   smuggle in parametric reasoning risk?
4. Right scope boundary: panel-only, or also case-shaped Quick Q&A? How to detect "case-shaped"
   without a brittle heuristic?
5. Cost: is a per-recommendation auditor on the final synthesis affordable at panel scale? cheaper
   design?
6. What's the smallest version that would move physician-perceived quality, and what would we regret?

---

## 7. Judge-panel review outcome (decision)

Reviewed by Gemini 3 Pro + two code-grounded readers (Codex crashed mid-run and was substituted).
Strong consensus. Decisions and corrections:

**Verdict: ship the scoped layer, NOT the reason-first rebuild.** The rebuild discards the fail-safe
posture, cannot be built without the Rule-18-violating formulas, and blows the cost envelope for a
problem not yet measured.

**C1 is ~80% of the physician-perceived value; C2/C3/C4 are polish.** Sequence:
**eval → C1 → measure C2's failure rates from C1's own verdict logs → build C2 only if data justifies.**
(C1's verdicts double as the instrumentation for whether coverage/volume-bias is actually frequent.)

**Corrections to §2–§3 (the code contradicted a few "already present" claims):**
- An **entailment gate already exists** but only under the `claims_first` flag (`entail_claims`,
  `research/claims_first.py:114`); the default/panel path has none. C1 *extends* this primitive with
  applicability + the normative firewall — it is not built from scratch.
- **C4 is Q&A-only, not a small panel extension.** The panel deliberately runs `reasoning_read=False`
  (`panel.py:153`, comment ~251 — the model malforms it when asked for both). C4's substrate exists
  only on the `run_react`/Q&A path. Deprioritize or rescope; do not silently re-enable the panel layer.
- **C2 is net-new, not a `plan_panel` reuse.** `plan_panel` covers *specialties/lenses*, not the
  clinical differential/can't-miss/test space, and the panel has **no** gap-surfacing plumbing
  (`directly_addresses`/`gap_note` are absent from the panel compose). Stop calling C2 "extend
  plan_panel."

**C1 build rules (from the panel):**
- One **batched** structured audit call over the final synthesis (verdict array `claim_id →
  {entailment, applicability, evidence_type, action}`), ~+2–5% cost; cache by `(claim, source_key)`
  (sources immutable).
- **Feed the auditor the atom's surrounding source TEXT (`atom.text`), not just the verbatim quote** —
  a quote-only auditor rubber-stamps (that *is* the Rule-6 "provenance masquerading as correctness"
  trap). Keep it a **separate adversarial pass**, never folded into compose.
- **Default action = DOWNGRADE/annotate, not DROP** (a false-positive applicability call silently
  deleting a correct recommendation is worse than the disease). Reserve DROP for unambiguous
  descriptive→normative breaches. Log every verdict (Rule 13, reversible).
- Runs on **any recommendation-bearing answer (panel + Q&A)** — normative-firewall breaches happen in both.

**C2 grounding firewall (the biggest regret to avoid):** the scaffold output may flow to EXACTLY two
sinks — (a) retrieval query formulation (the `focus`/`query`/`notes` search-steering seam) and (b) a
coverage critic that reads the **verified findings** and names an uncovered branch as a `coverage_gap`.
It must **NEVER** reach the findings list / `compose_user` / `verified_claims` / answer prose (enforce
with the existing `_unsupported_prose_tokens` guard). Prefer "cap what the composer *sees* per branch"
over "delete retrieved atoms" (a hard cutoff can drop the discriminating source).

**Three Rule-18 slip-points to guard explicitly in any build brief:**
1. C1 "tier-expectation" must be an **LLM verdict**, never `rank(source) < THRESHOLD`.
2. C1 descriptive→normative firewall must be **LLM evidence-type classification**, never a **regex for
   modal verbs** ("should"/"recommend"/"indicated") — the classic Rule-9/18 trap.
3. C3 "probability × severity × actionability" stays **qualitative prompt guidance**, never a computed matrix.

**Scope detector:** reuse the existing triage LLM signal (`triage.py` `recommended_mode: qa|panel`) to
tell case-shaped from lookup — never an age/"year-old"/vitals regex.

**Smallest version that moves quality:** eval + C1's **normative firewall alone** (defer C1's
tier-expectation sub-check) + C3's Action→Trigger conditionality (≈free prompt change).
