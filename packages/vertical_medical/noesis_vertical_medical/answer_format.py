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
relevant, that findings are research evidence, not individualized advice."""
