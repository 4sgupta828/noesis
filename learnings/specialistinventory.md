# Specialist Inventory — searchable, stats-backed medical specialists (US + IN first)

**Status:** SPEC v2 — panel-reviewed (E-series amendments at the end WIN over the v1 body) · **Goal:** a searchable inventory of medical
SPECIALISTS with objective public performance stats, per-specialty × geography, so a case
situation can surface "who has the deepest public track record for THIS" — eventually with
a compliant reach-out path. · **Companions:** CLAUDE.md (kernel/vertical, corpus-first,
credit discipline), `learnings/corpusfirst.md`, `learnings/knowledgegraph.md`.

## Product contract (Rule 1)

- Given a case situation (condition/procedure + geography), return ranked-BY-OBJECTIVE-STATS
  specialists: identity, specialty taxonomy, affiliation, geography, per-metric values with
  PER-FIELD PROVENANCE (source + date), and published practice contact (phone/website; email
  only where the practitioner published it).
- **Objective stats, never quality verdicts**: we publish counts (procedures, publications,
  trials, years, payments) and let users judge; we NEVER emit "better/worse than" derived
  judgments (defamation-adjacent; also clinically unfounded from volume alone).
- Reach-out is PHASE-GATED: v1 displays public contact; any outreach machinery (email/SMS)
  ships only after a consent/compliance design (CAN-SPAM; DPDP for IN).
- Invariants: every field carries provenance; specialists can be corrected/suppressed on
  request (right-of-reply before any public launch); no scraping of ToS-barred aggregators
  (Practo/Justdial/Doximity); kernel stays domain-neutral (a generic ENTITY INVENTORY —
  lawyers/engineers later — vertical supplies taxonomies + metric definitions).

## Data plan

### US (P0 — public-by-design, bulk)
1. **NPPES/NPI bulk file** (public domain, weekly): ~8M providers → filter to specialist
   taxonomies (~1-2M): name, taxonomy, practice address, PHONE. The spine.
2. **CMS Medicare Provider Utilization & Payment** (annual, per-NPI): procedure counts,
   beneficiary counts → the "patients seen / operated" metrics (label the Medicare-population
   skew explicitly).
3. **CMS Doctors & Clinicians** (bulk): med school, graduation year, group, hospital.
4. **Open Payments** (bulk): industry payment totals → influence/COI transparency metric.
5. **EPMC author aggregation** (existing connector): publication count + recency + trial
   investigator roles per name+affiliation (disambiguation via ORCID where present; else
   conservative name+city matching with an ambiguity flag — never merge uncertain identities).

### India (P0-thin, honest)
1. **NMC Indian Medical Register**: identity/qualification/registration — public search, no
   bulk; ingest approach + its legality VERIFIED FIRST (government registry, but scraping
   terms unclear — same legal-manifest gate as corpus sources).
2. **EPMC affiliations** → academic footprint (works today).
3. Hospital find-a-doctor pages: per-hospital, public — curated tranche, top ~50 private/
   public hospitals.
4. NO volume stats exist publicly — the IN profile says so rather than faking a proxy.
5. DPDP Act analysis is a P0 deliverable (publicly-available-data exemption scope, purpose
   limitation for outreach, correction rights).

## Architecture (kernel/vertical)

- Kernel: `noesis_entity` + `noesis_entity_metric` (entity_id, metric_key, value, unit,
  period, source, retrieved_at) + `noesis_entity_contact` (kind, value, source, published_by_
  subject bool). Content-addressed IDs; per-field provenance mirrors edge-evidence design.
- Search: structured facet search first (taxonomy × geography × metric thresholds); optional
  embedded profile blocks for semantic match ("TAVR high-volume in Texas") reusing rs_block
  machinery with entity facets.
- Vertical: taxonomy mapping (NUCC codes → clinical specialties), metric definitions,
  case→specialty routing (the graph already knows condition→specialty affinity via
  masquerade/manifestation edges later).
- Consumers: (1) inventory search UI/API; (2) case-situation matcher (question → condition →
  specialty + geography → stats-ranked list) — flag-gated, server-authoritative.

## Phasing

- **P0:** NPPES spine (specialists only) + CMS utilization + Doctors&Clinicians for 10 pilot
  specialties (cardiology, onc ×3, nephro, neuro, ortho, OB-GYN, pulm, endo) × full US;
  entity store + facet search + provenance; ingestion-console visibility; legal review notes.
- **P1:** Open Payments + EPMC influence layer + ORCID disambiguation; IN registry ingest
  (post legal check) + hospital tranche + EPMC-IN footprint; inventory UI (admin-first).
- **P2:** case→specialist matcher wired to the graph; right-of-reply/correction flow;
  outreach compliance design (own spec).

## Costs / risks

