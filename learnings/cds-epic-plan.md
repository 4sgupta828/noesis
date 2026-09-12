# Noesis CDS — the verification layer for clinical AI (EHR/Epic)

**Status: PANEL-REVIEWED v2 (2026-09-12).** An adjacent product built on the Noesis kernel. v1 framed
this as a point-of-care CDS that would "kill alert fatigue"; a four-lens red-team (Epic-integration
operator, CMIO/CDS-governance, FDA/regulatory counsel, healthcare-AI investor) **converged on rejecting
that framing** and reshaped the product. This v2 is the decision-of-record candidate. §12 records the
panel, the convergence, dissent, and exactly what changed. Grounded in three research streams (Noesis
architecture; Epic/EHR integration; CDS market + regulatory) plus `learnings/clinical-decision-ddx.md` and
`learnings/competitive-landscape.md`.

---

## 1. The thesis (revised by the panel)

CDS's defining failure is **unwarranted confidence surfaced at the wrong moment** — 90% DDI-alert override
(unimproved in a decade), the Epic Sepsis Model missing most cases at real-world AUC ~0.63, Watson Health's
unsafe recommendations, the Pieces/Texas-AG settlement over an undefendable accuracy claim. As GenAI floods
into the EHR (OpenEvidence embedded in Epic, UpToDate/Elsevier/EBSCO bolting on LLMs, Epic's own Cosmos/
CoMET and agents), **the number of confident, un-audited AI outputs a clinician sees is exploding — and no
one is checking whether the evidence actually supports them.** That is Noesis's exact moat: **typed
evidence, congruence-over-provenance (the sitagliptin fix), and a citation-first reviewable basis.**

