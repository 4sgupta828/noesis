# Noesis — US Launch (Legal/Healthcare) + GTM & Monetization Plan

> **Disclaimer.** This is a strategy/orientation document, **not legal or financial advice**.
> Every regulatory point below must be confirmed with **healthcare/FDA regulatory counsel**
> before acting. Market figures are estimates as of early 2026 and will move.

Noesis is an evidence-grounded medical research platform for clinicians (grounded, cited
answers + a multi-specialist "Ask Panel"). The nearest comparable is **OpenEvidence**
(free to verified clinicians, pharma-ad funded, reportedly valued in the multi-billions);
the incumbent reference tool is **UpToDate** (Wolters Kluwer, subscription/site-license).

---

## Part 1 — Launching in the US (legal / healthcare)

### 1.1 The dominant question: are we a "medical device"?
FDA regulates **Software as a Medical Device (SaMD)**. The entire strategy is to stay on the
**non-device Clinical Decision Support (CDS)** side of the line.

Under the **21st Century Cures Act §520(o)(1)(E)** and FDA's **2022 final CDS guidance**,
software is **non-device CDS** (no FDA clearance) only if it meets **all four** criteria:

1. **Not** analyzing images, signals, or patterns *from a medical device* (ECG, scan, pathology).
2. Displays/analyzes **medical information** (guidelines, literature, labs).
3. Provides **recommendations to a healthcare professional** — **not** directly to a patient.
4. Lets the HCP **independently review the basis** — sources/reasoning shown, so the clinician
   is not relying *primarily* on the tool.

**Noesis is architecturally aligned with prong 4** — every claim carries a verbatim-verified
citation and the evidence is surfaced. This "independent review" property is the defensible
non-device posture. **Preserve it as a hard product invariant.**

### 1.2 Where our regulatory risk concentrates (review these with counsel specifically)
- **Ask-Panel.** Reading a *specific patient's case* and emitting a **treatment recommendation**
  drifts toward patient-specific CDS. Likely still non-device *if* it keeps citing evidence and
  frames output as evidence synthesis for clinician review — but this is the exact boundary FDA
  scrutinizes. **Get a written device-status opinion on the panel.**
- **Image / vision feature.** Interpreting an uploaded **medical image** (scan/ECG/photo) can
  trip prong 1 → **device**. Analyzing an uploaded *document's text* is fine; *interpreting an
  image* is device territory. Scope/position carefully.
- **Patient-facing anything** (prong 3) changes the analysis entirely → **keep it HCP-only.**

If we ever cross into "device": path is a **510(k)** (predicate-based) or **De Novo** (novel
type) — months-to-year+, real cost.

### 1.3 The rest of the compliance stack
- **HIPAA / PHI.** Clinicians *will* paste identifiable text. Need: security program (encryption,
  access controls, audit logs), **Business Associate Agreements (BAAs)** with covered
  entities/customers, breach-notification process, and likely **SOC 2 Type II** to sell to
  hospitals. The no-PII consent gate reduces but does not eliminate exposure.
- **Practice of medicine / liability.** Position explicitly as a **clinician decision-support /
  reference tool, not medical advice**; clear **ToS + disclaimers**; **product-liability / tech
  E&O / media-liability insurance**. Grounding discipline (no fabricated claims) is also the best
  liability defense — a wrong *cited* answer ≠ a confident hallucination.
- **FTC / advertising.** No unsubstantiated accuracy/"physician-grade"/diagnostic/outcome claims.
  Internal eval numbers are for engineering, not marketing copy.
- **State law.** CCPA/CPRA + the growing state privacy patchwork; some states regulate AI in
  healthcare. Corporate formation, clinician-verification (gate access to **verified US HCPs** —
  supports the HCP-only, non-device posture).

### 1.4 Practical sequence
1. **Regulatory counsel first** — device-status determination on Noesis *and specifically the
   Ask-Panel + image features*. Load-bearing step; everything else follows.
2. **Lock the non-device posture** — HCP-only access + clinician verification, citations always
   visible, framing as synthesis-for-review, no patient-facing mode, careful image scoping.
3. **Privacy/security foundation** — HIPAA program, BAA template, start SOC 2.
4. **Legal wrapper** — ToS, disclaimers, privacy policy, insurance.
5. **Marketing review** — all claims vetted against FTC.

