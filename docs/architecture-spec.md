# Factra v2 — Vertical-Agnostic Research Platform: Target Architecture Spec (v2, panel-reviewed)

**Status:** Panel-reviewed (Codex GPT-5.5 + Gemini 3 Pro + code-grounded subagent — all three returned). Central corrections folded in.
**Author:** Claude — grounded in seam maps + a 3-member adversarial panel of `app/research_system/**`
**Date:** 2026-07-29

## 0. What we are building

A ground-up rebuild of Factra as a **vertical-agnostic evidence/research platform**: a domain-agnostic **kernel** (ingest → corpus → retrieval → research → synthesis) with a **vertical plug-in contract** on top. Regulatory-commissions is **vertical #1** (reference impl), **ingestion-based for all states incl. Ohio**.

**Locked (user):** greenfield build; retire legacy `app/` + the entangled local PUCO/Ohio pipeline; ingestion-based for all states; generic-core + verticalized-top; validate against regulatory/legislative/financial (only regulatory ships); data-migration deferred.

**Decisions resolved by the panel round (user-confirmed):**
- **O2 = lift-and-refactor** (Codex + Gemini). Port the proven research *organs* under clean contracts (ReAct mechanics, corpus-path span-check, comparison composer, retrieval fusion, cost governor, breaker/storage); **rewrite only the domain-welded skeleton** (gating/coverage/routing control flow, OH decision-tree router, origin routing) against the §4 policy interface; **re-author the qa eval** to be vertical-parameterized. No 100%-from-scratch rewrite of proven provenance/retrieval algorithms.
- **O1 = clean design, OH adaptation layered on — NO legacy carryover.** Keep a self-hosted **residential worker** as a first-class *egress class*, but **retire the Ohio legacy DB, the legacy `strata_rs` corpus substrate, the local-download/remote-download bridge, and the poll/sweep pipeline entirely.** Ohio becomes **just another connector** on the *generic* ingestion pipeline, with its F5/JA3 specifics (Firefox engine, homepage warm-up, persistent cookies, 8s pacing, residential egress) declared as a **layered `WarmedResidentialBrowserStrategy` + OH connector adaptation** — not a bespoke subsystem. OH data lands in the **unified corpus** like every other state. Any historical OH data worth keeping is a one-time deferred ETL (§0 migration-deferred), not a retained pipeline.

**Inherited as requirements (survive the rebuild):** LLM-owns-meaning / no-regex-for-semantics (Rule 18); span-check provenance hard gate; held-out eval discipline; forward-only migrations; immutable snapshots; flags-default-OFF as rollback seams; observability on LLM paths; **tenant isolation as a security invariant (Rule 15)**.

> ### ⚠️ PANEL HEADLINES (read first)
> 1. **"A generic spine already exists" was OVERSTATED (3/3).** The generic primitives are *embedded inside* a regulatory product. `BlockHit` carries `case_number`/`doc_family` (`block_retrieval.py:92`); `CorpusSource` returns US-state sets with "never default to OH" baked into the contract (`sources/base.py:33,44`); `span_check`'s corpus path is domain-free but its **web path pulls in the PUCO docket regex** (`verify.py:22,201`); the orchestrator loop **module-imports PUCO connector functions** (`loop.py:44-52`). Correct framing: **generic *contracts and algorithms* are extractable, but current code is entangled — we port proven algorithms under new contracts and rewrite the entangled control flow. Nothing is "already clean."**
> 2. **A 10th seam the contract MUST add: a domain-neutral GATING/ROUTING/COVERAGE policy.** Kernel control flow branches on Ohio values — `_DOCKET_RE` decides *whether the hard gate runs* (`loop.py:91-148`); `coverage_scope=="ohio_sufficient"`/`use_ingest_engine` drive the web-floor + termination (`loop.py:791-880`); `agent.py:140-200,420-495` is an OH decision-tree router + capability gate. Externalizing prompts/tools/scope-allowlists does **not** remove these.
> 3. **SECURITY gap (Rule 15):** multi-tenant/workspace isolation lives *inside* the span-check gate — a "cross-tenant FALSE-PASS guard" (`verify.py:579-595`). Tenant isolation, the atom **origin/substrate model**, a **per-run LLM cost governor** (`budget.py`), and the admin observability surface were all missing from the kernel layering. Added in §3.8/§6.
> 4. **O2 is a genuine panel SPLIT** (see §10) — Codex+Gemini: *lift-and-refactor*; code-grounded subagent: entanglement reaches loop control flow + eval math → closer to a real rewrite. Synthesized position + a decision for the user below.
> 5. **O1 [RESOLVED]: cloud-proxy ≠ guaranteed OH fetch** (3/3). F5 uses JA3/TLS + headless-JS, not just IP. Keep a **self-hosted residential worker** as a first-class egress class — but **NO legacy OH DB / bridge / pipeline carryover** (user). OH is a clean connector + `WarmedResidentialBrowserStrategy` on the generic pipeline, into the unified corpus. The new OH path is *proven by a live soak in P1* before it is relied on; there is no legacy fallback to "keep running in the meantime."
> 6. **Eval parity bar correction:** `lookup` scoring is generic/portable; **`qa` scoring is welded to the OH corpus-vs-ingest cutover** (`qa/scoring.py:12,147,269-327`) and must be **re-authored** vertical-parameterized before it can gate anything.

