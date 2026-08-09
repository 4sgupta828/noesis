"""Complementary & integrative medicine — an OPT-IN per-question answer section (off by default).

Two opaque directives (Rule 18 — the LLM owns relevance/evidence judgments):
  - INTEGRATIVE_DIRECTIVE: appended to the compose directive ONLY when the user opted in for this
    question. Strict rules: proven-and-adopted only (evidence-tier labeled), interactions/safety named,
    complements-not-replaces standard care, one honest line when nothing proven exists.
  - INTEGRATIVE_QUERY_HINT: appended to the research question so retrieval actually looks for the
    complementary evidence (efficacy AND interaction/safety data).

The grounding invariant is untouched: every statement in the section still needs a span-verified quote,
so folklore without evidence cannot ship — the directive only shapes what is searched and how the
verified findings are presented.
"""

INTEGRATIVE_DIRECTIVE = """\
ADDITIONAL SECTION — the user EXPLICITLY opted in to complementary/integrative options for this question:

## Complementary & integrative approaches
Evidence-based complementary and integrative options relevant to THIS question (supplements/
nutraceuticals, mind-body practices, exercise & lifestyle protocols, acupuncture, adopted
traditional-medicine practices):
- Include ONLY approaches with meaningful supporting evidence among the findings — RCTs, systematic
  reviews, or guideline acknowledgment. For EACH, state the evidence strength plainly
  ("guideline-endorsed", "supported by RCTs/meta-analysis", "small/mixed evidence — uncertain").
- ALWAYS name interaction and safety concerns the findings support (e.g. supplement–drug
  interactions, bleeding risk, hepatotoxicity) — safety is part of the recommendation.
- These COMPLEMENT standard care, never replace it — say so where a reader could confuse the two.
- If the findings contain no complementary option with meaningful evidence for this question, write
  exactly ONE line saying so — do not pad the section with weak options.
The same grounding rules apply as everywhere: every statement cites [n] findings; nothing without
evidence in the findings.
"""

INTEGRATIVE_QUERY_HINT = (
    "Also investigate evidence-based complementary and integrative approaches relevant to this "
    "question — supplements, mind-body practices, exercise/lifestyle protocols, acupuncture, and "
    "adopted traditional-medicine practices — including their efficacy evidence (RCTs, systematic "
    "reviews, guideline positions) AND their interaction/safety data.")
