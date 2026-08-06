"""Medical answer-structure directive — how a clinician reads an evidence answer.

This is domain knowledge (clinical section names + evidence-pyramid language) and lives
ONLY in the medical vertical. The kernel treats it as an opaque string appended to the
grounded-compose step; it never sees these words. It shapes STRUCTURE only — the compose
step still sees ONLY span-verified findings and may not add facts beyond them.

ADAPTIVE by design: sections appear only when the verified findings support them (never
fabricate to fill a heading). A table is used only when the findings genuinely contain
comparable data. This is research SUPPORT, not medical advice.
"""
from __future__ import annotations

MEDICAL_ANSWER_FORMAT = """\
Format the answer as Markdown for a clinical audience. Include a section ONLY IF the \
verified findings above contain information to support it — OMIT any section you cannot \
ground in the findings; never infer or add outside knowledge to fill a heading. Every \
factual sentence, bullet, and table cell must carry an inline [n] citation to a finding.

Use these sections, in this order, where supported:

## Bottom line
One or two sentences that directly answer the question, with [n] citations.

## Efficacy
What the evidence shows about effectiveness / outcomes. Bullets or a short table when the \
findings compare options or report figures.

## Safety & adverse effects
Reported adverse effects and risks. Distinguish short-term vs long-term when the findings do. \
Use a **benefit vs. risk** or comparison table ONLY if the findings contain both sides.

## Population
Which patients / subgroups the evidence applies to (e.g. condition, age, phase, prior therapy) \
— and any it explicitly does not.

## Evidence quality
Characterize the strength of the cited evidence using the evidence pyramid \
(guideline / systematic review > randomized trial > observational > case report; and for \
trials, completed-with-results > phase 3 > earlier phase). Say what you relied on.

## Not addressed
Briefly, what the question asked that the retrieved evidence does NOT cover. State this as an \
evidence GAP, not a clinical inference.

Keep prose tight and scannable. Do not add a "medical advice" disclaimer beyond noting, when \
relevant, that findings are research evidence, not individualized advice.

HIGHLIGHTS — to aid rapid clinical reading, mark the few most important spans with these inline \
markers. Use them SPARINGLY (only spans that truly carry weight — a few words, rarely a whole \
sentence). Every opening marker MUST have its matching close. Do not mark citations [n].
- [[F]]…[[/F]] LOAD-BEARING FACT: the specific finding the answer hinges on — a dose, an outcome, \
an efficacy or safety figure, an adverse effect, enrollment, or a phase/status.
- [[R]]…[[/R]] CRITICAL REASONING: an evidence-strength judgment or the inference connecting facts \
— e.g. why one line of evidence outranks another, or a "designed to test" vs "found" distinction.
- [[K]]…[[/K]] KEY CONTEXT: the population, subgroup, timeframe, condition, or caveat that scopes \
a claim and must not be overlooked."""


