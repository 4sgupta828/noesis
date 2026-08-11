# Grounded Relationship Graph — the knowledge layer over canonical topics

**Status:** SPEC v2 — panel-reviewed (Codex GPT-5.5 + Gemini 3.1 Pro + code-grounded subagent,
2026-08-11; all three returned). Where the Panel Amendments below conflict with the v1 body,
the AMENDMENTS WIN. · **Flags:** `NOESIS_GRAPH*` (all default OFF, Rule 20)
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

## Phasing (v1 — SUPERSEDED by Amendment A3; kept for the record)

- ~~P0: schema + curated edges + PrimeKG seed import + C1 dark + seed-mapping eval.~~
- ~~P1: chain harvester + no-invention eval + C1 ON after A/B.~~
- ~~P2: Pulse propagation; related-topic chips; graph view last.~~

---

# Panel Amendments (v2) — these override the v1 body above

Three-member panel per Rule 17: **Codex (GPT-5.5)**, **Gemini 3.1 Pro**, and a **code-grounded
subagent** (file:line verification), all with repo access, all returned. Convergence was
unusually strong — all three independently demanded the same four structural changes (A1–A4).

## A1 — Drop seeding from P0 entirely (unanimous)

At ~106 disease-only registry topics with skip-unmatched, PrimeKG yields near-zero edges
(disease–drug edges map to nothing — no drug topics exist; disease–disease among 106 common
conditions is a few hundred max, further cut by MONDO-vs-clinical-phrase name mismatch).
Licensing is also NOT "MIT-ish": PrimeKG bundles DrugBank-derived data with commercial
restrictions; SemMedDB requires a UTS/UMLS license (redistribution limits). **P0 graph content =
curated + (later) harvested only.** Revisit seeding when the registry is materially larger,
preferring **Hetionet (CC0)**, and even then as an offline experiment reporting match rate and
sampled precision BEFORE any prod write.

## A2 — Schema: edge + evidence tables, `status` column, norm identity (unanimous)

The v1 single-table design has four verified defects:

1. **No `status` column** — the change-event ledger's defining feature (shadow→approved gating
   effect, `store.py:32,138-153`) is missing, so "the ledger pattern again" wasn't actually the
   ledger pattern. Every edge gets `status` (`shadow` | `active` | `demoted`); **harvested edges
   are BORN shadow** and only the eval gate (A4) activates them. Consumers read `active` only.
2. **Evidence must be its own table** (`noesis_edge_evidence`, `document_id` indexed), not a
   jsonb blob — because of A5 (invalidation): finding every edge that leans on a retracted
   document must be an index lookup, not a full jsonb scan.
3. **Identity on NORM, not label** (`store.py:64-65`), with direction preserved and an optional
   `context_topic` in the identity key (A6). v1's "FK noesis_topic by norm" was not implementable
   as written (label is the PK; edge stored raw labels).
4. **`seen_count` = count of DISTINCT evidence document_ids**, not raw re-harvests — the same
   user re-asking the same question must not manufacture "independent" agreement.

## A3 — Reorder consumers: C2 (Pulse propagation) FIRST, C1 (retrieval expansion) LAST (unanimous)

C1 touches the live answer path; its real failure mode (all three panelists) is **planner
pollution** — a "RELATED topics" line competing with the planner's own search budget
(`react.py:643,718`) can crowd out on-question evidence BEFORE the span gate ever runs. C2 is
the cheap, safe first consumer: change-event subjects are already canonical topics
(`app.py:1611`), adjacency is one join, and the worst case is a low-priority inbox item — not a
degraded answer. **New phasing:**

- **P0:** schema per A2 + relation manifest + curated edges (incl. `narrower_than`, A6) +
  invalidation hook (A5) + admin/read API + **C2 dark** behind `NOESIS_GRAPH_PULSE`.
- **P1:** chain harvester writing SHADOW edges + no-invention/entailment eval (A4) + C2 ON.
  Related-change inbox items visually distinct, lower priority than direct hits. PLUS
  **C1 shadow-counterfactual logging** (per A9 — zero user-facing change, starts accumulating
  the recall-value evidence here).
