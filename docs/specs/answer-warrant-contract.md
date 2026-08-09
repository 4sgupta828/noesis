# The Answer-Warrant Contract (first-principles backbone)

**Purpose:** define, once, what makes a Noesis recommendation *trustworthy* — then derive the eval, the
auditor, and the feedback log from that single definition, so the work is first-principles (one
contract, three uses) rather than a pile of symptom patches.

---

## 1. The invariant we have vs. the invariant we want

- **Today (provenance):** *no sentence without a verbatim-verified quote in its cited source.* This is
  why Noesis doesn't hallucinate — but "a real quote exists" ≠ "this advice is warranted."
- **Target (warrant):** *no recommendation without a **warrant**.* A recommendation is **warranted**
  iff its evidence **exists**, **applies** to the question, **supports the inference** (not just
  mentions the topic), and is the **appropriate tier**; and the answer as a whole **covers** the
  material options, **states its conditions**, and **calibrates its confidence**.

Provenance is a *necessary* part of warrant, not the whole of it (this is exactly Rule 6:
"audit-pass is provenance, not correctness"). This spec upgrades the contract from provenance to warrant.

The auditor is a **transitional enforcement layer.** The end-state first-principles fix is a generator
that reasons in warrant terms and rarely emits an unwarranted claim. We cannot design that generator
responsibly until the eval tells us *which* warrant conditions break and *how often* — so:
**measure → enforce → learn where the generator fails → fix at the source.**

---

## 2. Warrant decomposed — the failure-mode taxonomy (the ONE list)

The complete set of ways an answer can be wrong *even when every quote is real*. This list is
simultaneously the **eval rubric**, the **auditor checklist**, and the **feedback schema**.

| # | Failure mode | Warrant condition it breaks | Example |
|---|---|---|---|
| W1 | **Unwarranted** | supports-the-inference | source mentions NMS but doesn't establish "order CK" |
| W2 | **Descriptive→normative** | supports-the-inference | "patient received a CT" → "obtain a CT" |
| W3 | **Inapplicable** | applies | CAR-T infection guideline cited for routine delirium |
| W4 | **Tier-mismatch** | appropriate-tier | a single case report driving a routine order |
| W5 | **Coverage gap** | covers material options | seizure pathway silently omitted |
| W6 | **Salience distortion** | covers → weighting | the topic with the most papers dominates |
| W7 | **Conditionality collapse** | states conditions | "do if febrile" presented as routine |
| W8 | **Contradiction** | internal consistency | a recommendation fights a stated safety caveat |
| W9 | **Miscalibration** | calibrates confidence | "high confidence" on low-tier, low-applicability evidence |

**Rule-18 discipline:** every one of W1–W9 is a **semantic judgment → owned by the LLM**, never a
regex/threshold. Code owns only *structure* (counting, budgets, persistence, tallies). In particular
W2 is NOT "regex for the word *should*"; W4 is NOT "rank < threshold"; W6 is NOT a document count.

---

## 3. Three uses of the one contract

- **Eval (measure).** For a held-out set of case-shaped questions, run the current product, then judge
  each answer against W1–W9 → a per-failure-mode rate. This tells us which conditions actually break
  and how often — the data that prevents redesigning in the dark.
- **Auditor (enforce).** The same W1–W9 judgment, run adversarially on a live answer's
  recommendation-bearing claims, fed the **surrounding source text** (not just the verified quote —
  else it rubber-stamps). Verdict → **downgrade/annotate by default**, drop only on an unambiguous
  W2 breach. Never folded into the compose call (a writer rationalizes its own blind spot).
- **Feedback log (learn).** Every auditor verdict AND every user signal (👍/👎, "flag this claim")
  persists with its W-code, so the distribution of failures is **visible and accumulating over time**.
  That distribution is the roadmap: the W-code that fires most is the next thing to fix in the
  *generator*, not just the auditor.

---

## 4. The improvement loop (why a post-hoc step still makes answers better)

1. **Immediate:** the reader only ever sees the *reviewed* answer — mis-sourced/over-claimed lines are
   corrected, re-attributed, or softened before display (editor-before-publish, not a warning label).
2. **Compounding:** the accumulating W-code distribution shows *where the generator systematically
   slips*, which we feed back into the compose prompt / retrieval contract — so future answers are
   better *before* they reach the auditor. Over time the auditor's job shrinks as the generator
   internalizes warrant. That shrinking is the signal we're solving it at the source, not patching.

---

## 5. What we build, in order (each gated on measured need)

1. **The eval harness** (`scripts/eval_warrant.py`): case set + W1–W9 judge + per-mode rates,
   persisted to an accumulating store. *This is step 1 — it measures whether the problem is real.*
2. **The feedback store + view:** one table keyed by W-code (auditor verdicts + user feedback), with a
   simple admin view so the signal is watchable over time.
3. **The auditor (C1)** for the top-firing modes (W2/W3 first) — enforce warrant on live answers.
4. **Generator fixes** for whatever the log shows is chronic — the actual first-principles root cause.
5. **Coverage (C2)** only if W5/W6 prove frequent.

Guardrails carried from the panel review (`reasoning-and-claim-audit.md` §7): auditor sees source text
not just the quote; downgrade-not-drop; keep W2/W4/W6 LLM-owned (no modal-regex, no rank-threshold, no
doc-count); case-shaped detection reuses the existing triage signal, not a vitals regex.
