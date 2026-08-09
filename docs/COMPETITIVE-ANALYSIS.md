# Noesis — Competitive Analysis & "What to Build Next"

*Prepared 2026. Competitor facts are from web research (dates noted inline); this space moves
weekly, and several vendor numbers are marketing/unverified — flagged as such. The goal is not a
scoreboard but a decision: **what to build to get clinicians using Noesis and giving feedback.***

---

## 0. TL;DR — the one-paragraph strategy

The field has split into two camps, and **two independent benchmarks in 2026 show neither camp has
won**: curated-corpus incumbents (**UpToDate Expert AI**, **ClinicalKey AI**, **AMBOSS**) have
trust, editorial depth, and EHR reach but closed/narrow content and conservative behavior (UpToDate
refused 19% of queries); frontier assistants (**ChatGPT for Clinicians**, **Claude for Healthcare**)
have scale, free access, and loud evals but thinner provenance and documented safety gaps (a Mount
Sinai study found 52% emergency **under**-triage). Noesis's real assets — **verbatim-verified
provenance** (every claim carries a quote proven to exist in its source), a **transparency layer**
(reasoning + confidence + informed judgment), the **Specialist Panel**, **Guided intake**, and
**geo-adaptability** (India) — sit exactly in the gap both camps leave: *frontier-grade reasoning you
can actually audit.* **But none of that matters until people can sign in and use it.** The single
biggest blocker to customers+feedback is not a feature — it's **access**: no accounts, no free
verified-clinician tier, no in-product feedback capture. Fix that first; then win a beachhead on
**trust-through-transparency + non-US relevance**, not by out-contenting UpToDate or out-scaling
ChatGPT.

---

## 1. The market map (what changed in 2025–2026)

- **Everyone converged on the same recipe:** conversational RAG, inline citations, clinician-in-the-
  loop, "say I don't know," and a *non-device* regulatory posture (no FDA clearance; all disclaim
  replacing clinical judgment). Grounding + citations are now **table stakes**, not a differentiator.
- **Two independent benchmarks are the credibility currency:**
  - **NOHARM** (Stanford/Harvard/ARISE, Forbes 4 Mar 2026; 100 real eConsult cases, 31 systems):
    **AMBOSS LiSA 1.0 #1 (62.3%)**, **Glass Health 4.0 ~3rd (59.0%)**, both narrowly edging frontier
    general LLMs — but the top ~6 were statistically similar and *all* systems produced harmful
    recommendations at non-trivial rates.
  - **Nature Medicine** (Jul 2026): general frontier LLMs (GPT-5.x, Gemini 3.1, Claude Opus)
    **out-scored** specialized tools UpToDate Expert AI (88.4% MedQA) and OpenEvidence on knowledge
    and expert alignment; UpToDate stood out for a **19% refusal rate** (WK frames refusal as safety).
- **Implication for Noesis:** (1) the frontier model *is* the quality engine — Noesis being
  model-agnostic (rides Opus/GPT) is an advantage, not a liability; (2) the battleground has moved
  from "can it answer" to **"can I trust and verify the answer, in my workflow, for my patients"** —
  which is precisely provenance + transparency + integration + safety. That's the game to play.
- **The elephant not on the list: OpenEvidence.** Free, ad-supported, physician-verified, and already
  the most-adopted evidence-Q&A tool among US clinicians; it's also ClinicalKey AI's launch tech
  partner. It is the *actual* incumbent to displace in the "evidence Q&A" job — and its weakness
  (thin provenance/transparency, US-centric, ad-funded) is Noesis's opening.

---

## 2. Full comparison matrix

Legend: ●●● strong · ●● moderate · ● weak/absent · — n/a. Noesis ratings are the honest read from
the current codebase.