- **P2:** C1 (graph-guided evidence legs, A9) behind `NOESIS_GRAPH_EXPAND`; ON only after the
  win-seeking A/B passes (must recall gold evidence graph-off misses on multi-hop questions,
  AND hold evidence-floor pass rate + steps-consumed on single-topic questions).
- **P3:** related-topic chips; graph view; seeding revisit per A1.

## A4 — Harvester: eval gates WRITES, not reads; labels need an entailment check (unanimous)

Code-verified reality: Understanding-engine chains are **prose only** — a composer directive
(`understanding.py:14-49`), never persisted as structure (`ComposedAnswer`/`AnswerResult` have no
chain field). So the harvester is prose re-extraction, and three leaks survive v1's index check:
label inflation (hypothesized→established lives only in prose — no code check can catch it),
wrong relation choice (causes vs. increases_risk_of), and citing a claim that merely MENTIONS
both endpoints without supporting the relation (the exact failure `understanding.py:43` warns
about). Therefore: **(a)** harvested edges are born `status='shadow'` (A2) and the no-invention
eval must PASS before any edge activates — eval-before-effect is structural, not procedural;
**(b)** add an LLM **entailment gate** at write time (does the quoted claim entail this relation
at this label?) — claims_first's entail pattern is the model; **(c)** code-enforced label
monotonicity (a raise requires a strictly stronger, independently-sourced label) and
distinct-document independence; **(d)** relation must be in the vertical manifest allowlist;
**(e)** NO silent failure drops — counters + a quarantine record for ambiguous extractions
(auditability is the product promise). **(f)** Persist an `engine` field on
`noesis_research_session` so the harvester selects Understanding answers structurally instead of
sniffing markdown headings.

## A5 — Evidence invalidation invariant (Gemini: "fatal if missing")

The graph must LISTEN to the currency subsystem it lives beside: when a document receives a
`retracted` or `superseded_by` change event (`CurrencyStore.apply_stamps`), every edge whose
evidence cites that `document_id` is re-evaluated — retracted-only evidence ⇒ edge demoted
(`status='demoted'`, consumers stop reading it); superseded evidence ⇒ flagged for re-harvest
against the successor. This is why evidence is a normalized indexed table (A2.2). An edge whose
evidence has died must never keep steering search or propagating Pulse pings.

## A6 — Topic granularity: minimal policy NOW, not deferred (unanimous)

Full deferral is unacceptable — WATCH_TOPIC_PROMPT itself mints composites ("anemia in CKD" is
its own example, `pulse.py:18`), so near-duplicate nodes are guaranteed and every harvested edge
would land on an arbitrary one, while exact-norm matching makes "anemia" and "anemia in CKD"
totally disconnected (C2 would never reach the "anemia" watcher). Minimal policy, no ontology
machinery: **(a)** edge endpoints prefer BROAD subjects, with an optional `context_topic`
qualifier carrying the setting/population (subject=CKD, relation=increases_risk_of,
object=anemia, context=CKD — not a new compound node per relation); **(b)** add
`narrower_than` as a curated-only relation in P0 (~20 rows for known composites) and have C2/C1
traverse it upward; **(c)** harvest endpoints must pass CANONIZE against the shown registry, and
"returned unchanged AND not in registry" = unmapped = SKIP (the prompt's return-unchanged rule
otherwise silently mints raw strings).

## A7 — C1 mechanics: planner-only `graph_context`, and the honest cost line (Codex + subagent)

v1's "in `ask()`, after the scaffold" doesn't exist — the scaffold lives in `ask_reasoned()`
(`research.py:161-204`); and appending to `question` is forbidden because `question` flows into
the COMPOSE prompt (`react.py:643,898`) — graph text could then shape uncited prose (the span
gate protects claims, not prose). The real design: a new **planner-only `graph_context` param**
threaded into `run_react`, modeled on `conv_ctx` (`react.py:553-559`), structurally excluded
from compose. New invariant alongside "never cites": **graph text never enters the compose
prompt.** And drop v1's "zero extra LLM calls" claim — mapping the question onto registry topics
is semantic (Rule 18); either piggyback the existing scaffold call in `ask_reasoned()` (add a
`canonical_topics` field — genuinely zero extra calls, reasoned-path-only) or admit +1 small
call. P0 expansion is capped at **one** adjacent topic and disabled on dosing/contraindication/
safety questions unless the edge relation is directly on-point; log suggested topics, searched
queries, and floor deltas every time.

