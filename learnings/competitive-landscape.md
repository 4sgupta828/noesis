# Competitive Landscape & Roadmap — Noesis vs leading AI medical platforms (2026-08-15)

Panel: Codex (GPT-5.5) + Gemini 3 Pro + a code-grounded subagent, plus current-web research
(WebSearch). All three converged; the code-grounded member CORRECTED two false premises the external
models held (see "The reframe"). This doc is the decision of record for what to build next.

## The 2026 field (who owns what)

| Segment | Leaders (2026) | Noesis stance |
|---|---|---|
| Point-of-care clinician lookup | **OpenEvidence** — 757k verified physicians, ~40% of US docs daily, 20M consults/mo, now embedded in Epic (Sutter, Mount Sinai) | Do NOT fight on distribution |
| Research / systematic review | Consensus (200M papers, "Consensus Meter"), Elicit (138M papers, SR screening, API launched Mar 2026) | Answer-first, not screening-first |
| Clinical reasoning / DDx | Glass Health (9-benchmark scorecard), Med-Gemini/AMIE (multimodal, MedQA 91%) | Panel+triage competes, with better provenance |
| Ambient scribing | Abridge, Nabla, Nuance/Dragon Copilot | STAY OUT (adjacent, incumbent-locked) |
| Patient-facing | Hippocratic AI | A feature, not the bet |

Two facts that frame everything:
1. **Faithfulness is the trust axis.** 44% of physicians name accuracy/hallucination as their #1 AI
   concern; medical hallucination rates run 33–38%; 45%+ of AI citations are fabricated. Noesis's hard
   span-gate + fail-safe abstain + (prod-on) misattribution judge attack this directly.
2. **HealthBench is now the standard scoreline.** OpenAI HealthBench (5,000 convos, 48k physician
   criteria) + HealthBench Professional (Apr 2026) is reported in every frontier release. Noesis has
   the slices WIRED but no PUBLISHED number.

## The reframe (what the code-grounded audit corrected)

The external panel assumed Noesis was a locked-garage demo. Prod reality (verified via Railway vars +
/config on 2026-08-15) says otherwise:
- `NOESIS_CLAIM_CONGRUENCE=1` + `NOESIS_EVIDENCE_IDENTITY=1` → the **misattribution gate (the strongest
  part of the moat) is ON**. Grounding = fail-closed verbatim span-gate PLUS an independent entailment/
  binding judge (`entail_claims`) that drops off-subject/not-entailed claims. Fabrication-proof by
  construction; misattribution-proofing live.
- `NOESIS_ACCOUNTS=1`, plus panel/pulse/graph/reasoning-read/patient-mode/People/charts/glossary/triage/
  modality — **all live in prod**. ~Everything is on.
- A held-out **eval harness already exists**: `evals/realworld/` (HealthBench, HealthBench-hard, K-QA,
  intake, India, stage-4 A/B slices) + calibrated LLM judge. Caveat: numeric/phrase gold is TODO
  (`eval_clinical_gold.py:23`, `eval_india_gold.py:19`) — ceiling is coverage/entailment, not verified
  numeric correctness yet.
- One surprising OFF flag: `country_scope_enabled=false` (matters for the India play).

So the moat is **built and live, just unproven and under-distributed.** The work is
**prove + publish + distribute + fill content**, NOT build-from-scratch.

Honest gaps that remain real: standard-of-care GUIDELINE full-text (corpus is trials/abstracts-heavy;
only KDIGO 2024 is full-text); no multimodal/imaging inference; no EHR/FHIR; 90s Q&A latency (DOA for
point-of-care lookup); licensed premium sources (Cochrane/NICE/NCCN/NEJM) = "planned, needs contracts."

## Prioritized roadmap (synthesized call)

1. **Prove it — run + PUBLISH the benchmark.** Harness exists → finish-and-publish, not build. Run
   HealthBench + a head-to-head vs OpenEvidence/ChatGPT/raw-Claude on **faithfulness + appropriate
   abstention** (Noesis's asymmetric strength; OpenEvidence drops <50% on subspecialty & only answers
   where evidence exists). Publish methodology + numbers. Sub-task: complete numeric-correctness gold.
2. **Close the standard-of-care content gap — public guideline full-text ingest.** ~80% of clinician
   queries are "what's the guideline for X"; corpus is abstracts-heavy (only KDIGO full-text). Ingest
   major PUBLIC guidelines (specialty societies, WHO/CDC/NICE/ICMR) via the existing connector seam.
   Converts research tool → clinical tool. Metric: management-question success rate. **← DOING FIRST
   (user directive 2026-08-15).**