| Dimension | **Noesis** | UpToDate Expert AI | ClinicalKey AI | AMBOSS AI | Glass Health | ChatGPT for Clinicians | Claude for Healthcare |
|---|---|---|---|---|---|---|---|
| **Primary job** | Evidence Q&A + multi-specialist panel + guided intake | Point-of-care Q&A | Point-of-care Q&A | Q&A + exam prep + DDx sidecars | DDx + A&P + scribe | General clinical assistant + cited search | Enterprise coding/RCM/prior-auth + research |
| **Content corpus** | Primary sources: trials, drug labels, FAERS, PMC lit, CDC, curated India guidelines, + trusted web | Closed graded editorial (UpToDate) + Lexidrug | Broad: society guidelines + full-text NEJM/Lancet/JAMA + textbooks + proprietary | Closed curated library (~1,500 topics) + drug DB + US guidelines | Physician-curated guidelines + PubMed | Undisclosed; "peer-reviewed" cited search | MCP to PubMed(35M)/ClinicalTrials/CMS/ICD-10 |
| **Content breadth** | ●● (deep on trials/drug-safety; thin on "what to do") | ●●● | ●●● | ●● | ●● | ●● | ●● |
| **Grounding / provenance** | ●●● **verbatim-verified quote per claim (span-checked)** | ●● cites + high abstain | ●● RAG + real-time citation validation | ●● inline citations, "IDK" | ●● inline citations | ●● cited search (corpus opaque) | ●●● span-level provenance |
| **Answer transparency** | ●●● reasoning-read: interpretation + confidence + informed judgment | ●● shows reasoning/assumptions | ● | ● flags guideline disagreement | ●● 3-tier live differential | ● | ● |
| **Distinctive UX** | Specialist Panel (multi-lens) · Guided triage · briefing videos · patient mode | — | CME/MOC tracking | Education↔practice ecosystem | Ambient scribe + DDx | Reusable "skills" | Agent skills (coding/prior-auth) |
| **Workflow depth (case→DDx→plan)** | ● (panel/triage partial) | ● | ● | ●● (DDx sidecar) | ●●● (DDx+A&P+scribe) | ●● | ●● (admin) |
| **EHR / FHIR integration** | ● none | ●● ecosystem embedding | ●●● SMART-on-FHIR SSO + API | ● early "Clinic Connect" + MCP | ●● Epic/athena/Elation (Max tier) | ●● FHIR at consumer/enterprise | ●●● FHIR skills → Epic/Cerner/MEDITECH |
| **Compliance / trust infra** | ● HCP-informational disclaimer only; no BAA | ●● governance tooling | ●●● HIPAA-built, no-train, CHAI | ●● (HIPAA unverified) | ●● (BAA/SOC2 unverified) | ●●● BAA + customer keys (enterprise) | ●●● BAA + Bedrock/Vertex |
| **Access / distribution** | ● demo tenant, no accounts | ●● Pro Plus / enterprise | ●● institutional + individual + free student yr | ●● bundled subscription (~$12.50/mo student) | ●● free Lite + paid tiers | ●●● **free for verified US clinicians** | ● enterprise/dev only |
| **Independent eval** | ● internal India/US baselines only | ●● Nature Med (trailed LLMs, 19% refuse) | ● none found | ●●● **NOHARM #1** | ●● NOHARM ~3rd | ●● HealthBench 59>physicians (but triage-unsafe study) | ● no public clinical-chat eval |
| **Geography / language** | ●● **US + India scoping, multilingual-ready** | ● US/English-centric | ● English-centric | ●● multilingual, US-guideline-biased | ● English only | ● US-first | ● US-first |
| **Mobile** | ● web only | ●● iOS/Android app | ●● app + voice | ●● app + offline | ●● iOS/Android | ●● | — |
| **Moat** | Provenance discipline + vertical-agnostic engine + geo | Brand + editorial network + install base | Content licenses + integration | Education install base + corpus | DDx/scribe workflow | Distribution + model | Connectors + enterprise + model |

---

## 3. What each competitor has that Noesis doesn't

- **UpToDate Expert AI** — a *trusted brand* and a graded editorial corpus 7,600 experts maintain, plus
  deep health-system install base. Noesis has no brand and no "what-to-do" editorial layer. (Its 19%
  refusal is a weakness Noesis can beat with grounded-but-answering behavior.)
- **ClinicalKey AI** — the strongest *content licenses* (full-text NEJM/Lancet/JAMA + textbooks +
  society guidelines), **SMART-on-FHIR** EHR SSO, real HIPAA/no-train posture, and CME/MOC tracking.
- **AMBOSS AI** — the **#1 independent safety benchmark**, an education→practice funnel that owns
  students before they're attendings, and a closed physician-reviewed corpus. Noesis has *no external
  benchmark* and *no education funnel*.
- **Glass Health** — a purpose-built **encounter workflow**: case → live differential → A&P →
  ambient scribe, with multi-EHR write-back. Noesis has no case-to-plan flow and no scribe.
- **ChatGPT for Clinicians** — **free, low-friction, verified-clinician access at scale** + CME +
  reusable skills + the loudest self-reported eval. Distribution is its superpower; Noesis's is
  effectively zero today.