The panel's correction: **do not sell this as another answer engine at the point of care** (that fights
free OpenEvidence on its own axis, is architecturally blocked from touching Epic's native alerts, and turns
abstention into dangerous silence). Sell it as **the verification / oversight layer over clinical AI** —
the instrument a CMIO and patient-safety office use to prove that the AI outputs already flowing through
their EHR (Epic's, OpenEvidence's, anyone's) rest on congruent, correctly-attributed evidence, with an
auditable basis that satisfies FDA Criterion 4 and ONC HTI-1. **The buyer has a P&L reason (claims,
M&M, regulatory exposure); the wedge is defensibility, not answer quality; and it is a wedge incumbents
structurally cannot copy without conceding their own outputs need policing.**

Trust is the scarce resource. Noesis is architected for it — but as *oversight*, not as one more voice.

---

## 2. What exists today (landscape)

### 2.1 The CDS failure mode
- **Alert fatigue is chronic.** DDI-alert override ~90% (95% CI 85–95%, 2024 meta-analysis); 46–96% across
  studies (JAMIA 2026); "no evidence of progress" over a decade. Low specificity/relevance → clinicians
  silence or reflexively dismiss even valid warnings.
- **Efficacy is real but narrow.** CDS reliably changes *clinician behavior* (~64% of studies, Garg 2005);
  hard *patient-outcome* benefit is condition-dependent and unproven in aggregate.
- **Critical nuance the panel surfaced:** the ~90%-override noise *is the mandated FDB/Medi-Span alerting*,
  which a third party **cannot touch** in Epic (see §2.4). "Reduce alert fatigue" is therefore not a
  third-party-addressable promise via CDS Hooks. The addressable problem is **trust and auditability of the
  AI outputs that are additive to that floor.**

### 2.2 Incumbents (content + plumbing moats)
UpToDate (WK; *UpToDate Expert AI* Sept 2025), DynaMed/DynaMedex (EBSCO; 2026 Best in KLAS), Elsevier
ClinicalKey AI (built *with* OpenEvidence), Micromedex/Merative (ex-IBM Watson). **Drug-alerting duopoly:**
First Databank (FDB) + WK Medi-Span power US EHR medication alerting via proprietary identifiers
(GCN_SEQNO, GPI) and ONC-mandated checking — **a licensed cost line for anyone reasoning over med alerts.**
Zynx (order sets), VisualDx, Isabel (dx).

### 2.3 AI-native entrants
- **Ambient scribing** (hottest, fastest ROI): Abridge ($5.3B, first in Epic's program), Nuance/Dragon
  Copilot (Microsoft), Nabla. **Epic is nativing it** (AI Charting GA Feb 2026). STAY OUT.
- **Evidence retrieval** (our comparable): **OpenEvidence** — free-to-clinician, ~$6B, ~40% of US docs
  daily, embedded in Epic. Atropos Health (real-world evidence).
- **Diagnostic/other:** Glass Health (quiet since 2023), Regard, Navina, Aidoc, Hippocratic AI.
- **Cautionary tales that make trust the axis:** Watson Health, Epic Sepsis Model, Pieces/Texas AG.
- **The whitespace:** every one of these *produces* AI outputs. **None verifies another's outputs for
  congruence.** That gap is the product.

### 2.4 Epic as the integration surface — and the corrections the panel forced
- **Standards:** CDS Hooks **2.0** (hooks `patient-view`, `order-select`, `order-sign`, `encounter-start`;
  cards = info / suggestion / app-link; feedback endpoint; prefetch). **SMART on FHIR** App Launch v2 on
  **FHIR R4** (OAuth2/OIDC, granular scopes, EHR-launch vs standalone, Backend Services). Epic has run CDS
  Hooks since 2018. Clinician mobile = **Haiku** (phone) / **Canto** (iPad); desktop = **Hyperdrive**.
  **MyChart is patient-facing** — not a clinician reach surface.
- **CORRECTION 1 (fatal to v1's S2):** Epic's native medication alerting (DDI, drug-allergy, dose,
  duplicate) is FDB/Medi-Span content executing *inside* Chronicles/Willow and surfaced as native alerts /
  BestPractice Advisories (BPAs). It is **not CDS-Hooks-driven, and there is no API for an external service
  to read, re-rank, suppress, or de-emphasize a native alert.** A CDS Hooks card renders *in addition*, in
  a different UI region. A third party can only *add* a card — never quiet the noise. Alert-tier changes
  are an Epic-side BPA-tuning + P&T governance project the *health system* owns, not something a vendor does.
- **CORRECTION 2:** **Toolbox is Epic-*granted*** (licensed API access gated by Epic + demonstrated
  mutual-client demand + fees, revocable) — not a certification you "pursue and pass" on a Q3–Q4 timeline.
  **Connection Hub** listing (~$500/yr) is table-stakes discoverability; every real *connection* requires
  the health system's own (backlogged) Epic team to register your client and run a HECVAT/security review.
  **Workshop (startup co-dev) is being sunset.**
- **CORRECTION 3:** Epic's CDS Hooks **feedback-endpoint support is partial**, and override reasons for
  *native* alerts live in Clarity/Caboodle — a per-site data-extract agreement, not an automatic pipe.
- **THE BUYER REFRAME:** *you do not sell TO Epic.* Epic is not acquisitive, builds native, and is
  **marketplace-plus-compete**. Epic gates the connection; **the health system is the buyer/sponsor.**
- **Native Epic AI to route around:** sepsis/deterioration models, SlicerDicer, **Cosmos** (~300M
  patients) + **CoMET**, and 2025 agents (Art/AI Charting, Penny, Emmie, Agent Factory).

### 2.5 Regulatory (the design *is* the strategy)
- **FDA CDS guidance (final Sept 2022, revised Jan 6 2026):** non-device only if it meets **all four**
  Cures Act §520(o)(1)(E) criteria. Crit 1–3 are satisfiable (discrete already-reported values, info
  exchanged among HCPs, supporting recommendations — the 2026 examples explicitly bless "prioritized lists
  of treatment/diagnostic options," so a **qualitative ranked differential is not per se a device**). **The
  fight is Criterion 4** (clinician can *independently review the basis* and does not rely *primarily* on
  the software). **The Jan 2026 revision moved automation bias INTO Criterion 4 and deleted the automatic
  exclusion for time-critical use** — so a sub-second `order-sign` card is now the express danger, because
  a card fast enough to not interrupt is a card the clinician *cannot actually review*.
- **AI/ML SaMD:** PCCP final guidance (Dec 2024) pre-authorizes model updates; GMLP principles.
- **ONC HTI-1 (compliance from Dec 31 2024):** LLM-generated ranked output is a **Predictive DSI → 31
  source attributes** (development, validation, fairness/bias, ongoing monitoring), **not** evidence-based
  (13). Citation-first does **not** downgrade this. The §170.315(b)(11) obligation lands on the certified
  EHR (Epic) until we embed via certified surfaces, then flows to us contractually.
- **Liability:** "learned intermediary" shields the vendor **only while purely informing** — controlling
  or suppressing the information field is closer to *driving* management and can defeat the shield
  (failure-to-warn).
- **HIPAA:** any PHI touch → Business Associate → **signed BAA before PHI flows**; the **LLM provider is a
  subcontractor BA** needing its own BAA + contractual zero-retention/no-train.
- **Enforcement (FTC / state-AG):** "never publish a hallucination rate" is necessary but **not
  sufficient** — "assurance," "verifiable," "would rather stay silent," "born compliant," and asserting
  "non-device" are all safety/performance claims needing competent-and-reliable substantiation (Pieces was
  a *performance*-claim case). "Rather stay silent than cry wolf" is a **false-negative safety claim** one
  missed event turns into a deceptive-assurance case.
- **Net:** a citation-first, congruence-checked system natively produces the *reviewable basis* Crit 4 and
  HTI-1 demand — but only if recommendations live where the basis can actually be reviewed (behind a click,
  not at sign), outputs stay **additive** (never suppress), and marketing is substantiated.

---

## 3. What Noesis already is (the reuse base)

- **Kernel/vertical split, CI-enforced.** `packages/kernel/` domain-blind (retrieval, ReAct, verification,
  synthesis, graph, currency); `packages/vertical_medical/` teaches medicine via typed `Protocol`
  contracts + a manifest.
- **The evidence contract ("evidence is typed, not text").** Gates that matter: **G1 span** (verbatim
  substring, always on, drop — provenance), **G2 entailment** (quote supports the claim, drop), **G3
  on_subject** (claim attributes content to the subject the source is actually about — the **sitagliptin
  fix**, drop), **G4 kind_ok** (assertion kind matches evidence kind — demote + annotate). Unbindable claim
  ⇒ *the claim does not exist*. **Congruence beats provenance** — the market whitespace no incumbent
  defends, and the literal engine of the verification product.
- **Pipeline:** scaffold/route → bounded ReAct (cost governor) → hybrid retrieval (Postgres tsvector +
  pgvector, RRF fusion, rerank, web-leg for gaps) → atoms→claims → evidence gates → rank/cap → compose
  ("use ONLY these findings") → post-checks → currency/Pulse.
- **Shipped, eval-gated differential engine** (`MEDICAL_DIFFERENTIAL_FORMAT`): ranked differential +
  workup + what-changes-management, **qualitative-likelihood only**, per-entry basis labeling. **Already
  treats "the patient's facts" as a labeled, non-citable ledger separate from retrieved (citable)
  findings** — the exact seam FHIR patient context plugs into. **Specialist panel** adds multi-lens
  synthesis.
- **Currency/Pulse** (span-verified change briefs on retractions/supersessions). **Grounded graph**
  (typed, span-verified edges). **Held-out eval harness** (faithfulness/abstention/coverage). All
  flag-gated, default OFF.
- **Stack:** Python 3.13, FastAPI, Postgres+pgvector, Anthropic default (`claude-sonnet-5`), Railway.

### The honest gaps (what this product needs that Noesis lacks)
No FHIR/CDS Hooks/SMART; no patient context; no write-back/alerting/event triggers; **~90s latency**
(fine for offline audit and behind-a-click, DOA for synchronous hooks); no HIPAA/BAA/PHI isolation/audit
beyond a generic `tenant_id`; **prose-layer verification thinner than the claim layer** (structured/atomic
outputs ride the no-new-facts validator; prefer structured outputs at the point of care).

---

## 4. The product (reshaped by the panel)

Positioning: **"The verification layer for clinical AI — an auditable, congruence-checked evidence basis
your safety office can defend."** Sequenced hardest-last, not hardest-first. The core asset (congruence +
typed evidence) is applied first as *oversight of other AI*, then earns the right to inform at the point of
care.

### P0 — Retrospective Congruence Auditor (the beachhead — ships first) ★
An **offline, batch** service that audits a health system's *existing* clinical-AI / CDS recommendation
logs and AI-generated note text for **sitagliptin-class failures**: evidence attributed to the wrong
subject/kind, claims with no congruent support, superseded/retracted guidance. Runs the span/entailment/
on_subject/kind gates over already-produced outputs.
- **Why it wins where v1 lost:** no real-time (90s latency is fine), no synchronous hook, no PHI-at-
  order-time, **no device line** (retrospective QA, not a point-of-care recommendation), **no suppression
  liability**, no Epic-architecture dependency. Works on a BAA-covered or de-identified extract.
- **Buyer:** patient-safety / quality / risk office + CMIO — a P&L for defensibility (M&M, claims, HTI-1
  evidence). **Proves the failure class is real and common on THEIR own data for ~single-digit-dollar
  compute** before anyone commits to a live build. This is the "$4 converts the debate into data" move
  from `diagnosticprocess.md`, applied commercially.
- **Deliverable:** a per-output congruence verdict + an aggregate safety-QA report + the audit trail. Sold
  as a safety-QA instrument, expandable to continuous monitoring of AI outputs.

### P1 — Evidence-on-demand, patient-contextualized (SMART app, `patient-view` app-link) — non-device
The real point-of-care surface (the proven OpenEvidence-shaped one), behind a **click**, 5–15s streamed —
where Criterion 4 is genuinely satisfiable. Contextualized to the patient via FHIR prefetch, riding the
differential engine's non-citable patient-facts ledger. **Options + per-entry basis, never a single
directive.** Gated by a **context-quality check** (see §5). This expands reach once P0 has earned trust.

### P2 — Additive congruence advisory (`order-select` CDS Hooks) — non-device by construction
The reshaped former "S2." **Purely additive, informational, high-specificity** net-new advisory that fires
*only* on congruent, patient-specific evidence — competing with the org's own BPA build **for a slot on
merit**, proven head-to-head as "the card they don't override." **It does NOT read, rank, reorder, or
suppress any native/FDB alert** (architecturally impossible and a device/liability line). **No directive
or likelihood verdict at the synchronous hook**; the recommendation and full basis live one tap away on
the P1 surface. Coverage is shown explicitly ("evaluated X, Y") — **silence is never rendered as
clearance** (see §5).

### P3 — Guideline-currency passive alerts (Pulse) — non-device, lowest risk
Passive inline notice with a span-verified change brief when a supersession/retraction touches a patient's
active problem/med. No interruption.

### X — Cross-cutting: the auditable basis + Predictive-DSI model card + feedback loop
Every surface exposes the reviewable basis (quote, source, subject, evidence kind, congruence note). We
ship the **full 31-attribute Predictive-DSI transparency artifact ("model card")** as a partner
deliverable (development, validation, fairness/bias, monitoring) — not a light "satisfies HTI-1" checkbox.
Feedback loop is built around **our own cards** (site override analytics is a separate Clarity engagement).

---

## 5. Two safety mechanics the panel required (non-negotiable)

1. **Silence is never clearance.** Abstention is safe for a *pull* engine (user asked, got "gap"); in a
   *push* surface, an absent card reads as reassurance → errors of omission = the Epic-Sepsis silent-miss
   failure inverted, and un-auditable. Rule: **always show coverage explicitly** ("evaluated A, B; NO basis
   found for C — this is not clearance"), keep mandated alerts fully visible, and distinguish "no concern
   found" from "we lacked the document." **Measure the false-negative / errors-of-omission rate against a
   clinician-adjudicated gold set — sensitivity, not just precision.**
2. **Context-quality gate for dirty FHIR.** FHIR problem lists/meds/allergies are often stale/incomplete
   and free-text is invisible. Grounding on wrong facts yields confidently-wrong *patient-specific* output
   — worse than a generic alert. Rule: check resource coverage/timestamps; if key context is missing/stale,
   **degrade to a population-level answer and say the context was incomplete** — never imply specificity we
   don't have. Validate FHIR completeness on a real target site's production data in Phase 0, not the
   sandbox.

---

## 6. Architecture — kernel-first, per the standing directive

**Litmus test:** a legal/regulatory vertical must reuse the surface by supplying its own manifest (a
"matter context" ledger, an "audit other legal-AI outputs" job) — so interop *mechanics* are kernel;
medical *mapping* is vertical.
- **Reuse as-is:** retrieval/fusion/rerank, ReAct + governor, the four gates, corpus + ingestion,
  currency/Pulse, graph, eval harness, differential engine, panel.
- **New kernel mechanics** (`packages/kernel/` or new `packages/interop/`): a **batch congruence-audit
  runner** (P0 — the first thing built, and mostly a new *driver* over existing gates); CDS Hooks 2.0
  service (cards/feedback/prefetch); SMART-on-FHIR R4 launch (OAuth2/OIDC, FHIR client); a generic
  **context-ledger** abstraction + the **context-quality gate**; a **precompute cache seam** (see §7);
  **PHI-at-rest** primitives (encryption, access control, retention limits, tamper-evident audit).
- **New medical vertical:** FHIR-resource→clinical-fact mapping; the congruence policy for "genuine,
  patient-specific concern"; guideline authority for currency; card templates + clinician copy.
- **New app surface** (`apps/cds` or extend `apps/api`): audit endpoints + hook endpoints + the SMART app
  UI — **mobile-friendly is mandatory** (Haiku/Canto; per repo CLAUDE.md).

**Compliance backbone (corrected):** the **evidence corpus stays PHI-free** (public/de-identified). Patient
context is PHI — and the panel corrected the v1 "ephemeral" claim: the **precompute cache, audit log, and
feedback store are PHI *at rest*.** Treat all three as encrypted, access-controlled, retention-limited PHI
under BAA. The LLM provider is a **subcontractor BA** requiring a BAA + contractual zero-retention/no-train
before any PHI enters a prompt. Drop the blanket "ephemeral" language.

---

## 7. Latency (only P1/P2 need it; P0 doesn't)

`order-sign` sync expectation is sub-second; ReAct is ~90s. Design:
- **P0 is offline** — no latency constraint at all (why it's the beachhead).
- **P1 runs behind a click** — 5–15s streamed is acceptable and is where recommendations live.
- **P2 synchronous card** returns fast from a **precomputed congruence cache** warmed on `patient-view`
  (retrieval + gate check, no ReAct). **Panel caveats to validate in Phase 0 on a real site:** Epic's
  support for firing `encounter-start` to external services is uneven; `patient-view` may fire only seconds
  before signing; many orgs won't enable external `order-sign` hooks at all. If the cache misses, **render
  explicit "not yet evaluated" — never stall and never imply clearance.**

---

## 8. Go-to-market — "selling to Epic," realistically

1. **Lead with P0 (offline auditor) to the patient-safety/risk/quality office + CMIO.** A buyer with a P&L,
   a surface with no integration/latency/device blockers, and a proof-on-their-own-data motion that closes
   fast and cheap. This is the wedge.
2. **Build P1/P2/P3 to open standards** (CDS Hooks 2.0 + SMART on FHIR R4) → multi-EHR (Epic, Oracle
   Health, athenahealth) — a hedge and a differentiator Epic's native models can't match.
3. **Connection Hub listing** (table stakes). **Decouple the business case from Toolbox** — make it work on
   Connection Hub + client-sponsored SMART/CDS Hooks alone; treat Toolbox as year-2+ Epic-granted upside,
   not a milestone. Budget the health system's own Epic-analyst time + HECVAT review as the real gate.
4. **The pitch to Epic (endorsement, not acquisition):** *"We verify the congruence of the AI outputs
   already flowing through your EHR — yours and third parties' — and hand your customers the auditable,
   Predictive-DSI-transparent basis they need for HTI-1 and their own safety governance. We're oversight
   that raises trust in the platform, additive to Cosmos/CoMET, never a competitor to them."*
5. **Assume Epic natives evidence lookup.** Defend on: verification-of-*others'*-outputs (which Epic can't
   do without policing itself), cross-EHR reach, and the safety/compliance buyer.
6. **Commercial:** sell P0 as safety-QA (subscription + per-audit) to the safety/risk office; P1/P2 per-
   site/enterprise to the health system. **Do NOT** adopt OpenEvidence's ad/pharma-funded model on a safety
   product (conflict optics are toxic). ACV benchmarks aren't reliably public — validate in discovery. Note
   the **FDB/Medi-Span license cost** if P2 ever reasons over med identifiers.

---

## 9. Phased roadmap

**Phase 0 — Validate & de-risk (wks 0–8, near-zero LLM spend).**
- **Regulatory:** written non-device opinion (513(g) or counsel memo) for P0/P1/P3 **and** the P2
  order-select boundary, citing the *Jan 2026 revised* guidance — **before** building P2, not after.
- **P0 proof-of-value:** run the batch congruence auditor over a design-partner's de-identified AI/CDS
  output logs; quantify the sitagliptin-class failure rate on their data. This is the sales artifact.
- **Discovery:** patient-safety/CMIO interviews; FHIR data-quality study on a real site's production charts
  (not sandbox); measure the true `patient-view`→`order-sign` interval and which hooks a real org fires to
  external services.
- **Standards spike:** CDS Hooks 2.0 + SMART launch against `fhir.epic.com` sandbox (free, structural).
- Deliverable: go/no-go + a signed design-partner LOI.

**Phase 1 — Ship P0 (offline auditor) commercially (Q1–Q2).** BAA + PHI-at-rest hardening + audit trail;
HITRUST/SOC2 track started. Land 1–2 paying safety-office customers. Extend the held-out harness with
audit-mode + false-negative/sensitivity metrics (eval before flip, per repo Rule).

**Phase 2 — P1 evidence-on-demand behind a click (Q2–Q3).** Context-ledger + FHIR ingestion + context-
quality gate; options-not-directive; multi-EHR; Connection Hub listing; Vendor Services technical/security
review.

**Phase 3 — P2 additive advisory + P3 currency + X model-card/feedback (Q3–Q4).** Precompute cache
(validated timing); additive-only, coverage-explicit; **prospective stepped-wedge pilot** measuring
override reduction **AND** no rise in missed alerts/adverse events; publish the *methodology* (not a
hallucination %); 31-attribute Predictive-DSI model card.

**Phase 4 — Scale (year 2).** Oracle Health/athenahealth; continuous (not just batch) AI-output monitoring;
payer prior-auth via **Da Vinci CRD** (runs on CDS Hooks); pursue Epic Toolbox if client demand materializes.

---

## 10. Metrics that matter
- **P0:** sitagliptin-class failure rate found in a customer's existing AI/CDS outputs (the sales metric);
  audit coverage.
- **Sensitivity / false-negative (errors-of-omission) rate** vs a clinician-adjudicated gold set — the
  metric the CMIO demanded; guards against "fire less → miss more."
- **Appropriate-abstention with explicit coverage** (never bare silence).
- **P2 prospective pilot:** override reduction **AND** non-inferior missed-alert/adverse-event rate.
- **P1:** time-to-decision, context-quality-gate hit rate.
- **Never** a published hallucination rate; qualify every claim to its substantiation file (§11).

---

## 11. Risks & mitigations
1. **Not a business / feature copied in a quarter (VC)** → wedge is verification-of-others'-AI + the
   safety/risk buyer + auditable basis, which incumbents can't copy without policing themselves; lead P0.
2. **Selling against free OpenEvidence (VC/CMIO)** → don't fight the lookup axis; P1 is expansion, not the
   wedge; sell oversight, not answers.
3. **Third party can't touch Epic native alerts (Epic op)** → P2 is additive-only, competes for a BPA slot
   on merit; kill all "rank/suppress" framing.
4. **Errors of omission masked as reassurance (CMIO) — the top safety risk** → silence-≠-clearance,
   explicit coverage, mandated alerts stay visible, measure sensitivity.
5. **Dirty FHIR → confidently-wrong specificity (CMIO)** → context-quality gate; degrade + disclose;
   validate on real site data.
6. **`order-sign` is likely-device; suppression defeats learned-intermediary (counsel)** → recommendations
   behind the click only; synchronous surface additive/informational; written opinion before P2.
7. **HTI-1 is a Predictive DSI, 31 attributes (counsel)** → build the full model card as a deliverable;
   don't market "HTI-1" as a light lift; obligation is Epic's until we embed.
8. **BAA/PHI-at-rest gaps (counsel)** → BAA + zero-retention with LLM provider; cache/audit/feedback = PHI
   at rest, encrypted/retention-limited; drop "ephemeral."
9. **Marketing overclaim (counsel)** → substantiation file per claim; never assert "non-device" pre-opinion;
   strike "assurance/rather-stay-silent/born-compliant"; qualify metrics to the pilot population.
10. **Toolbox not a milestone; feedback endpoint partial; FDB license cost (Epic op)** → decouple GTM from
    Toolbox; loop on our own cards; budget FDB license if P2 needs identifiers.
11. **Epic natives lookup** → verification-of-others + cross-EHR + safety buyer.
12. **Prose-layer weaker than claim-layer** → structured outputs at the point of care; harden prose gate
    before any synchronous copy.
13. **Corpus gaps (paywalled guidelines)** → OA-first + licensed contracts (`corpusfirst.md`); abstain with
    explicit coverage, never paper over.
14. **Capability/burn reality (VC)** → this is a company-scale build (FHIR, PHI compliance, HITRUST, EHR
    relationships) — but **P0 is shippable on the existing engine with no integration**, which is why it's
    the beachhead: it de-risks the raise before the heavy build.

---

## 12. Panel Review

**Panel (2026-09-12):** four independent expert lenses red-teaming the v1 draft — (a) Epic-integration
operator, (b) CMIO / CDS-governance chair, (c) FDA/regulatory counsel, (d) healthcare-AI investor. Method
mirrors `learnings/panelcontract.md` and the `competitive-landscape.md` panel: independent critiques →
convergence → dissent → what changed.

**Strong convergence (all four, independently) — v1 was wrong on its central bet:**
- **v1's headline surface — a CDS Hooks card that ranks/suppresses FDB/Medi-Span alerts to "kill alert
  fatigue" — is dead.** (a) architecturally impossible for a third party in Epic; (b) clinically unsafe and
  un-passable by patient-safety governance; (c) "driving management" + failure-to-warn liability at
  order-sign; (d) not a moat. → **Reframed to P2 (additive-only advisory); the wedge moved to P0.**
- **Lead with the offline/behind-a-click surfaces, not the synchronous safety-critical one.** Hardest-last.
- **Abstention-as-silence is a liability in a push context** (errors of omission = inverted Epic-Sepsis).
  → §5.1 silence-≠-clearance + sensitivity metric; the "rather stay silent than cry wolf" tagline is struck
  (counsel flagged it as a false-negative safety claim).
- **The durable, uncopyable wedge is verification/oversight of *other* clinical AI, sold to the
  safety/risk buyer with a P&L** — not a paid answer engine competing with free OpenEvidence. → New
  positioning (§1) + P0 beachhead (§4).

**What changed from v1 → v2 (concrete):**
- New **P0 Retrospective Congruence Auditor** as the beachhead (VC's "retrospective auditor" + repo's
  "$4 converts debate to data").
- v1 "S2 alert-fatigue killer" → **P2 additive-only advisory**, no ranking/suppression, recommendations
  behind the click.
- Added §5 (silence-≠-clearance; context-quality gate for dirty FHIR).
- Regulatory §2.5 rewritten: Jan 2026 automation-bias-into-Crit-4; per-surface device verdicts; **Predictive
  DSI = 31 attributes**; LLM-provider BAA; additive-only preserves learned-intermediary; substantiation file.
- Compliance backbone corrected: **cache/audit/feedback = PHI at rest**, "ephemeral" dropped.
- GTM: buyer = safety/risk office; **Toolbox decoupled** from the roadmap (Epic-granted, not earned);
  Connection Hub + client sponsorship carry the case; FDB license noted; feedback loop on our own cards.
- Roadmap resequenced hardest-last (P0 offline → P1 click → P2 sync).
- Metrics: added sensitivity/false-negative + P0 failure-rate; kept "no hallucination rate."

**Dissent / unresolved (carry forward):**
- The investor's stronger form — *"this is a company pivot, not a repo feature; the point-of-care surfaces
  may never be worth building"* — is only partly adopted. This plan keeps P1–P3 as an **earned expansion**
  behind P0; whether to ever build them is an explicit Phase-1 review gate, not a commitment.
- Whether P0's buyer (safety/risk office) has real budget for a *new* category is unproven — Phase-0
  discovery must confirm willingness-to-pay, not just pain.
- Market size for verification-of-AI is unquantified here; needs sizing before a raise.

**Verdict:** proceed to **Phase 0 only** — regulatory opinion + P0 proof-of-value on a design partner's
data + FHIR/hook reality-check on a real site — gated on a go/no-go before any heavy integration build.

---

# PART II — The India variant: a real-time prescription-safety CDSS (the stronger wedge)

**Status: DRAFT (2026-09-12), grounded in two India research streams (market/regulatory/EHR; drug-safety/
data/RWE) + `learnings/noesisindia.md`. Needs its own clinical + CDSCO-counsel panel before build.**
User direction: build a point-of-prescribing CDSS for India (greenfield), checking prescription
correctness, patient-adaptation, cross-comorbidity concurrency/interactions, and evidence-anchored
divergence — real-time, advisory, **not diagnosis**. Assume EHR/patient-data access is granted.

## II.1 Why India is a stronger wedge than the US play
- **It dissolves the US killer.** The US plan died on the fact that a third party cannot touch Epic's
  native FDB/Medi-Span alerting. India is **greenfield — there is no incumbent alerting layer to sit
  under; you BE the layer**, embedded via ABDM's national FHIR R4 rails (an India-wide SMART-on-FHIR
  analog: ABHA IDs, HIE-CM consent manager, HIP/HIU) or directly inside an EMR/HIS.
- **The pain is enormous and quantified** (the market rationale the US play lacked): >90% of antibiotic
  FDCs judged irrational; one OPD study found **98.9%** of prescriptions deviated from standard treatment;
  ~22% inpatient medication-error rate; 33.7% elderly polypharmacy — all feeding AMR.
- **Noesis already has India infrastructure built** (`noesisindia.md`, deployed dark): an FDC/strength-
  aware **abstaining brand→generic resolver**, CDSCO FDC-ban/approved lists + NLEM + MoHFW/ICMR treatment
  guidance as ranked evidence, Indian web domains, tier-aware country boost, per-user profiles + auth on
  the research route, an India eval slice. The prescription checker is an *extension* of this, not a cold
  start.
- **The core moat fits the market exactly.** The one competitor already shipping — HealthPlix's in-EMR DDI
  (14k+ doctors) — is "good enough," not India-localized or evidence-grounded. Global engines (Medi-Span/
  FDB/Micromedex) aren't localized to Indian brands/FDCs. Noesis's differentiator (every flag carries a
  congruent, cited, correctly-attributed basis; abstains when data/evidence won't support it) is what
  turns a checker from "another override" into a trusted second read.

## II.2 The regulatory 180° (the load-bearing finding)
- **India has NO US-style "non-device CDS" safe harbor.** CDSCO's **Draft Guidance on Medical Device
  Software (21 Oct 2025)**, IMDRF-aligned, explicitly names "standalone clinical decision support tools"
  and software that "synthesizes or interprets patient data" as **SaMD requiring a license.** There is no
  Cures-Act-§520(o) independent-review carve-out and no ONC-style transparency rule to lean on.
- So the US strategy inverts: **in India you embrace being a regulated device.** Prescription-checking
  that informs/drives management in serious situations plausibly lands **Class B–C (possibly C/D → central
  CDSCO licensing)** under Medical Device Rules 2017. This is a **moat (barrier to entry) and a cost/
  timeline**; AI/ML manufacturers must disclose training-set composition, bias, generalizability, and run
  post-market monitoring. **Exact class is the load-bearing unknown — get a CDSCO/counsel read in Phase 0
  before committing** (verify whether the Oct-2025 guidance is still draft or finalized).
- **Liability posture = advisory.** NMC/Telemedicine rules: only a registered practitioner prescribes and
  owns the decision. Keep the CDSS **advisory, clinician-retains-authority** (already Noesis's non-
  autonomous stance; eSanjeevani deploys advisory AI-CDSS at national scale). "Not diagnosis" helps
  liability but does **not** exempt it from SaMD licensing.

## II.3 DPDP Act 2023 — and the sharp edge on "learn from similar patients"
- DPDP Act 2023 + **DPDP Rules 2025 (notified 13 Nov 2025, phase-in to ~mid-2027)**: consent must be free/
  specific/informed; providers get limited care-exemptions from *verifiable* consent for delivering care;
  data-fiduciary duties, likely **Significant Data Fiduciary** status (India DPO, DPIA, independent audit).
  **Design for data residency in India.**
- **The population-learning feature is a distinct purpose.** You **cannot** re-use treatment data for model
  training under the care exemption — it needs its own lawful basis (explicit consent or robust
  de-identification). This gates the divergence/anomaly feature behind a consent/de-id pipeline —
  `noesisindia.md` already flags this ("real user cases … require a DPDP consent/de-identification
  pipeline, its own spec with its own panel review").

## II.4 The safety mechanic the India data forces: evidence-anchored divergence, never peer-conformity
**The validity trap (central risk).** Because guideline deviation is the *norm* in India (~99% in one
study; antibiotic/FDC overuse is majority behaviour), **peer-conformity is a broken oracle** — "diverges
from what similar patients get" frequently means "diverges from a bad majority," and a naïve peer-
comparison model would flag the *correct* minority prescription as the anomaly and **entrench irrational
prescribing.** Rule (non-negotiable): **every divergence flag resolves to a congruent guideline/evidence
citation** (NLEM, ICMR AMSP/AWaRe, STGs, WHO) — peer patterns may be used *only* for hypothesis generation
/ case-finding, never as the correctness signal. This is Noesis's standing "conformity ≠ correctness"
discipline applied directly (the sitagliptin lesson). Plus §5.1 (silence-≠-clearance) and §5.2 (context-
quality gate) carry over verbatim — and matter more here, since Indian chart completeness is the real
bottleneck even with access granted.

## II.5 Capability → feasibility map (the user's exact list)
1. **Prescription correctness** (drug/dose/route/freq) — feasible. Needs brand→molecule+strength+form
   normalization (Noesis resolver seed + build; the hard, defensible core given 60k–100k+ brands, FDC-
   heavy, no central DB) + NLEM/NFI dosing + guideline anchors.
2. **Patient-adaptation** (age/weight/renal/hepatic/pregnancy/allergy) — feasible where data exists; the
   differential engine's non-citable patient-facts ledger is the seam. **Hard dependency: Indian EHR
   completeness** — even with access, structured eGFR/weight/allergy are not safe to assume. Degrade
   gracefully ("cannot verify renal function → cannot confirm dose"), never assume normal.
3. **Cross-comorbidity concurrency / polypharmacy DDI** — feasible, but requires **licensing a global DDI
   *chemistry* database** (DrugBank/Lexicomp/FDB — no Indian equivalent exists; RxNorm interaction API
   discontinued 2024, DrugBank free checker retiring Mar 2026). Noesis adds India localization + the
   evidence-grounded, congruent rationale on top.
4. **Real-time feedback** — the **latency** problem, now core (not deferrable). Two-tier: **deterministic
   rule checks** (dose bounds, allergy, banned-FDC, DDI severity) fire **<1s** from structured data + the
   licensed DB, **no LLM**; the **evidence/reasoning layer** (guideline-appropriateness, the cited "why")
   runs asynchronously to enrich, or on-demand behind a tap. Never block prescribing on a reasoning
   round-trip.
5. **Rule out interactions** — same as (3).
6. **Learn from similar patients → flag divergence** — most novel, most valuable long-term, most fraught.
   Governed by II.4 (evidence-anchored only) + II.3 (DPDP consent/de-id). **Stage it last.**
7. **Not diagnosis** — keeps it advisory; does not change SaMD licensing.

## II.6 Go-to-market (India-specific)
- **Willingness-to-pay for standalone clinical software is weak** (HMS/EMR ~₹500–5,000/bed/user/mo,
  price-sensitive buyers). **Best path = OEM/embed as a component (API) into Indian EMR/HIS vendors**
  (Eka.care — ABDM-native; HealthPlix; KareXpert; Napier; Bahmni for public/NGO) who need differentiation
  — not direct-to-doctor. **Bundle into e-Rx/CPOE, not a standalone alert box.**
- Secondary buyers: large private chains (Apollo/Fortis/Max/Manipal — patient-safety + **NABH**
  accreditation angle, real budgets, long cycles); government/NHM/ABDM (huge scale, brutal procurement,
  lowest price); pharmacy chains (dispensing-side). **NABH + SaMD licensing become both moat and cost.**

## II.7 What Noesis reuses vs must build (India prescription CDSS)
- **Reuse:** the four evidence gates (span/entailment/on_subject/kind — the congruence engine that makes
  divergence safe), the patient-facts ledger seam, currency/Pulse (FDC-ban notifications = change events),
  the India-mode content/brand/boost/profile stack, the eval harness.
- **Build:** (a) a **licensed DDI database integration** + Indian product mapping onto it; (b) a
  **deterministic real-time safety-rules engine** (<1s, no-LLM) for dose/allergy/FDC/DDI; (c) the
  **brand→molecule+strength+form normalizer** hardened well past the current ~97-row v1 (the core moat);
  (d) **ABDM/FHIR R4 HIP-HIU integration** + consent-manager flow; (e) **DPDP data-residency + consent/
  de-id pipeline** (gates the divergence feature); (f) SaMD **quality system + licensing + post-market
  monitoring**; (g) the evidence-anchored divergence layer (last).

## II.8 Sequencing (India)
- **Phase 0 (de-risk):** CDSCO class determination + counsel opinion (load-bearing); DPDP/data-residency
  architecture; **license the DDI chemistry**; sign an **EMR-vendor design partner**; validate real EHR
  data completeness on their data (can we actually get eGFR/weight/allergy at prescribing time?).
- **Phase 1:** the **deterministic real-time safety core** (correctness + dosing + interactions + patient-
  adaptation with graceful degradation), evidence-grounded rationale, embedded in one EMR partner. SaMD
  licensing track started.
- **Phase 2:** the **guideline-appropriateness layer** (evidence-grounded "is this the right drug per
  NLEM/ICMR/AWaRe" — where the Noesis engine shines, congruent + cited).
- **Phase 3:** the **evidence-anchored divergence/anomaly layer** (DPDP-compliant, guideline-anchored,
  hypothesis-generation only).

## II.9 India risks (delta from Part I)
1. **SaMD licensing (Class B/C/D) is mandatory — no non-device escape** → embrace it as a moat; get the
   class read in Phase 0; build the quality system early.
2. **Validity trap** (peer-conformity is inverted in India) → evidence-anchored divergence only (II.4).
3. **DPDP on population learning** → consent/de-id pipeline + India residency; stage the feature last.
4. **Latency at prescribing** → deterministic <1s core, async reasoning (II.5#4).
5. **Indian EHR data completeness** (even with access) → graceful degradation, explicit "cannot verify".
6. **Licensed DDI-DB dependency + cost** (DrugBank/Lexicomp/FDB) → budget it; it's the interaction
   chemistry we don't own.
7. **Weak WTP / "good-enough" incumbent (HealthPlix)** → OEM-embed + evidence-grounded differentiation +
   NABH/AMR-stewardship angle, not a standalone alert box.
8. **Brand normalization is the make-or-break engineering problem** (60k–100k+ brands, FDCs) → it's also
   the moat; invest accordingly.

## II.10 Open questions for the India panel (clinical-safety + CDSCO-counsel + India-GTM)
- Exact SaMD class for a prescription CDSS, and whether an "inform-only" scoping lowers it.
- Which DDI database to license (coverage vs cost vs India-mappability).
- Real point-of-prescribing availability of structured renal/weight/allergy data in a partner EMR.
- The divergence feature's lawful basis under DPDP (consent vs de-identification) and residency design.
- OEM economics with an EMR partner vs direct hospital-chain sales.