---

## 1. Layering

```
App / API / UI  (vertical-neutral shells; render whatever entities/deliverables a vertical declares)
Vertical packages (entry-point registered): factra_vertical_regulatory (ships) · legislative · financial (design targets)
Vertical Plug-in Contract (the SPI — §4): typed Protocols + manifest. NO kernel code names a domain noun.
Kernel (domain-agnostic — §3): ingestion · document/corpus spine · index+retrieval · research orchestrator
  (ReAct mechanics + provenance gates) · synthesis · gating/routing POLICY interface · project/registry model ·
  tenant-isolation · cost governor · eval harness mechanics · job queue/storage/breaker/observability
```
**Success invariant:** no semantic domain noun (`docket`/`utility`/`puco`/`ohio`/`state`/`case`) appears in kernel control flow, DTOs, SQL filters, gate activation, or eval math. (Today all of these do — §3 lists each site.)

## 2. Principles
1. **Code owns structure; LLM owns meaning; vertical owns vocabulary AND policy.** New: "policy" (gating/routing/coverage/authority) is *also* the vertical's, exposed to the kernel through interfaces — not inlined `if`-branches.
2. **Declared, not edited-in.** New vertical = installable package + manifest via entry points; kernel builds every registry from manifests. Keep registry *mechanisms* in-kernel (`FetcherRegistry`/`ParserRegistry`/`SourceKind` are generic in concept — `extensions/fetcher.py:87`, `models/source_kind.py:17`); move only the *registrations* + domain branches out.
3. **Port proven algorithms under contract; rewrite entangled control flow.** The ReAct mechanics, corpus-path span-check, comparison composer, retrieval fusion, cost governor, breaker, storage are production-hardened — extract them behind clean interfaces, don't reinvent. The routing/gating/coverage control flow and the qa eval math are domain-welded — rewrite them against the new policy interface.
4. **Fail safe, never heuristic-fallback** (Rule 18). Absent/abstaining vertical component → kernel abstains/quarantines.
5. **Provenance ≠ correctness.** Span-check stays provenance; semantic correctness is gold/held-out. Both preserved. **Tenant isolation is enforced at the provenance gate and is non-negotiable.**
6. **Zero external credits by default.** Every metered external effect — LLM completions, embeddings, web search — sits behind a kernel **Provider Port** with three modes: **`replay`** (offline, deterministic fixtures — the DEFAULT for all dev/CI/eval; zero credits), **`record`** (real call + persist a cassette), **`live`** (real call). Spending credits is an explicit, budgeted action — recording/refreshing cassettes, an occasional live smoke test, or real production ingestion — never the default of a test or a local run. The existing `llm/interface.py` + `llm/fake.py` (`FakeLLM`) + `eval/cassette.py`/`record_cassettes.py` (`CassetteLLM`) are the PORT basis. Embeddings additionally support a **local model** (`sentence_transformers`, already used in `snapshot_search.py`) so even *production* ingestion can be credit-free — the vector dimension is fixed at the schema level and the local-vs-hosted retrieval-quality tradeoff is validated by the retrieval eval. Docling PDF parsing is already local (free).