- **Claude for Healthcare** — auditable **MCP connectors** to authoritative structured sources,
  span-level provenance, real FHIR-to-EHR reach, BAAs, and pharma/health-system partnerships. It
  validates the "provenance + connectors" thesis Noesis is built on — but skews administrative, not
  bedside, leaving the *clinical-Q&A-with-provenance* lane open.

---

## 4. Noesis — honest SWOT

**Strengths (defensible, shipped):**
- **Verbatim-verified provenance** — the hardest grounding claim in the field (proves the quote
  exists in the source, not just "cites a source"). This is the brand.
- **Transparency layer** — reasoning-read (interpretation + confidence + informed judgment); nobody
  else foregrounds "how far to trust this."
- **Specialist Panel** and **Guided intake** — genuinely novel surfaces.
- **Primary-evidence depth** on trials, drug labels, adverse events — exactly where Glass is weak.
- **Geo-adaptability** (India ingest + country scoping) — every incumbent is US-guideline-biased.
- **Model-agnostic frontier** — rides the very models the Nature Medicine study says win.

**Weaknesses (blocking adoption):**
- **No accounts / no free verified-clinician tier / single demo tenant** — can't onboard or retain.
- **No in-product feedback capture** — can't learn from users.
- **No HIPAA/BAA, no SOC2, no clinician verification, no brand** — fails enterprise/trust bar.
- **No EHR/FHIR** — not in the point-of-care workflow.
- **No curated "what-to-do" guideline layer** — thin vs. UpToDate/ClinicalKey on management guidance.
- **No case→DDx→A&P flow, no mobile app, no CME, no external benchmark.**

**Opportunities:** the *trust-through-transparency* lane (post-benchmark, provenance is the currency);
the *non-US* markets everyone ignores; *drug-safety/interactions* depth; being the auditable frontier
alternative to OpenEvidence.

**Threats:** OpenEvidence's free distribution; ChatGPT's free clinician tier; incumbents bolting AI
onto content moats; commoditization of "cited RAG."

---

## 5. What to build next — prioritized for *adoption + feedback*

Ordered by "unblocks real usage" first, not feature-parity. Each ties to the actual constraint:
getting clinicians in and hearing from them.

### P0 — Make it usable & learnable (weeks, not quarters) — *do these before anything else*
1. **Accounts + verified-clinician free tier.** Replace the localStorage name/email gate with real
   auth and server-side per-user history; add lightweight clinician verification (email domain / NPI
   lookup) to unlock a free tier and to signal "for professionals." *This is the #1 blocker to
   customers.* (ChatGPT/ClinicalKey/AMBOSS all lead with easy verified access.)
2. **In-product feedback capture.** Per-answer 👍/👎 + "was this correct/complete?" + "flag this
   claim," written to a table you can review. You cannot improve or sell without this loop.
3. **Lead with the provenance story.** One-screen "why you can trust this" (verbatim-quote checking,
   reasoning-read, no claim without a source) — make the differentiator legible on first use.

### P1 — Earn credibility & sharpen the wedge (this quarter)
4. **Publish an independent-style eval.** Run a NOHARM/HealthBench-style benchmark (or externalize the
   India/US baselines) and publish the number + methodology. A benchmark is now table stakes for
   credibility; Noesis is the only tool here without one.
5. **Curated guideline layer.** Ingest and maintain a set of major guidelines (specialty societies,
   WHO/CDC/NICE/ICMR) via the existing connector architecture, so answers rest on *management
   guidance*, not only trials/labels — closing the biggest content gap without licensing textbooks.
6. **Own the non-US beachhead.** Double down on India (and the next locale): local guidelines, brands,
   and country-scoped retrieval where UpToDate/AMBOSS are explicitly weak. This is where a small team
   can get real clinicians using it and giving feedback *because it's more relevant than the giants.*

### P2 — Workflow depth (next)
7. **Case → DDx → A&P flow** built on the panel/triage machinery (compete with Glass on structured
   clinical reasoning, with better provenance).
8. **EHR/FHIR read** (SMART-on-FHIR) to pull patient context at point of care; ambient scribe later.
9. **Mobile (PWA first)** — everyone else has an app.

### P3 — Enterprise & trust infrastructure (when pulled by demand)
10. **HIPAA/BAA + SOC2 + teams/admin** — required the moment you touch PHI or sell to institutions.
11. **CME** — both an engagement lever and a distribution funnel (ClinicalKey/AMBOSS/ChatGPT all use it).

---

## 6. Positioning recommendation

