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