### 1.5 Bottom line
OpenEvidence operates at scale without FDA clearance because it's a **cited, HCP-only evidence
tool where the clinician independently reviews the basis** — non-device CDS. Noesis fits that
mold. The two things to watch with counsel: **the panel's patient-specific recommendations** and
**the image-analysis feature**.

---

## Part 2 — Monetization, valuation, and GTM

### 2.1 What actually has value
The grounded-RAG + panel **technology is not the moat** — it's replicable. Value = **distribution
+ clinician trust + engagement + proprietary data/content + regulatory posture + integration
relationships.** "How much can I sell for" is almost entirely a function of **traction**, not code.

### 2.2 Pricing by segment (what the market bears)
| Segment | Realistic price | Reality check |
|---|---|---|
| **Individual clinicians** | $20–50/mo ($240–600/yr) | UpToDate's ceiling — hard to convert (institution-pays norm; OpenEvidence free). Weak standalone unless huge volume. |
| **Institutions** (health systems, AMCs) | ~$10k–$500k+/yr (per-seat or enterprise) | Durable B2B money. They pay for **provenance, auditability, security, data-control** — which Noesis's grounding + tenant isolation support. |
| **Pharma / life-sciences med-affairs** | $50k–$1M+/yr enterprise | High willingness to pay, **far less crowded** than the clinician race. MSLs/med-affairs need evidence synthesis. |
| **API / "grounding-as-a-service"** | usage-based ($/query) or platform fee | Sell the engine to EHRs, digital-health apps, payers. |

### 2.3 What the company/asset could sell for (traction-dependent)
- **Tech + no users:** acquihire / strategic tech value — low single-digit **$millions**.
- **Real engagement or early enterprise/pharma revenue:** health-SaaS multiples (~**5–15× ARR**,
  higher if the AI story is hot), or a **strategic premium** from an incumbent.
- **Likely acquirers:** Wolters Kluwer (UpToDate), Elsevier (ClinicalKey), an EHR (Epic /
  Oracle-Cerner), a pharma, or a larger digital-health player. Realistic exit for a small team =
  **acqui-hire / strategic acquisition**, not an IPO race.

### 2.4 GTM that makes sense (don't fight OpenEvidence head-on)
We will **not out-fund** OpenEvidence in the free-clinician, ad-supported game (needs capital for
user acquisition + a pharma ad-sales org). Pick a wedge:

1. **Own a niche where we're demonstrably better.** The **multi-specialist Ask-Panel** is a real
   differentiator on **complex, multi-system cases**. Lead with "the panel for hard cases," or go
   deep in one specialty. Depth beats breadth against a generalist incumbent.
2. **Sell to institutions/pharma, not individuals.** A private, **tenant-isolated, fully-auditable,
   grounded** tool is something a health system or pharma med-affairs team will pay for and
   OpenEvidence's ad model can't cleanly offer (they'd be showing pharma ads to your clinicians).
   Cleanest revenue **and** cleanest regulatory story.
3. **API / embed** — license the grounded-answer engine to companies that need provenance they
   can't build. Lower-glamour, real revenue, defensible.

### 2.5 Recommendation
- **Don't** try to be OpenEvidence. **Do** be *"the auditable, panel-driven evidence engine for
  institutions and pharma."*
- **Monetize B2B first** (institution + pharma pilots) — real willingness-to-pay, and where our
  architecture (grounding, tenancy, panel) is a genuine advantage.
- **Optimize for a strategic acquisition,** not a funding war.
- The single most value-moving next step is **evidence of engaged users or a paying pilot** — that
  moves valuation more than anything in the codebase.

---

## Immediate next actions
- [ ] Engage healthcare/FDA regulatory counsel for a device-status determination (incl. panel + image).
- [ ] Write the "non-device CDS posture" memo (HCP-only, citations-always-visible, no patient mode).
- [ ] Draft ToS + disclaimers + privacy policy; get liability/E&O insurance quotes.
- [ ] Stand up the HIPAA program + BAA template; scope SOC 2.
- [ ] Build a 1-page institutional/pharma pitch leading with the panel + auditability.
- [ ] Line up 2–3 lighthouse pilots (a health system's specialty service line; a pharma med-affairs team).
