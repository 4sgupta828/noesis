# Grounded Relationship Graph — the knowledge layer over canonical topics

**Status:** SPEC v1 (panel review pending) · **Flags:** `NOESIS_GRAPH*` (all default OFF, Rule 20)
**Companions:** `learnings/evidencepulse.md` (the currency subsystem this composes with) ·
`learnings/engineprimitives.md` (the Understanding engine whose causal chains this captures as data)

## The idea in one paragraph

A typed relationship graph over the CANONICAL TOPIC REGISTRY (`noesis_topic` — the stable node
vocabulary the Pulse stability contract already guarantees): edges like `causes`,
`increases_risk_of`, `treats`, `contraindicated_with`, `comorbid_with`, `mechanism_of` between
topics, where **every edge carries span-verified evidence and an honesty label**
(established / supported / hypothesized — the Understanding engine's per-link discipline, persisted
as data instead of evaporating as prose). Seeded structurally from free public medical KGs for
instant density; verified and labeled by our own grounded pipeline as answers touch edges — the
graph gets more trustworthy with usage.

## Why now (what it composes with)

- The topic registry solved entity resolution (the usual KG killer) — nodes exist and are stable.
- Change events already prove the typed-edge pattern in prod (`superseded_by`/`retracted`).
- The Understanding engine already GENERATES causal chains with per-link evidence labels —
  capturing them as data was explicitly deferred in engineprimitives; this is that work.
- Rule 18 split holds perfectly: kernel owns nodes/edges/evidence mechanics; the vertical owns the
  relation vocabulary and judgment prompts. Same subsystem serves legal (cites/overrules) or
  regulatory (amends/implements) verticals later (A7 discipline).

## Contract (Rule 1)

- **Given** a question about CKD, **retrieval expansion** (consumer 1) may add searches for
  strongly-related topics (anemia in CKD, mineral-bone disease) via high-confidence edges — and the
  answer must never cite the graph itself as evidence: the graph steers SEARCH; citations still
  come only from span-verified findings. OFF-flag behavior byte-identical.
- **Given** an Understanding-engine answer whose causal chain ships, **chain harvesting**
  (producer 2) records each link as a candidate edge carrying the answer's claim quotes and the
  link's stated label — never upgrading the label, never inventing links not in the answer.
- **Given** a seeded (unverified) edge and a harvested (grounded) edge asserting the same relation,
  the grounded edge's evidence and label WIN; seed provenance is always distinguishable.
- **Invariants:** every edge names its provenance tier (`seed` | `harvested` | `curated`); only
  edges meeting a confidence bar drive retrieval expansion; nothing in the graph is ever surfaced
  to users as a claim without its evidence; graph writes never block or slow the answer path
  (harvest is post-answer, async).

## Architecture

```
                       ┌──────────── producers ────────────┐
  PrimeKG/SemMedDB ──▶ seed importer (structural map to    │
  (free downloads)     registry topics; provenance=seed)   │
  Understanding/reasoned answers ──▶ chain harvester       │  (post-answer, async;
                       (links + claim quotes + labels)     │   LLM maps endpoints → registry)
  curator ──▶ declared edges (provenance=curated)          │
                       └───────────────┬───────────────────┘
                                       ▼
                    noesis_topic_edge  (kernel; the ledger pattern again)
                                       │
        ┌──────────────────────────────┼──────────────────────────────┐
        ▼                              ▼                              ▼
  [C1] retrieval expansion      [C2] Pulse propagation          [C3] answer/UI surfaces
  (adjacent-topic searches      (a change event ripples to      (related-topics chips;
   for high-confidence edges)    related topics' watchers)       graph view — LAST)
```

### Data model (kernel, additive)

```sql
CREATE TABLE noesis_topic_edge (
  id          text PRIMARY KEY,          -- sha(subject|relation|object)
  subject     text NOT NULL,             -- canonical topic label (FK noesis_topic by norm)
  relation    text NOT NULL,             -- vertical vocabulary (validated against manifest)
  object      text NOT NULL,
  label       text NOT NULL DEFAULT 'hypothesized',  -- established | supported | hypothesized
  provenance  text NOT NULL,             -- seed | harvested | curated
  evidence    jsonb NOT NULL DEFAULT '[]'::jsonb,    -- [{quote, document_id, session_id?}] — REQUIRED for harvested
  confidence  real NOT NULL DEFAULT 0,   -- seed-source score or harvest-count-derived; expansion gate
  seen_count  integer NOT NULL DEFAULT 1,-- times independently harvested (agreement strengthens)
  created_at  timestamptz NOT NULL DEFAULT now(),
  updated_at  timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX ... ON noesis_topic_edge (subject);
CREATE INDEX ... ON noesis_topic_edge (object);
```
Edge identity is (subject, relation, object); re-harvest increments `seen_count`, appends evidence
(capped), and may RAISE label only when the new evidence's label is stronger AND independently
sourced (code-checked: distinct document_ids). Same audit ethos as the change-event ledger.