## A8 — Honesty edit to the premise

"The topic registry solved entity resolution" is overstated: it solved stable string REUSE
(case/whitespace norm + LLM-shown registry), not medical entity resolution — synonyms are
prompt-mediated, not deterministic. The spec's claims and the granularity policy (A6) are
written against that weaker, true foundation.

## A9 — C1 redesigned: graph-guided evidence legs (post-panel, user-driven deepening)

The panel reviewed C1 as "a RELATED-topics hint to the planner" and rightly contained it. But
that mechanism undersells the graph's actual value: **search can only find evidence semantically
near the question as asked.** Two structural misses follow — vocabulary miss (the CKD-fatigue
question never reaches evidence indexed under "erythropoietin deficiency / ESA therapy") and
multi-hop miss (the load-bearing evidence is about an intermediate topic — CKD → anemia →
fatigue — that appears nowhere in the question text; no reformulation is guaranteed to reach
it, and the planner reformulates only toward its own priors). The graph knows the hop as
verified data, so it can generate the query the user never typed. That is recall the search
stack cannot achieve alone — the graph compensates for missing semantic capture and missing
reformulations.

**Mechanism (replaces the planner context line as C1's primary design):**

1. Question → registry topics (the one semantic step — scaffold piggyback per A7, or +1 small
   call).
2. Walk **1-hop** edges above the confidence bar (2 hops compounds edge error multiplicatively
   and explodes fan-out — not in P0/P1).
3. **Generate sub-queries from edge templates in code** — `CKD —increases_risk_of→ anemia
   [context: CKD]` ⇒ "anemia in chronic kidney disease". Deterministic, auditable, zero LLM.
4. Run them as **capped additional retrieval legs** (P0 caps: ≤2 graph legs, smaller k per leg)
   alongside the normal legs; merged candidates flow through the EXISTING ranking, evidence
   floors, and span gate unchanged. Every graph-pulled block is provenance-tagged with the edge
   that fetched it (diagnostics + measurement).

This deletes the panel's planner-pollution objection at the root: the planner's step budget is
untouched, nothing is suggested to an LLM, and the graph's contribution is exactly measurable.
The A7 invariants hold unchanged — graph text never enters compose, never gets cited; the graph
only widens what the span gate chooses from. A bad edge's block still has to out-rank
on-question evidence and survive the floors. Residual risk is candidate-pool dilution — managed
by the caps, not by not building it. The planner hint (old C1) is demoted to an optional
secondary experiment.

**Shadow-counterfactual mode (how the value hypothesis gets proven before anything changes):**
run steps 1–4 but DON'T merge — log what would have happened: "graph legs surfaced N blocks;
M would have entered the top-k pool; K cover a topic no searched query touched." Zero
user-facing change, so this is as safe as C2-dark and starts in **P1** (amending A3's ordering:
C1-shadow no longer waits for P2; only C1-ON stays behind the eval). A week of prod shadow
traffic turns the value question from a design debate into a measurement.

**Eval reframed from no-harm to win-seeking:** on held-out multi-hop questions with known gold
evidence, graph-on must recall evidence graph-off provably misses; PLUS the no-harm check
(evidence-floor pass rate, steps consumed) on single-topic questions. The A/B ships C1 ON only
on a win, not merely an absence of harm.

**Consequences elsewhere:** ~30 curated edges for top conditions (CKD↔anemia, AF↔stroke,
diabetes↔CKD, HFpEF↔cardiac amyloidosis, …) are sufficient to test the recall hypothesis —
seeding (A1) remains unnecessary for this. And the write-side discipline (A2/A4/A5) becomes
MORE important, not less: under this design a bad edge silently spends retrieval budget, so
shadow status, entailment gates, and invalidation are what make retrieval-side trust possible.