## 3. Kernel modules — what's genuinely reusable, what leaks, where it goes

### 3.1 Ingestion framework
- `Source` (generalizes `Commission`, keyed `commission_id`→`source_id`; `models.py:312` job FK follows): `key`, `base_url`, `transport_kind`, `rate_limit_cfg`, `status`, **`facets` JSONB** (scope tags). No `state`/`industry_filter` columns.
- `Connector` SPI (rename verbs): `discover_entities`/`list_documents`/`fetch_artifact`; `EntityRef`/`DocumentRef` = small typed head (`native_id`,`title`,`dates`,`facets`) + vertical `extra`→`raw_metadata`. (Today `CaseRef`/`FilingRef` nouns — `connectors/base.py:30,96` — are the leak.)
- **`FetchStrategy` (NEW)** framed as **egress-placement conformance** (panel): a strategy declares `egress_class` (datacenter/residential), `engine`, `warmup`, `pacing`, `session_lifetime`, `live_probe`. `HttpStrategy` / `BrowserStrategy` / `WarmedResidentialBrowserStrategy`. The scheduler places jobs on a worker pool that satisfies `egress_class`. **This makes the residential worker a first-class generic role, not a legacy bolt-on — but does NOT promise cloud-only OH (O1).** `BrowserSession` (`browser.py`, domain only in comments) is the primitive. **OH adaptation is layered, not bespoke:** the OH connector declares `WarmedResidentialBrowserStrategy(engine=firefox, warmup=homepage-F5, pacing=8s, egress=residential)`; the generic scheduler + pipeline do the rest. **No legacy `strata_rs`/bridge path exists** — OH ingests through the same discover→fetch→parse→block→embed→extract path as every state, into the unified corpus.
- Job queue / pipeline / storage / breaker — reusable in shape (SKIP-LOCKED, backoff, three-phase connectionless loop, sha256 content-addressed store, per-source token-bucket breaker). Port as-is with the `Source` rename; job-type strings become generic (`discover_entities|list_documents|fetch_artifact`).

### 3.2 Document / corpus spine
Reusable shape: `Document(sha256,content_type,facets,dates)`→`ParsedDoc(markdown_ref,parser_version)`→`Block(index,span,section_path,splitter_version)`→`BlockContent(content_key,text,tsv,embedding,signal_*)`. **Leaks to remove:** denormalized `state/native_case_number/doc_family/utility_canonical_name` on `IngestBlock` (`search_models.py:141`) AND the block-builder **prefixing indexed text with those fields** (`block_builder.py:51`) → generic indexed **`facets JSONB`** (+ vertical-declared typed facet columns), hard-filter `facets @> :filter`. **Parser is a content-type-keyed registered step** (kernel ships pdf+html; verticals add xbrl) — the abstraction must not assume PDF.
**NEW kernel concept — document VERSION LINEAGE** (panel, legislative): `Document` needs a version/supersedes relation (bill v1→v2, amended/restated filing). Not a regulatory add-on; first-class.