### Producers

1. **Seed importer (P0, structural, zero-LLM at scale):** one-time script mapping PrimeKG (or
   Hetionet) disease–disease / disease–drug edges onto registry topics. Mapping = normalized-name
   match + synonym table from the source itself; unmatched entities are SKIPPED (never minted as
   new topics — the registry's stability contract outranks graph density). Provenance=`seed`,
   label=`hypothesized` regardless of source claims (we didn't verify them), confidence from the
   source's own scores. License check before ingest (PrimeKG: MIT-ish; SemMedDB: UMLS terms —
   verify; prefer PrimeKG first).
2. **Chain harvester (P1, the differentiator):** post-answer async hook — when an Understanding
   (or reasoned) answer ships with causal-chain content, one LLM call extracts links as
   (subject, relation, object, label, supporting claim indices), endpoints mapped onto the
   registry (reuse the canonicalizer; unmapped endpoint → skip, log). Code re-verifies that each
   cited claim index exists and copies its quote/document_id into edge evidence. Never blocks the
   answer; failures drop silently to a log.
3. **Curated edges (P0): trivial — a vertical-declared list, like declared lineage.**

### Consumers (phased)

- **[C1] Retrieval expansion (P0, flag `NOESIS_GRAPH_EXPAND`):** in `ask()`, after the scaffold:
  look up the question's topics (reuse `/pulse/topics` extraction or scaffold subjects), fetch
  edges above the confidence bar (default: `curated` OR `seen_count>=2` OR seed-confidence high),
  cap at 2-3 adjacent topics, append ONE compact context line: "RELATED (from the relationship
  graph — verify before relying): X (treats), Y (comorbid)". The planner decides whether to search
  them (LLM owns the judgment); no automatic extra searches (cost-bounded).
- **[C2] Pulse propagation (P1):** event subjects → adjacent topics → those topics' watchers get
  a "related change" inbox item (visually distinct, lower priority than direct hits).
- **[C3] Surfaces (P2):** "related topics" chips on answers/Pulse cards; a graph visualization
  view LAST (engagement candy only after the data is trustworthy).

## Eval gates (Rules 4/5/7 — before any consumer trusts the graph)

- Seed mapping precision: sample 50 mapped edges → manual/LLM-judge check that topic mapping is
  correct (target ≥95%; wrong-node edges poison expansion).
- Harvester no-invention: held-out answers with known chains → extracted edges must be exactly the
  chain's links with matching labels; a fabricated link or upgraded label fails.
- Expansion win/loss: A/B a small held-out question set with C1 on/off — expansion must not drop
  evidence-floor pass rates (relevance dilution is the known risk) and should improve coverage on
  multi-system questions.

## Costs

Seed import: one-time, structural. Harvester: 1 small call per Understanding-engine answer (only
when chains present). Expansion: zero extra LLM calls (context line only); bounded extra searches
only if the planner chooses them. Registry growth: bounded by skip-unmatched policy.

## Risks / honest unknowns

- **Wrong edges are worse than no edges** (expansion pollutes retrieval; propagation spams
  watchers) — hence the confidence bar, provenance tiers, and eval gates before consumers ship.
- Seed licensing must be verified per source before ingest.
- Registry topic granularity ("anemia" vs "anemia in CKD") will produce near-duplicate nodes —
  mitigation: edges may need the canonicalizer's judgment at harvest; possibly a `narrower_than`
  relation later. This is the hardest open design question.
- The graph must never become an uncited answer shortcut — the contract's "graph steers search,
  never cites" line is the guardrail; violating it would break the product's core promise.

## Phasing

- **P0:** schema + curated edges + PrimeKG seed import (license-checked) + C1 expansion dark
  behind flag + seed-mapping eval.
- **P1:** chain harvester + its no-invention eval + C1 ON after the expansion A/B passes.
- **P2:** Pulse propagation; related-topic chips; graph view last.