3. **Frictionless verified-clinician front door + feedback loop.** Accounts/feedback are on but thin —
   make NPI/email-domain verification → free tier frictionless, server-side history, prominent per-answer
   flag/feedback wired to the improvement loop.
4. **India beachhead.** Geo-arbitrage; ICMR seam seeded; flip `country_scope` on; local guidelines/brands.
5. **Legibility + hardening.** One-screen "why you can trust this"; spot-verify the misattribution gate
   fires on sitagliptin-class cases in prod; de-ALPHA the panel.
6. **Fast point-of-care path.** A "quick answer" mode (the ~10s pre-loop overlap from task #59) so Noesis
   competes where OpenEvidence wins on speed. Keep deep-research mode separate.

## Do NOT
Ambient scribing (solved, incumbent-locked) · out-corpus UpToDate (can't hire 7,000 editors) · general
patient diagnostic chatbot (FDA device territory) · DICOM/imaging inference (FDA scrutiny, off-core).
Unanimous across panelists.

## Positioning
> "Frontier-grade clinical answers you can audit — every sentence backed by a quote we've verified, with
> the reasoning and confidence shown, tuned to your guidelines, not just US ones."

Head-to-head = OpenEvidence, but attack ASYMMETRICALLY (subspecialty/thin-evidence faithfulness + non-US
relevance), never their distribution. Highest-leverage move is a reliability/transparency POSTURE
(publish the benchmark, capture feedback, FDA-CDS "independently reviewable" framing), not a feature.

## #2 execution — guideline full-text ingest (started 2026-08-15)

Tranche 1 (5 flagship management guidelines) added to `GLOBAL_GUIDELINES` as full-text entries and
prod-ingested. Operational learnings (durable):
- **Society sites 403 datacenter/automated fetches** (NICE, CDC, WHO IRIS, GINA all block; WHO IRIS
  bitstream URL form is also broken). Prod ingest runs from Railway's datacenter IP, so hand-curated
  society PDFs are a fragile channel. GOLD's host is a permissive exception (fetched its 16 MB PDF fine).
- **Durable channel = Europe PMC OA mirror**: `https://europepmc.org/articles/PMC<id>?pdf=render`
  returns a real `application/pdf` from a datacenter IP for any OA guideline. Caveat: many flagship US
  guidelines (ACC/AHA, ESC, full ADA) are PAYWALLED → OA curation yields a strong subset, not everything.
- **content_type must be explicit**: `?pdf=render` URLs are PDFs but don't end in `.pdf`, so the
  suffix-only check in `GlobalGuidelinesConnector.list_documents` mis-routed them to the markdown path
  (raw PDF bytes → garbage). Fixed: entries carry `"content_type": "application/pdf"`.
- **Ingest = `POST /admin/corpus/ingest`** (admin token) with `{"connector":"global_guidelines","query":<cond>}`;
  the gap-queue worker (`apps/api/gap_queue.py`) drains it. Per-job status/errors at `GET /corpus/queue`;
  per-connector block counts at `GET /admin/ingest/sources`. Transient **Postgres deadlock**
  (AccessExclusiveLock during concurrent block insert) can fail a job — just re-queue; the retry succeeded.
- **The corpus is TENANT-SCOPED** (block PK `(tenant_id, document_id, block_id)`; retrieval filters by
  tenant). Admin ingest writes under `tenant_id="demo"`, so validate retrieval with `tenant_id:"demo"` —
  a fresh tenant sees no corpus and silently falls back to web (this bit me: my first validations used
  fresh tenants and wrongly looked like web-dominance).
- Result: all 5 landed (COPD 218 blocks, SLE 88, ACS 22, CAP 26, ADA-abridged diabetes 4). ADA abridged
  is thin (443 KB primary-care digest) — full ADA Standards is huge + partly paywalled; abridged is the
  OA proxy.
- SCALE PLAN: (a) more Europe PMC OA flagship guidelines (datacenter-safe), (b) a guideline-tagged
  europepmc query path for breadth, (c) WHO IRIS bitstream-UUID resolver, (d) licensed contracts for the
  paywalled flagships (Cochrane/NICE/NCCN) — the P3 "licensed" line.

Related: learnings/corpusfirst.md, learnings/evidencecontract.md, learnings/noesisindia.md,
learnings/realworldqa.md, learnings/improvementloop.md.
