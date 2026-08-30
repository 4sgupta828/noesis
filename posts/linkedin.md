# Noesis — Can AI give a clinician an answer they can actually trust?

*A LinkedIn post. Repo: https://github.com/4sgupta828/noesis*

---

**The problem that keeps AI out of the exam room:**

A clinician doesn't need a confident paragraph. They need an answer they can *defend* — one where every claim and every number traces back to a primary source they can click and read. General-purpose chatbots fail this in the most dangerous way: they're fluent, they're often right, and when they're wrong they're indistinguishable from when they're right. In medicine, "usually correct, occasionally fabricated, never labeled" is not a product — it's a liability.

**What I explored: Noesis — an evidence-grounded research engine for clinical decision support.**

The design is the opposite of "an LLM that knows medicine." Noesis is a research engine that **finds** things, **quotes** them, **verifies** the quote physically exists in the source, and only *then* writes prose:

- Curated corpus + live web → hybrid retrieval → a research loop (search → look up → extract atoms → make claims) → a hard span-check gate.
- The one rule that defines the architecture: **a claim that can't be tied to a real retrieved passage does not ship.** Provenance is structural, not a suggestion.
- Answers are *decision-shaped* — not a wall of evidence, but a reasoned conclusion with citations you can click back to the exact passage.
- Crucially, the *engine* knows no medicine. It's a domain-agnostic kernel (ingest → corpus → retrieval → synthesis) with a medical vertical on top; a legal or financial vertical reuses the kernel untouched.

**What AI solves well:**
- Reading across dozens of sources and synthesizing a coherent, cited answer far faster than a human could.
- Reasoning to a *decision* rather than dumping search results — when it's forced to stay grounded.

**What AI does NOT solve — and where guardrails must be code:**
- Its own honesty. Left alone, a model will produce a plausible citation for a claim it invented. The verifier (does this exact quote exist in the cited block?) has to be deterministic and un-overridable.
- Currency and retraction. Whether a paper is current, superseded, or *retracted* is a data-pipeline problem, not something to trust the model to remember.

**What stays genuinely hard:**
- Evidence quality and conflict. Retrieval that returns a *real* but low-authority or outdated source is worse than no answer. Ranking by authority, recency, and study design — and being honest when the evidence conflicts — is the hard, unglamorous core.
- Attribution vs. correctness: a quote can physically exist and still be the wrong quote for the question. Provenance is necessary, never sufficient.
- Safety framing: "for informational use by professionals, verify against primary sources" isn't boilerplate — it's the responsible boundary of what this class of tool should claim.

**How to take it from here:**
- Held-out clinical eval gates before trusting any LLM feature; measure grounded correctness, not fluency.
- A corpus-currency subsystem (stamp, demote, exclude retractions) so the *data* stays trustworthy, not just the generation step.
- Kernel/vertical discipline so the same trustworthy engine can serve law, finance, policy.

**Products this could become:**
- Point-of-care evidence lookup that returns a cited, decision-shaped answer.
- A literature-surveillance tool that flags when new evidence changes a standing recommendation.
- A "grounded research engine" platform licensed per vertical.

**To go deeper, look up:** evidence-based medicine and GRADE, retrieval-augmented generation, hallucination in medical LLMs, Med-PaLM / HealthBench, and attributed QA (the AIS framework).

The takeaway: **in high-stakes domains, the winning architecture isn't a smarter model — it's a research engine that physically can't ship a claim it didn't ground.**

#HealthcareAI #ClinicalDecisionSupport #RAG #EvidenceBasedMedicine #TrustworthyAI #MedTech