Bulk files are big-but-free (NPPES ~1GB zip; CMS ~2-4GB/yr) — parsing is structural, NO LLM;
storage in Postgres (structured rows, NOT embedded per-provider → ~2-3GB for 1-2M
specialists; embeddings only for pilot-specialty profile cards). Risks: name disambiguation
(merge errors are reputational harm — conservative + flagged), stat misreading (Medicare
skew, teaching-hospital billing under attendings), stale contacts, IN legal gray zones,
"ranking doctors" press risk — mitigated by objective-stats-only contract + provenance +
correction path.

---

# Panel Amendments (v2, E-series) — these override the v1 body

Panel per Rule 17 (Codex GPT-5.5 + Gemini Pro + code-grounded subagent, all returned
2026-08-12/13). One architecture disagreement adjudicated on code evidence (E-5).

## E-0 — People-data legal gate (all three)
A PER-SOURCE PEOPLE-DATA MANIFEST is a hard ingest gate: legal basis, ToS, allowed fields,
update cadence, suppression policy, contact policy. **NMC stays blocked**: DPDP's
publicly-available exemption applies to data the DOCTOR made public — a government registry
publishing it does NOT transfer the exemption to our secondary use (Gemini). Clinician
NOTICE + right-of-reply moves from P2 to BEFORE any public launch (Codex).

## E-1 — Credential/discipline data is first-class, not optional
ABMS/AOA board certification + ACTIVE LICENSE STATUS join the P0 schema ("more relevant to
specialist trust than publications" — Codex). Disciplinary actions: Gemini says launch-
blocking, Codex says include-only-if-perfect — adjudicated: P0 carries
`discipline_status='not_collected'` and the inventory stays ADMIN-ONLY until P1 adds final
public board actions verbatim (action category/date/source link, no summaries). Deceased/
retired detection required.

## E-2 — Identity (unanimous)
Natural keys (NPI; NMC reg no) as entity_id — content-hash IDs only where no registry number
exists (relocation must not orphan metrics). Publication merges: **ORCID-verified only**;
name+city produces flagged CANDIDATES, never auto-merges.

## E-3 — Ranking is an implied verdict — design it away (unanimous)
NO default ranking: the user actively selects the sort metric; sortable tables, not opaque
lists; banned vocabulary: best/top/expert/quality/score/recommended; NO composite score in
P0/P1 ("a verdict wearing a trench coat" — Codex); the case matcher is deferred, flag-gated,
and its output must state: "public-record matches sorted by [metric]; Noesis has not
evaluated quality or suitability."

## E-4 — Metric honesty as fields, not footnotes
Label volumes as "Original Medicare Part B claims, year X" — never "patients seen/operated";
teaching-hospital attribution caveat carried as a field; measurement taxonomy separates
volume / experience / academic activity / COI / credential / availability.

## E-5 — Architecture (adjudicated: dedicated tables WIN)
Gemini's reuse-the-graph-tables proposal is REJECTED on code evidence: the graph read path
is an in-process full snapshot capped ~20k rows — unusable at 1-2M entities. Keep the
dedicated `noesis_entity/_metric/_contact` tables with the graph's WRITE ethos (status
lifecycle, per-field provenance, append-only, never-resurrect) but INDEXED SQL reads only.
Add a `registry_row` CitationVerifier (the protocol already anticipates it) + a staleness
model (`valid_as_of` vs `retrieved_at`, Pulse-style field supersession).

## E-6 — Bulk loading (subagent; unpriced bottleneck found)
No bulk path exists: NPPES (~1GB zip → ~9GB CSV) through the connector protocol would OOM
the API container. P0 adds an OFFLINE streaming CSV→COPY loader run outside the serving
containers (one-off Railway job or local→prod-DB — an explicit, documented exception to the
prod-direct-ingest directive). PRICE the per-procedure CMS table in-spec: ~10M rows/year
(NPI × HCPCS), 10-20GB multi-year against a contended 48.8GB volume — decide HCPCS-level vs
procedure-family rollup BEFORE ingest; "no embeddings for the spine" is load-bearing.

## E-7 — P0 re-scoped (the launchable core)
P0 = NPPES specialist spine (natural-key identity) + CMS utilization (rollup granularity per
E-6) + Doctors&Clinicians + certification/license fields + facet SQL search + per-field
provenance + ADMIN-ONLY console + people-data manifests. CUT from P0: embedded profile
cards, the case matcher, all outreach, Open Payments, publications/trials (until the ORCID
pipeline exists), the India hospital tranche.

## E-8 — India is a labeled PREVIEW tier, not the US product
"Registry + academic footprint preview" only, post-legal-manifest; alphabetical/filter
navigation, no ranking, no contacts without practitioner/hospital-published sourcing; never
commingled with the US stats view (Gemini wanted India cut entirely; Codex's labeled-preview
compromise adopted — the brand risk is commingling, not existence).