### 3.3a Retrieval backend [DECIDED — panel 3/3, 2026-07-30]
**Embeddings = OpenAI** (text-embedding-3-small, 1536-d default; -large/3072 optional) behind the `Embedder` port (fake/local/cassette for zero-credit dev). **Search backend = Postgres-first**, behind the `RetrievalSource` port so it's swappable:
- Build in P2: one `PostgresRetrievalSource` — `pgvector` **HNSW** (dense) + `tsvector` (lexical) + **app-level RRF fusion** (legs stay inspectable; ES/Vespa can slot in later behind the same port) + generic **`facets JSONB @>`** hard filters (no domain columns).
- Upgrade *within* Postgres first: **ParadeDB `pg_search`** for true BM25 (today's `ts_rank_cd` is not real BM25), **pgvectorscale** for filtered-ANN scale.
- Leave Postgres only on a measured wall (~tens of millions of vectors, or learned ranking) → **OpenSearch/Elastic single hybrid engine**. A dedicated vector DB is premature (dual-write/sync tax).
- Rationale: dense leg carries semantic recall so `tsvector` suffices to anchor exact terms; single datastore = no sync tax + ACID tenant isolation; the ONLY option that keeps the whole dev/CI/eval loop offline (Docker Postgres + cassette embeddings).
- **Port fixes applied (panel-caught bugs):** `FacetFilter` (value or set → `IN` semantics); a `RetrievalRequest` with **first-class mandatory `tenant_id`/`workspace_id`** (isolation is a security boundary, not a soft facet); `query_embedding` supplied by the kernel so sources don't re-embed and fusion stays app-level; `BlockHit.legs`/`extra` for per-leg provenance.

### 3.3 Index & retrieval
Keep hybrid BM25+dense+structured fusion (RRF) + rerank + the `Capability` enum. **But `BlockHit`/`CorpusSource`/`SearchContext` are NOT domain-free** — `BlockHit.case_number`/`doc_family` (`block_retrieval.py:92`), `CorpusSource.jurisdictions()/ready_states()→frozenset[state]`, `SearchContext.states`, "never default to OH" (`sources/base.py:33,44`), SQL hard-filters on `case_number/doc_family/utility_canonical_name/case_type` (`block_retrieval.py:325-344`). **Rewrite these to carry a generic `domain_metadata: dict`/`facets` instead of named domain fields**; routing reads a vertical **scope table**, not an OH decision tree. Remove hardcoded `build_registry()` + `select_sources()` (`registry.py:21-71`).

### 3.4 Research orchestrator (ReAct)
- **Port under contract (proven mechanics):** the loop scheduler, tool-dispatch, working-memory/atom model, degraded-signal handling, `search_evidence`/`precision_lookup`(+cell verifier)/`read_doc_section`/`emit_answer`. **Split `span_check`:** the **corpus/locator path (`verify.py:456-508`) is the domain-free crown jewel — port verbatim**; the **web path (`verify.py:22,201`, docket-token extraction) + `authority_floor` + the three judge prompts (`verify.py:50-55,626,956,1025`) are vertical** and move to the persona/authority pack. `span_check`'s **cross-tenant FALSE-PASS guard (`verify.py:579-595`) stays kernel — it's a security invariant.**
- **Rewrite (domain-welded control flow) against the §4 policy interface:** module-level PUCO imports (`loop.py:44-52`); the gate-activation `_DOCKET_RE`/`_question_has_bindable_dimension`/`_select_gate_needing` (`loop.py:91-148`); the coverage/web-floor/termination logic `coverage_scope=="ohio_sufficient"`/`exceeds_corpus`/`use_ingest_engine`/`_web_floor_unmet` (`loop.py:791-880`); the OH-floor router + entity→jurisdiction resolver + capability gate in `agent.py:90-200,420-495`. These are **not** prompts or data — they are kernel control flow encoding a single-corpus geographic identity.
- **Move to vertical:** the domain structured tools `query_corpus_structured`/`compare_metrics`/`monitor_filings` (`tools.py:218-347`); `_SYSTEM` prompt + all tool *descriptions* (`loop.py:431-605`) — **prompt and tool schema externalize together as one unit** (they must stay byte-consistent).

### 3.5 Synthesis & deliverables
- Keep `compose_comparison_table` (genuinely generic entities×columns + provenance + extractive verifier — `compose_comparison_table.py:198,302`), **but** make excerpt-sourcing + cell-verifier prompts vertical-configurable, and externalize the `utility_axis` pruning heuristic (`canonicalize_table_schema.py:47`) as a vertical **comparison-axis** hook.
- Keep the collective-take template system (data-driven forks). Make `DeliverableKind` register via manifest (mechanism in kernel; classes from vertical). Drafter/section-planner prompts → persona pack (builtin templates hardcode ROE/capital-structure — `builtin_templates.py:69,84`).
- **Comparison paradigm is itself vertical** (panel): regulatory=cross-entity metric table; legislative=version/amendment text-diff; financial=fact-coordinate table. The composer stays, but "what a comparison IS" is a vertical operation.

### 3.6 Project / taxonomy registries
Keep 7 data-driven registries + FK-from-`Project`. **De-domain `Project`:** `default_research_states`→generic `default_scope JSONB`; `source_fetch_policy` PUCO default→vertical (`project.py:118,166`). Project binds to active vertical(s).

### 3.7 Eval harness
Keep `lookup/scoring.py` (generic — verified). **Re-author `qa/scoring.py`** — it folds `LEGAL_SOURCE_FAMILIES` into `fully_correct` and its PRIMARY gate is corpus-vs-ingest recall + `state_bleed` welded to the OH cutover (`qa/scoring.py:12,147,269-327`). Vertical supplies gold + vocab; kernel keeps generic scoring math; the corpus/ingest-recall gate is **removed** (the unified corpus retires the substrate split). Keep the held-out invariant + adversarial trap taxonomy.

### 3.8 Kernel concerns the draft DROPPED (panel — add as first-class)
- **Tenant isolation / origin model:** atom `origin` (corpus/ingest/workspace) is load-bearing — ids collide across substrates; span-check/block-loaders/eval route by origin with FALSE-PASS/FALSE-FAIL guards (`verify.py:456-611`). The unified-corpus schema (§8) **retires** origin-routing — but workspace/BYOD tenant isolation remains a kernel security boundary and must be modeled explicitly (per-tenant scoping on every retrieval + gate).
- **Per-run LLM cost governor** (`budget.py:BudgetState`, `DEFAULT_MAX_LLM_CALLS`, reserved across gates — `loop.py:250,743,858`): kernel infra on the research path (distinct from the per-source WAF breaker).
- **Admin observability surface** (waf-breaker, pipeline-settings, DownloadMonitor): a kernel operational API, not just deploy roles.

## 4. Vertical Plug-in Contract (SPI) — expanded per panel

A vertical = installable package exposing a `VerticalManifest` via `factra.verticals` entry point. Kernel discovers all at startup. Declarations:

1. **Entity taxonomy** (types + relationships incl. **version-lineage** and parent/child).
2. **Scope / routing model** — facet dimensions, default/home scope, LLM-signal allowlist + validator (replaces `allowlists.py` + US-state routing).
3. **Gating / coverage POLICY (NEW, 10th seam)** — the domain-neutral policy the kernel calls to decide: does the hard responsiveness/dimension gate apply to this question? what constitutes a coverage gap? when is a web-floor/termination warranted? (replaces the inlined `_DOCKET_RE`/`ohio_sufficient`/`use_ingest_engine` branches).
4. **Source connectors + fetch strategies** (each declaring `egress_class` etc.).
5. **Source kinds + fetchers/extractors** (data rows + code registered by kind).
6. **Retrieval intent contract** — vertical-declared filters, boost/demotion rules, hard/soft facet semantics, and the schema the LLM emits (replaces `plan_intent.py:60`+`allowlists.py`).
7. **Retrieval source(s)** — `CorpusSource` impls + capabilities + ready-scope.
8. **Locator / citation contract** — per content-type: PDF page, HTML anchor, XBRL fact-coordinate, table cell, registry row (so span-check stays generic across verticals).
9. **Authority / gate contract** — source-class taxonomy, authority floors, sufficiency/dimension gate prompts, legal-effect/effective-date rules (replaces `authority_floor.py` + the judge prompts).
10. **Entity-resolution contract** — aliases, canonical IDs, parent/child, cross-entity contamination rules, temporal identity.
11. **Structured-fact-store contract** — units, periods, lifecycle/value dims, confidence, source priority, update/restatement semantics, and **fact-coordinate verification** (financial needs this as first-class, beyond prose span-check) (replaces hardcoded `_METRICS` — `case_issue_core.py:13`).
12. **Persona / prompt pack** — orchestrator system prompt + tool descriptions (as one unit with the tool schemas), drafter/section prompts.
13. **Structured tools + deliverable kinds + comparison-axis + change-event/monitoring semantics.**
14. **Eval gold + vocab** (held-out; scoring math stays kernel).

**Conformance suite:** kernel ships `VerticalConformance` (manifest completeness, connector round-trip, retrieval→`BlockHit`, span-check on a gold claim, tenant-isolation probe, one deliverable renders) — CI gate for any vertical.

## 5. Cross-cutting
- **Scope facets** replace US-state routing (§5.1 prior). Regulatory `{jurisdiction}`, legislative `{chamber,session,jurisdiction}`, financial `{issuer,period,form_type}`.
- **Fetch strategy = egress-placement conformance** (O1). OH baseline = residential worker; keep the remote bridge until a live OH discovery+PDF+soak passes on the new strategy.
- **Registration via manifest/entry-points** for every registry; keep the mechanisms.
- **Document version lineage + fact-coordinate identity** are kernel primitives, not regulatory extras.

## 6. Data model (clean; migration deferred)
Kernel tables (no domain columns): `source`, `ingest_job`, `document`(sha256,content_type,facets, **version/supersedes**), `parsed_doc`, `block`, `block_content`, `entity`(type,facets,relationships,temporal_identity), `project`(vertical_id,default_scope), `snapshot`(immutable), `finding`, `claim`, `deliverable`(+version), `tenant`/`workspace`(isolation boundary), registry tables, eval tables, cost-governor + breaker + observability tables. Vertical structured facts live in vertical-owned tables keyed to kernel `entity`/`document` ids. Forward-only migrations. **Unifying substrates retires the corpus/ingest/workspace origin split — call this out: it removes origin-routing but *requires* the qa eval grounding math be rewritten (§3.7), not ported.**

## 7. 3-vertical validation (panel-hardened)
| Interface | Regulatory | Legislative | Financial | Note |
|---|---|---|---|---|
| Connector verbs | dockets | bills | issuer filings | ✓ |
| FetchStrategy | http + **residential(OH)** | http | http (EDGAR) | residential only where WAF |
| Doc spine | PDF | **HTML + version lineage** | **HTML/XBRL** | parser content-type-keyed; lineage first-class |
| Scope facets | {jurisdiction} | {chamber,session} | {issuer,period,form} | ✓ |
| Comparison paradigm | cross-entity metrics | **version/amendment text-diff** | **fact-coordinate table** | composer stays; "what a comparison is" = vertical |
| Verification | prose span-check | span-check | **fact-coordinate verification** | financial needs coordinate check, not just span |
| Authority | order>testimony | enacted>introduced | audited>pro-forma; restatements | vertical authority contract |
| Monitoring | new filings | bill actions/votes | amended/current filings | change-event semantics = vertical |
| span-check corpus path / lookup eval | unchanged | unchanged | unchanged | domain-free ✓ |
| qa eval math | **re-author** | re-author | re-author | welded to OH cutover today |

## 8. Build plan
- **P0** Establish current-prod eval baselines; **re-author the qa harness to be vertical-parameterized** (prereq to any parity gate); build the AST/boot conformance tooling.
- **P1** Kernel ingestion + document spine (+version lineage, content-type parser) + job queue + FetchStrategy (incl residential egress) — prove by ingesting 2 http states + OH end-to-end into the unified corpus; OH via residential worker with a live soak.
- **P2** Index + retrieval (generic `BlockHit`/facets) + `CorpusSource` + **split span-check (corpus path)** + generic ReAct mechanics + cost governor + tenant isolation — prove by the ported **lookup** eval + a tenant-isolation probe.
- **P3** Vertical contract + manifest discovery + regulatory vertical (taxonomy, connectors, retrieval-intent, gating/coverage policy, authority pack, structured tools, persona) — prove by `VerticalConformance` + the **re-authored qa** eval at parity with captured prod baseline.
- **P4** Synthesis/deliverables + comparison-axis + project/registry + app/API/UI + admin observability.
- **P5** Legislative conformance stub (manifest + 1 connector + version-lineage case + 1 eval) — proves the seam is real (Rule 5/7). Ship regulatory only.

## 9. Deploy topology
**One deployment per vertical (O3)** — each vertical is its own Railway project + corpus DB + worker set, activating a single manifest at boot. Regulatory topology: api · http ingest-worker pool · **residential ingest-worker pool (first-class; OH + WAF states — runs the SAME generic pipeline, just on residential egress)** · index-worker · extract-worker · app-worker · admin/observability. (Financial topology drops the residential pool — EDGAR is http.) Migrations in pre-deploy. **No remote-download bridge and no legacy OH service in the topology** (O1). The residential pool's OH connector is validated by a live soak (P1) before cutover; there is no legacy pipeline to fall back to.

## 10. O2 [RESOLVED — lift-and-refactor]
User confirmed the panel's lead: **port the proven organs under contract, rewrite the domain-welded skeleton.**
- **Port under new contracts (do NOT green-field):** ReAct loop mechanics, corpus-path span-check, comparison composer, retrieval fusion, per-run cost governor, breaker/storage, lookup-eval scoring.
- **Rewrite against the §4 policy interface:** gate activation, coverage/web-floor/termination logic, the OH decision-tree router + entity→jurisdiction resolver + capability gate (`agent.py`), origin routing.
- **Re-author (not port):** the qa eval scorer → vertical-parameterized (P0, blocks the P3 parity gate).
This bounds scope and protects the eval-tuned behavior Codex + Gemini flagged, while still cleaning the control flow the code-grounded subagent showed is domain-welded.

## 11. Risks
- Rewriting proven provenance/retrieval algorithms → quality regression (2/3 panel). Mitigate: port those under contract; gate on re-authored evals.
- OH residential WAF unsolved from cloud → keep residential worker + bridge until soak passes (O1).
- Contract still leaks domain (10th-seam class) → the success invariant grep + `VerticalConformance` + P5 second-vertical stub.
- Tenant-isolation regression in a rewrite (Rule 15) → isolation probe in conformance + at the gate.
- qa parity bar unsound until re-authored → P0 blocks P3.
- Full-rewrite scope/cost blowup on a 581k-LOC system → kernel-first + port-under-contract keeps scope bounded.

## 12. Open decisions
- **O1 [RESOLVED]** residential worker retained as an egress class; **no legacy OH DB/pipeline/bridge**; OH = clean layered connector+strategy on the generic pipeline.
- **O2 [RESOLVED]** lift-and-refactor: port organs under contract, rewrite the domain-welded skeleton, re-author qa eval (§10).
- **O3 [RESOLVED]** single vertical per deployment — one manifest activated at boot; separate deployments + DBs per vertical; no runtime cross-vertical routing/isolation. Simplifies registry/scope/policy loading to deployment-level; tenant/BYOD isolation still applies within a vertical.
- **O4 [OPEN, non-blocking]** deferred-ETL scope — with O1's "no legacy OH DB," the only question is whether *historical* OH corpus/facts are ETL'd once into the unified corpus, or OH re-ingests from scratch (P1 re-ingests fresh regardless).
- **O5 [RESOLVED]** second vertical = **Financial** — forces the content-type parser (XBRL) + fact-coordinate verification, the hardest stress on the Document spine + provenance gate. Ships as a P5 conformance proof only.

## Appendix — panel provenance
Panelists: Codex GPT-5.5 (returned), Gemini 3 Pro (returned — CLI auth fixed via API key), code-grounded subagent (returned). Unanimous: "already-generic" overstated; O1 keep residential worker; contract needs more seams. Split: O2 (refactor vs rewrite). Unique-subagent: the 10th gating/routing seam, tenant-isolation-in-the-gate security gap, qa-eval-welded-to-OH-cutover, origin/substrate model, cost governor.
