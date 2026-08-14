# The Panel Output Contract (v1, 2026-08-14)

What a Specialist Panel answer MUST produce, in what format, and on what grounding. This
is the definitional artifact: the synthesis directives and addenda in
`packages/vertical_medical/noesis_vertical_medical/specialists.py` implement it, and
panel evals judge against it. Owner-stated bottom line: **actionable, well-reasoned,
clinical-grade output, grounded in a principled way.**

## Why a panel exists

A panel runs when multiple clinical lenses would MATERIALLY change the answer. Its value
is the ANALYSIS COMING TOGETHER: not N mini-answers stapled together, and not a flattened
average that hides who disagreed — the visible convergence, divergence, and resolution of
expert perspectives on each decision the case contains.

## The five obligations

**1. The decision surface, made explicit.** Every clinical decision the case contains —
workup choices, treatment starts/stops/holds, monitoring calls — enumerated as first-class
objects with their options. A case question is a bundle of decisions; the answer's
structure must be the decisions, never a wall of themed prose.

**2. Actionable, in scannable form.** Per decision: what to DO NOW, the decisive
threshold or result that changes the action ("eGFR < 30"), and the action it triggers
("stop metformin"). Sequenced do-first. Concrete — doses, thresholds, timeframes wherever
the evidence supplies them. The actionable layer must be absorbable in under a minute
(the grid); depth lives below it, never instead of it.

**3. Reasoned and attributed.** The panel's position per decision names WHICH specialties
agree and which dissent, and why. Tensions are stated AS tensions with the reconciliation
logic ("ID cautions against reflexive antibiotics; geriatrics ranks infection first —
reconciled by targeted testing before treating"). Silent averaging of disagreement is a
contract violation: the disagreement IS the information.

**4. Principled grounding.** Every actionable cell carries its [n] citations to verified
findings; the evidence KIND stays visible (guideline vs RCT vs label vs consensus);
consensus-level guidance is labeled as such, never dressed as trial evidence. Nothing
appears in the grid that is not in the verified findings — the grounding invariant is
inherited from the Q&A path unchanged (identity-tagged, congruence-judged claims).

**5. Honest edges, computed not lucky.** Panel-level coverage gaps ("no specialist
retrieved evidence for X") are COMPUTED from the shared contract's slot grid and always
rendered — a gap the pipeline found, not one a specialist happened to mention. Plus: the
uncertainties that would change the answer, and safety red flags FIRST when present
(urgency outranks completeness, same as intake).

## The format contract

1. **Bottom line** — ≤3 sentences: the do-first action(s) and the single most important
   caution. Red-flag banner above it when applicable.
2. **Decision grid** — one row per decision/cause: Do now [n] | Decisive
   threshold/result [n] | Action it triggers [n] | Panel position (specialties agreeing;
   dissenting) | Open gap.
3. **Agreements & tensions** — attributed convergence ("independently found by 4
   lenses") and named disagreements with reconciliation.
4. **Safety** — interactions, contraindications, monitoring; adjacent to anything the
   grid recommends.
5. **Evidence quality & gaps** — kind distribution, confidence, the computed coverage
   gaps.
6. **Deliberation notes** — the reasoning depth for readers who want it.

## How it's enforced

- Implementation: `PANEL_DECISION_ADDENDUM` / `PANEL_ENUMERATIVE_ADDENDUM` +
  the amended attribution rule (structured attribution required, narrative
  he-said-she-said still banned) — flags `NOESIS_PANEL_CONTRACT` / `NOESIS_PANEL_DEDUP`.
- Evaluation: panel answers are judged pairwise on the five obligations as dimensions
  (decision-surface completeness, actionability, attribution/reasoning, grounding
  discipline, honest edges). A panel answer that reads beautifully but fails obligation
  2 or 5 loses.
- Evolution: change this contract first, then the directives, then measure — the same
  order as everything else.