**Don't** try to out-content UpToDate/ClinicalKey or out-scale ChatGPT/OpenEvidence. **Do** win the
narrow, defensible wedge the benchmarks just exposed:

> **"Frontier-grade clinical answers you can actually audit — every sentence backed by a quote we've
> verified, with the reasoning and confidence shown — and tuned to *your* guidelines, not just US
> ones."**

Beachhead: pick one under-served, reachable segment where the free tier + provenance + local
relevance create pull and a tight feedback loop — the strongest candidate is **Indian clinicians**
(large, English-capable, under-served by US-biased incumbents, and Noesis already has the ingest
seam). Land there, harvest feedback, and let the provenance/transparency engine be the thing that
travels back to the US market as the "trustworthy alternative."

---

## 7. Sources & caveats

Key independent signals: **NOHARM** (Stanford/Harvard/ARISE, Forbes 4 Mar 2026); **Nature Medicine**
LLM-vs-clinical-tools study (Jul 2026); **HealthBench Professional** (arXiv, OpenAI) and the
countervailing **Mount Sinai triage study** (Nature Medicine, Feb 2026). Vendor pages for UpToDate
Expert AI (Sep 2025), ClinicalKey AI (Elsevier), AMBOSS AI Mode (Nov 2025 / Feb 2026), Glass Health,
OpenAI (ChatGPT for Clinicians, Apr 2026), and Anthropic (Claude for Healthcare, JPM 2026).

**Flagged as unverified / vendor-sourced:** exact per-seat pricing across products; AMBOSS & Glass
HIPAA/BAA/SOC2 status; Glass's "97/98/90%" accuracy figures (no primary source); named EHR
certifications for several AI layers; Claude's MedAgentBench/USMLE numbers. Treat all competitor
specifics as directionally current, not contractual — re-verify before external use.

---

## Addendum (Aug 2026): Perplexity — the general research engine clinicians actually use

Perplexity isn't a clinical product, but it's the research UX bar and informally used by clinicians —
so it belongs in the comparison. Research as of mid-2026, sources in the research log.

**What it is.** Deep Research (Feb 2025): agentic multi-search (~20–50 queries, hundreds of sources),
2–4-minute cited reports; by 2026 folded into "Perplexity Computer" routing subtasks across 20+ models.
Free/Pro($20)/Max($200)/Enterprise tiers. Self-reported evals: 21.1% Humanity's Last Exam, 93.9%
SimpleQA. **Perplexity Health** (Mar 2026) is consumer-wellness (Apple Health/EHR dashboards, NEJM/BMJ
"premium sources") — NOT a clinician evidence engine. HIPAA only via Enterprise BAA.

**Where Noesis is structurally ahead (the moat, confirmed):**
- **Provenance:** Perplexity attaches *links*, never verifies the claim exists in the source — the Tow
  Center/CJR study found it wrong on ~37% of citation tests (and it was the BEST of 8 engines tested);
  documented real-URL/wrong-claim failures, AI-slop pages cited as sources, and an active
  false-attribution lawsuit (Dow Jones). Noesis's verbatim span-check is precisely the thing it lacks.
- **Evidence hierarchy:** a guideline, an RCT, and a content farm render as identical numbered chips;
  medical sourcing is SEO-rank-driven (WebMD-tier sources documented). Noesis has authority tiers +
  now a curated top-tier guideline layer.
- **Calibration:** "confidently wrong," minimal hedging (Tow Center) vs Noesis's reasoning-read
  confidence decomposition + coverage-gap honesty.

**What to steal from its UX (priority order):**
1. **Suggested follow-ups everywhere** — their single biggest session-extender (we have /suggest; make
   it more prominent).
2. **Hover source previews + a persistent source rail** — our evidence dossier is stronger but buried;
   surface per-sentence source cards on hover.
3. **Clarifying questions before long runs** — we built this (Guided mode); Perplexity validates it.
4. **Focus modes** (e.g. "guidelines only / trials only" source scoping as one-click toggles — we have
   the facets, no UI).
5. **Export/Pages** — shareable formatted briefs from answers (we have copy-markdown; a share-page is a
   step further).
6. **Speed as a feature** — 2–4 min beats 30; our long runs need the progress narration to carry trust
   (we have the live trace — keep investing there).

**Net:** Perplexity wins speed, polish, and breadth; it structurally cannot claim verified provenance,
evidence tiers, or clinical calibration — the exact lane Noesis occupies. Its Health launch pulls
consumer attention to "AI + health" without entering the clinician-evidence niche.
