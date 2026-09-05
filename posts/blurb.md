# Noesis — blurb for partners and investors (2026-09-05)

## One line
Noesis is an evidence-grounded clinical research engine: a clinician asks a real question and gets a decision-shaped answer in which every claim and number is verified against its source before it is shown.

## Short (≈70 words)
Noesis answers clinicians' questions from the evidence, not from a model's memory. It searches a curated corpus of 1.5 million passages (open-access literature, ClinicalTrials.gov, FDA labels and safety reports, CDC, society guidelines) plus the live literature, drafts an answer, and then verifies every claim against the exact passage it came from. Anything it cannot verify is dropped, not softened. The result is an answer a clinician can defend.

## Standard (≈220 words)
Clinicians will not act on an AI answer they cannot defend. The problem with today's medical LLMs is not their average accuracy; it is their failure mode: a fluent, confident number that no source supports, or a real quote attached to the wrong trial. Noesis is built around that failure mode.

Noesis is a research engine, not a chatbot. For each question it retrieves from a curated corpus of 1.5 million evidence passages (Europe PMC and PubMed open-access literature, ClinicalTrials.gov, FDA DailyMed labels and FAERS safety reports, CDC, and a registry of society guidelines) together with the live literature. It reasons over what it finds, then passes every claim through three independent gates before writing: the quoted passage must physically exist in the source, it must actually support the claim, and it must be about the right subject. Claims that fail are removed. When the evidence does not settle a question, the answer says so.

The output is shaped for the question, not forced into a template: a decision plan for a case, a differential for an undifferentiated presentation, a head-to-head for a comparison, an explainer for a general question, a dated change log for "what's new". Every line carries a citation that opens the source passage. Answers arrive in about ninety seconds.

Under the medical product is a domain-agnostic kernel: ingestion, corpus, hybrid retrieval, verification, and synthesis carry no medical vocabulary. Medicine is a plug-in. Legal, regulatory, and financial research are the same engine with a different plug-in.

Noesis is live today with clinician accounts, private per-user history, and an evaluation harness that measures faithfulness and appropriate abstention on held-out questions.

## Notes for whoever sends it
- Every claim above is verifiable in the repo or in prod today. No user counts or revenue claims are included; add them only with real numbers.
- The competitive framing (versus point-of-care lookup incumbents) is in learnings/competitive-landscape.md; the differentiator to lead with is faithfulness and honest abstention, not distribution.
