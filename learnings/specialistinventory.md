# Specialist Inventory — searchable, stats-backed medical specialists (US + IN first)

**Status:** SPEC v1 (panel review pending) · **Goal:** a searchable inventory of medical
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