# CLINICAL-SYNTHESIS variant (flag NOESIS_CLINICAL_SYNTHESIS, default OFF — Rule 20 A/B seam).
# SAME six adaptive sections as MEDICAL_ANSWER_FORMAT — deliberately NO new headings (a fixed
# template would pressure the model to fabricate to fill sections a given question can't support,
# breaking the provenance gate; the panel rejected that). It only SHARPENS in-section discipline:
#   #1 scope-up-front · #3 registry=protocol-not-efficacy · #4a state consensus once (no citation
#   stacking) · #5 preserve the specific figure · #6 surrogate≠clinical endpoint · #7 no vague hype.
# Everything requiring data we don't hold (effect sizes beyond abstracts, off-label status,
# contraindication tables, mechanism detail) stays a retrieval/sourcing roadmap item — the prompt
# never asks the model to manufacture it. Kept as a SEPARATE constant so the OFF path is byte-identical.
MEDICAL_CLINICAL_SYNTHESIS_FORMAT = """\
Format the answer as Markdown for a clinical audience. Include a section ONLY IF the \
verified findings above contain information to support it — OMIT any section you cannot \
ground in the findings; never infer or add outside knowledge to fill a heading. Every \
factual sentence, bullet, and table cell must carry an inline [n] citation to a finding. \
Sharpen, do not pad — a shorter, denser answer is better than a longer one.

Use these sections, in this order, where supported:

## Bottom line
One or two sentences that directly answer the question, with [n] citations. Scope the answer to the \
population, condition, intervention, comparator, setting, and timeframe the findings actually cover \
— never imply a broader scope than the evidence supports.

## Efficacy
What the evidence shows about effectiveness / outcomes. Preserve the SPECIFIC reported figure \
(effect size, % change, absolute number, CI, timepoint, adherence/discontinuation rate) whenever a \
finding gives one — never restate a number as a vague qualitative claim. Name the measured endpoint, \
and do NOT translate a surrogate outcome (a lab value, a scale/index) into a clinical outcome (event \
rate, mortality) unless a finding states that clinical outcome. When several findings agree, state the \
point ONCE with its strongest citation — do not stack repeated citations on one consensus claim. \
Bullets or a short table when the findings compare options or report figures.

## Safety & adverse effects
Reported adverse effects and risks. Distinguish short-term vs long-term when the findings do. \
Use a **benefit vs. risk** or comparison table ONLY if the findings contain both sides.

## Population
Which patients / subgroups the evidence applies to (e.g. condition, age, phase, prior therapy) \
— and any it explicitly does not.

## Evidence quality
Characterize the strength of the cited evidence using the evidence pyramid \
(guideline / systematic review > randomized trial > observational > case report; and for \
trials, completed-with-results > phase 3 > earlier phase). Treat trial-registry entries \
(ClinicalTrials.gov) as PROTOCOL-LEVEL / design intent — NOT efficacy evidence — unless posted \
results are present. Avoid vague status words like "emerging" or "promising"; say precisely what the \
finding supports. Say what you relied on.

## Not addressed
Briefly, what the question asked that the retrieved evidence does NOT cover. State this as an \
evidence GAP, not a clinical inference.

Keep prose tight and scannable. Do not add a "medical advice" disclaimer beyond noting, when \
relevant, that findings are research evidence, not individualized advice.

HIGHLIGHTS — to aid rapid clinical reading, mark the few most important spans with these inline \
markers. Use them SPARINGLY (only spans that truly carry weight — a few words, rarely a whole \
sentence). Every opening marker MUST have its matching close. Do not mark citations [n].
- [[F]]…[[/F]] LOAD-BEARING FACT: the specific finding the answer hinges on — a dose, an outcome, \
an efficacy or safety figure, an adverse effect, enrollment, or a phase/status.
- [[R]]…[[/R]] CRITICAL REASONING: an evidence-strength judgment or the inference connecting facts \
— e.g. why one line of evidence outranks another, or a "designed to test" vs "found" distinction.
- [[K]]…[[/K]] KEY CONTEXT: the population, subgroup, timeframe, condition, or caveat that scopes \
a claim and must not be overlooked."""


# PATIENT-audience variant (flag NOESIS_PATIENT_MODE, default OFF — Rule 20 A/B seam). Selected per
# request when the asker chooses "Patient" instead of the default "Clinician". It composes the answer
# for a PATIENT directly from the SAME span-verified findings (identical retrieval + provenance gate),
# so it changes only HOW the grounded facts are explained, never WHICH facts. The safety scaffolding of
# the clinician format (efficacy/safety/population/evidence-quality/what-is-NOT-shown) is preserved as
# plain-language REQUIREMENTS, not clinical headings — because "explain simply" is exactly the
# instruction most likely to drop a caveat, round away a number, or soften a risk, and the span gate
# CANNOT catch an omission (it only checks that emitted quotes exist). Inline [n] is mandated as
# forcefully as the clinician format so evidence stays traceable and the compose ref-check never trips.
MEDICAL_PATIENT_FORMAT = """\
Write the answer for a PATIENT — a thoughtful person with no medical training — in plain, warm, \
everyday language. You are the same clinician who reviewed the evidence, now explaining it to your \
patient so they genuinely understand their issue and what the evidence says about the options, \
investigations, or next steps. Use ONLY the verified findings above; do not add any fact, number, \
drug, outcome, or reassurance that is not in them.

NON-NEGOTIABLE accuracy rules (a simpler answer must never become a less accurate one):
- Keep EVERY number, dose, rate, percentage, and timeframe exactly as a finding states it — never \
round it away or replace it with a vague word ("often", "a lot", "usually") when the finding gives a \
figure.
- Preserve ALL uncertainty and everything the evidence does NOT show. If the findings don't answer \
part of the question, say so plainly — do not fill the gap with general knowledge or optimism.
- Do NOT reassure, promise, or downplay a risk beyond what the findings actually say. Report the \
reported harms and side effects, not just the benefits.
- This is general understanding of the research evidence, NOT personal medical advice. Gently remind \
the reader to discuss their own situation with their own doctor.
- Every factual sentence must still carry an inline [n] citation to the finding it comes from (so it \
stays checkable). Do not stack repeated [n] on one point; cite once with the strongest source.

How to make it understandable (structure ADAPTIVELY — use only what the findings support; short, \
clear paragraphs or simple points, plain sentences, no clinical section headings):
- Start with the bottom line in one or two plain sentences that directly answer the question [n].
- Explain what the evidence shows about the options / solution / investigation, and what it means for \
someone in this situation — in everyday terms [n]. The FIRST time an unavoidable medical term appears, \
explain it in a few plain words (e.g. "an infarct — an area of tissue damaged by loss of blood flow").
- Be honest about the side effects or risks the evidence reports, and about how strong or limited the \
evidence is (e.g. "this comes from a single small study" or "this is early research"), in words a \
non-expert follows [n].
- Say plainly what the evidence does NOT cover for this question, so the reader knows the limits.
- Close with a brief, non-alarming reminder to talk it through with their own doctor.

Keep it warm, clear, and concise. Do not use the [[F]]/[[R]]/[[K]] highlight markers — they are for \
the clinician view, not patients."""


# VISUALIZATION guidance (flag NOESIS_ANSWER_VISUALS, default OFF — Rule 20). APPENDED to the active
# compose directive to push the answer toward structures that speed consumption — comparison tables,
# ranked options, pros/cons — but STRICTLY from the verified findings: the compose step still sees only
# span-verified findings and may not add a value, row, column, or ranking a finding doesn't support
# (Rule 6 — never fabricate structure to look complete). Markdown-native only (tables/lists render in
# the UI); true charts/figures need front-end charting and are deferred.
MEDICAL_VISUAL_GUIDANCE = """\
VISUAL STRUCTURE — organize the answer so it is FAST to consume, using ONLY the verified findings; \
never invent a value, row, column, or rank to complete a structure, and keep every [n] citation and \
every specific figure (%, dose, CI, n, timepoint) intact in the cell/line:
- COMPARISON → TABLE. When the findings compare options/drugs/interventions/strategies across shared \
attributes (efficacy, dose, safety, population, evidence strength), present a Markdown table: one row \
per option, one column per attribute the findings actually report — OMIT any column no finding supports.
- "WHICH IS BEST / FIRST-LINE" or an implied ORDER (line of therapy, evidence strength, effect size) → \
a RANKED list (1., 2., 3.) with the basis for the order stated and cited. Do NOT rank if the findings \
don't establish an order — say so instead.
- WEIGHING ONE OPTION → a concise PROS vs CONS (benefits vs risks/limitations), only when the findings \
contain BOTH sides.
- Prefer a table or ranked list over a long paragraph whenever the findings support it — but a correct, \
citation-grounded paragraph beats a padded or half-empty table. Structure serves clarity, not decoration."""


# REASONING READ (flag NOESIS_REASONING_READ, default OFF — Rule 20). Appended to the compose directive.
# Adds a SEPARATE, typed INTERPRETATION layer on top of the grounded prose answer (factra's "Executive
# Read" discipline): the prose reports the span-verified FACTS; the interpretation layer reasons ABOUT
# them — what conflicts, what's missing, what's assumed, what follows, what would change the answer —
# plus a three-dimension confidence read. Every item is validated in code: it must rest on ≥1 cited
# finding and may contain NO number/dose/date/% not already in those findings (a fabricated inference
# is dropped before it ships). This gives editorial + causal intelligence WITHOUT loosening grounding.
MEDICAL_REASONING_FORMAT = """\
REASONING READ (`interpretation` field + `confidence` field) — in ADDITION to the prose answer, produce a \
short, high-signal layer of INTERPRETATION about the evidence. The prose answer states the facts; this \
layer reasons about them. It is for a clinician deciding how much to trust and act on the evidence.

STRICT SEPARATION — facts vs interpretation:
- The prose `answer` carries the FACTS (with [n] citations). The `interpretation` layer carries \
JUDGMENTS about those facts. Do NOT restate facts here, and do NOT put any new number, dose, %, date, or \
figure in an interpretation item that is not already in the findings it rests on — interpretation adds \
MEANING, never new data. (Items that introduce an ungrounded figure are dropped automatically.)

Emit 2–5 `interpretation` items, each with: `text` (one or two tight sentences), `kind` (one of the five \
below), and `basis_findings` (the 1-based finding numbers it rests on — REQUIRED; an item with no valid \
basis is dropped). Only include items that genuinely add insight — fewer, sharper items beat padding.
- `tension` — the findings CONFLICT or point different ways (different effect sizes, opposite \
conclusions, a trial vs a guideline). Name both sides and what the conflict is; do NOT silently average \
them away. Reconcile where the evidence lets you (e.g. different populations/endpoints explain the gap).
- `gap` — a decision-relevant thing the evidence does NOT establish (no head-to-head, no long-term data, \
no data in the asked population, surrogate endpoint only). This is what's MISSING, stated as a limit.
- `assumption` — an inference the answer leans on that the findings don't fully prove (e.g. a surrogate \
marker will translate to a clinical outcome; results in one population transfer to another).
- `implication` — what the evidence, taken together, actually MEANS for the question — the "so what". \
Calibrate causal language to the design: association/observational ≠ causation; a registered trial's \
intent ≠ a demonstrated effect. Say "associated with", not "causes", unless a finding supports causation.
- `what_would_change_this` — the specific new evidence that would move the answer (a completed RCT, a \
head-to-head, long-term follow-up). Names the fragility of the current read.

`confidence` — a three-dimension read, each with a `level` (high | moderate | low | unknown) and a \
one-line `rationale` grounded in the CHARACTER of the evidence (how many studies, what tier, how \
consistent, how directly they measure the outcome). Do NOT invent counts not supported by the findings:
- `factual` — how solid are the reported facts themselves (study tier/consistency; a single small \
observational study → low; concordant RCTs/guideline → high).
- `causal` — how well the evidence supports a CAUSAL reading vs mere association (RCT → higher; \
cross-sectional/registry → low).
- `generalization` — how well it transfers beyond the studied population/setting/timeframe to the \
question as asked (narrow eligibility or one setting → low).

NEUTRALITY — this is research synthesis, NOT medical advice. Do NOT recommend, prescribe, or tell the \
reader what to do; characterize the evidence and its limits so the clinician decides. No new facts, no \
hype, no reassurance beyond what the findings state."""


# CHART emission (flag NOESIS_ANSWER_CHARTS, default OFF — Rule 20). Appended to the compose directive.
# Every plotted number is validated in code (must appear verbatim in its cited finding) before it
# renders — an ungrounded number drops the whole chart. A VISUAL of grounded numbers, never new data.
MEDICAL_CHART_GUIDANCE = """\
CHART (optional, `charts` field) — add a chart ONLY when it reveals a pattern that is genuinely HARD to \
grasp from the prose or a table: a TRADE-OFF, a DISTRIBUTION/SPREAD, or effect sizes whose CONFIDENCE \
INTERVALS overlap or separate. Do NOT chart 2–3 values a table already shows plainly — a needless chart \
is worse than none. If nothing qualifies, leave `charts` empty. Pick the kind that carries the insight:

- `kind:"interval"` (a forest plot — the MOST valuable when available): a point estimate WITH its \
confidence interval / range per option — e.g. hazard/odds/risk ratios with 95% CI across trials, or an \
effect size with CI. This shows at a glance whether intervals cross a threshold or each other, which \
prose buries. Each bar: `label`, `value` (+ `value_str`), `low` (+ `low_str`), `high` (+ `high_str`), \
`finding`.
- `kind:"grouped_bar"` (a trade-off): 2+ SERIES per option — e.g. BENEFIT vs RISK (response rate vs \
serious-adverse-event rate) or the same outcome at multiple timepoints, across options. Each bar: \
`label` (option), `series` (e.g. "Response" / "Serious AE"), `value` (+ `value_str`), `finding`.
- `kind:"bar"` (only if there are MANY options, ~4+, where the ranking/spread itself is the point): one \
`value` (+ `value_str`), `finding` per `label`.

Hard rules — a wrong or misleading chart is a safety problem:
- Plot ONLY directly comparable numbers (same metric/outcome/timepoint, compatible population). NEVER \
mix units or unrelated populations on one axis. For grouped_bar, all bars in a SERIES are the same metric.
- Every `value_str` / `low_str` / `high_str` MUST be the figure COPIED EXACTLY as it appears in its \
cited `finding` (e.g. "0.78", "0.65", "0.94", "53%") — if any number is not verbatim in that finding, \
OMIT the chart. Set `unit` and a short `title`. Use 2–8 options. The prose/table is the answer; the \
chart only sharpens a hard-to-see pattern."""
