# Factra v2 — Phased Implementation Plan

**Companion to:** `factra-rearchitecture-spec.md` (v2, panel-reviewed).
**Decisions locked:** O1 = clean OH, no legacy DB/pipeline/bridge, OH adaptation layered on the generic pipeline. O2 = lift-and-refactor (port proven organs under contract, rewrite the domain-welded skeleton, re-author the qa eval). **O3 = single vertical per deployment** (a deployment activates exactly one vertical manifest; verticals get separate deployments + DBs). **O5 = Financial** is the second vertical (P5) — forces XBRL + fact-coordinate verification.
**Date:** 2026-07-29

---

## A. Approach & ground rules

- **Kernel-first, vertical as the forcing function.** Build the domain-agnostic kernel; the regulatory vertical is the first (and only shipping) consumer that proves each kernel contract.
- **Lift-and-refactor, not green-field.** Every "port" task starts from the named existing module, extracts it behind a clean contract, and strips the domain branch. "Rewrite" tasks replace domain-welded control flow. "Discard" = deleted, not carried.
- **Each phase ends at a hard gate** (an eval, a boot check, a soak) that must pass before the next phase depends on it. No phase is "done" on code-complete alone.
- **Every change behind the success invariant:** CI greps the kernel for semantic domain nouns (`docket|utility|puco|ohio|\bstate\b|case_number|doc_family`) and fails on a hit outside the vertical package.
- **Execution model (per CLAUDE.md):** subagent-driven development — a fresh subagent per task, code review between tasks. High-blast-radius phases (P2 span-check split, P3 gating/routing policy) get a judge-panel design pass before implementation.
- **New repo layout:** `packages/kernel/` · `packages/vertical_regulatory/` · `apps/{api,web,workers}/` · `packages/kernel/conformance/` (the `VerticalConformance` suite) · `evals/`.
- **Definition of done for the whole build:** the regulatory vertical passes the re-authored qa eval + lookup eval at parity with the captured prod baseline, all 5 service roles boot, OH ingests through the residential strategy (live soak), tenant-isolation probe passes, and a legislative conformance stub compiles against the same contracts.

---

## B. Cross-cutting workstreams (span all phases — assign an owner each)

- **W1 — Vertical Contract SPI** (`packages/kernel/contract/`): the 14 typed Protocols from spec §4, plus the `VerticalManifest` + entry-point discovery. Grows phase by phase; each kernel contract lands here first, then the regulatory vertical implements it.
- **W2 — Conformance suite** (`packages/kernel/conformance/`): one check per contract (manifest completeness, connector round-trip, retrieval→BlockHit, span-check on gold claim, tenant-isolation probe, deliverable render). Every vertical must pass; CI gate.
- **W3 — Eval harness**: port `lookup` scoring as-is; **re-author `qa` scoring** to be vertical-parameterized (remove the corpus/ingest-recall + state_bleed OH-cutover gates). Baseline capture of current prod scores is P0.
- **W4 — Observability/admin**: cost-governor metrics, WAF-breaker + pipeline-settings admin API, ingestion dashboards — built alongside the modules they observe, not bolted on.
- **W5 — Success-invariant CI + import-graph AST check**: the grep gate + a boot-all-roles check, wired from P1.

---

## C. Port / Rewrite / Discard map (grounds every phase)

| Existing module | Disposition | Target |
|---|---|---|
| `commission_ingest/queue.py`, `storage.py`, `breaker.py`, `pipeline.py` (run loop), `browser.py` | **PORT** | kernel ingestion (rename `Commission`→`Source`, `commission_id`→`source_id`) |
| `commission_ingest/connectors/base.py` (verbs/DTOs) | **REWRITE** | generic `Connector`/`EntityRef`/`DocumentRef` + `FetchStrategy` |
| `commission_ingest/connectors/*` (ohio, indiana, …) | **MOVE → vertical** | regulatory connectors; OH gets `WarmedResidentialBrowserStrategy` |
| `search/{parse_loop,block_builder,embed_loop,engine,classify_block,reranker}` | **PORT** | kernel index/retrieval (strip domain text-prefix in `block_builder:51`) |
| `search_models.py` denorm dims (`:141`) | **REWRITE** | generic `facets JSONB` (+ vertical typed facet cols) |
| `services/retrieval/dispatcher.py`, `structured_leg.py` | **PORT** | kernel retrieval fusion |
| `services/retrieval/sources/base.py` `BlockHit`/`CorpusSource` | **REWRITE** | generic `domain_metadata`/`facets`; scope-generic contract |
| `services/retrieval/sources/registry.py` `select_sources`, `oh_corpus.py` | **REWRITE / DISCARD** | scope/routing policy (registry) ; oh_corpus discarded (no legacy substrate) |
| `retrieval/plan_intent.py`, `allowlists.py` | **MOVE → vertical** | retrieval-intent contract + allowlists |
| `retrieval/authority_floor.py` | **MOVE → vertical** | authority/gate contract |
| `research_orchestrator/loop.py` (mechanics, tools dispatch, atom model) | **PORT** | kernel ReAct core |
| `loop.py` gate-activation (`_DOCKET_RE`, `:91-148`), coverage/web-floor/termination (`:791-880`) | **REWRITE** | gating/coverage policy interface |
| `loop.py:44-52` PUCO module imports; `_SYSTEM` + tool descriptions (`:431-605`) | **MOVE → vertical** | persona pack (prompt + tool schema as one unit) |
| `research_orchestrator/verify.py` corpus span-check (`:456-508`) + cross-tenant guard (`:579-595`) | **PORT** | kernel provenance gate + tenant isolation |
| `verify.py` web path (`:22,201`), `authority_floor_check`, judge prompts (`:50-55,626,956,1025`) | **MOVE → vertical** | authority/gate + locator/citation contract |
| `tools.py` `query_corpus_structured`/`compare_metrics`/`monitor_filings` | **MOVE → vertical** | vertical structured tools |
| `application/commands/compose_comparison_table.py` | **PORT** | kernel synthesis (excerpt-source + verifier prompt vertical-configurable) |
| `canonicalize_table_schema.py` `utility_axis` (`:47`) | **MOVE → vertical** | comparison-axis hook |
| collective-take template system, `builtin_templates.py` | **PORT / MOVE** | mechanism kernel; regulatory templates → vertical |
| `extensions/{fetcher,parser}.py`, `models/source_kind.py` | **PORT (mechanism)** | registry mechanisms kernel; registrations → vertical manifest |
| `extensions/deliverable_kinds/__init__.py` `KIND_REGISTRY` | **REWRITE (mechanism) / MOVE (classes)** | manifest-registered kinds |
| `services/case_issue_core.py` `_METRICS`, `case_issue_*` models | **MOVE → vertical** | extraction schema (data) + structured-fact-store |
| `budget.py` cost governor | **PORT** | kernel research-path governor |
| `tests/.../eval/lookup/scoring.py` | **PORT** | kernel eval |
| `tests/.../eval/qa/scoring.py` | **REWRITE** | vertical-parameterized qa eval |
| `models/project.py` (`default_research_states`, PUCO `source_fetch_policy`) | **REWRITE** | `default_scope JSONB`, vertical source policy |
| legacy `app/{api,services,models,core,workers,main.py}` | **DISCARD** | — |
| `poll_sources`, `document_sweep`, `remote_bridge/ship`, `corpus_ingest_loop`, sentinel, `dis_client`, `remote_download` endpoints, `oh_corpus` | **DISCARD** | superseded by generic residential ingestion (O1) |
| companion app, voice, active-questions, OFF-flag dead code | **DISCARD** | — |

---

## D. Phases

### P0 — Foundations, baselines, eval re-authoring *(blocks everything; no product code)*
**Goal:** the measuring instruments + repo skeleton exist before we build.
1. Stand up the repo layout (B) + CI: success-invariant grep gate (W5), lint/type, empty `VerticalConformance` runner (W2).
2. **Capture current-prod eval baselines** — run today's `lookup` + `qa` evals against prod, freeze the scores as the parity bar (record model/prompt/SHA per Rule 11).
3. **Re-author the qa scorer** vertical-parameterized: keep the generic correctness/citation-grounding math; remove `LEGAL_SOURCE_FAMILIES`-in-core, the corpus-vs-ingest recall gate, and `state_bleed`; expose gold + vocab + a `grounded-in-scope` check via the (stub) vertical. Prove it reproduces the frozen baseline verdicts on the existing gold set.
4. Port the `lookup` scorer unchanged; wire both into W3.
**Gate:** re-authored qa eval reproduces the P0-frozen pass/fail on every existing gold case (no verdict drift); lookup eval green; CI grep gate live.
**Dependency:** none. **Risk:** qa re-author changes a verdict → investigate before proceeding (the eval is the contract).

### P1 — Kernel ingestion + document spine + FetchStrategy (incl. residential OH) *(the O1 proof)*
**Goal:** a generic pipeline that ingests any source into the unified corpus, and proves OH works cleanly with no legacy carryover.
1. **PORT** queue/storage/breaker/pipeline-run-loop → kernel `ingestion/` with `Source`/`source_id` rename; job types genericized (`discover_entities|list_documents|fetch_artifact`).
2. **REWRITE** the `Connector` SPI + `EntityRef`/`DocumentRef` (generic head + `extra`); **NEW** `FetchStrategy` (egress-placement: `egress_class/engine/warmup/pacing/session_lifetime/live_probe`); **PORT** `BrowserSession`.
3. **Document spine:** `Document`(sha256, content_type, facets, **version/supersedes**) → `ParsedDoc` → `Block` → `BlockContent`; **content-type-keyed parser registry** (ship pdf; html stubbed for P4/vertical-2). Strip domain text-prefix from block builder.
4. **Vertical (regulatory) minimal:** implement 2 http-state connectors + the **OH connector with `WarmedResidentialBrowserStrategy`** (Firefox, F5 homepage warm-up, cookies, 8s pacing, residential egress). Register via manifest (W1).
5. **Residential worker role** in `apps/workers` + scheduler egress placement (W4 dashboards).
**Gate (the O1 soak):** 2 http states + **OH end-to-end** (discover→fetch→parse→block→embed) into the unified corpus from the residential worker; sustained OH soak (multi-hour, no WAF block, dedup working); zero references to legacy `strata_rs`/bridge. Boot-all-ingest-roles green.
**Dependency:** P0. **Risk (O1):** OH WAF still blocks from residential worker → tune strategy (engine/warmup/pacing) before declaring the path viable; do NOT reintroduce the legacy bridge.

### P2 — Kernel retrieval + provenance gate + ReAct mechanics + cost governor + tenant isolation
**Goal:** the generic evidence engine and research loop mechanics, domain-free, provable on the lookup eval.
1. **PORT** hybrid fusion (dispatcher + structured_leg) + reranker + `Capability`; **REWRITE** `BlockHit`/`CorpusSource`/`SearchContext` to carry generic `facets`/`domain_metadata` (no `case_number`/`state`); hard-filter `facets @> :filter`.
2. **Split `verify.py`:** **PORT** the corpus/locator span-check + the **cross-tenant FALSE-PASS guard** into the kernel provenance gate; leave web/authority/judge paths for the vertical (P3). Define the **locator/citation contract** (PDF page now; HTML/XBRL/table-cell/registry-row stubs).
3. **PORT** ReAct loop mechanics, tool dispatch, atom model, the 4 generic tools (`search_evidence`/`precision_lookup`(+cell verifier)/`read_doc_section`/`emit_answer`); **PORT** `budget.py` cost governor.
4. **Tenant isolation** modeled explicitly: per-tenant scoping on every retrieval + at the gate (`tenant`/`workspace` boundary in the data model).
**Gate:** ported **lookup eval** passes at P0 baseline against the unified corpus (regulatory gold); **tenant-isolation probe** in W2 passes (a workspace atom cannot ground a claim in another tenant's corpus); boot research role green; kernel grep gate clean.
**Dependency:** P1. **Design-panel pass first** (span-check split is high-blast-radius provenance/security code).

### P3 — Vertical contract completion + regulatory vertical + gating/routing policy *(the parity proof)*
**Goal:** the full plug-in contract exists and the regulatory vertical drives the loop to qa-parity.
1. **Contract (W1) completion:** scope/routing model, **gating/coverage policy (10th seam)**, retrieval-intent contract, authority/gate contract, entity-resolution contract, structured-fact-store contract (+ fact-coordinate verification hook), persona pack (prompt + tool schemas as one unit), structured tools, comparison-axis, change-event/monitoring, eval gold/vocab.
2. **REWRITE** the domain-welded skeleton against the policy interface: gate activation (was `_DOCKET_RE`), coverage/web-floor/termination (was `ohio_sufficient`/`use_ingest_engine`), the `agent.py` OH-router + entity→jurisdiction resolver + capability gate → generic router reading the vertical scope table. **DISCARD** origin routing (unified corpus).
3. **MOVE → regulatory vertical:** connectors (done P1) + retrieval-intent + allowlists + authority_floor + judge prompts + `_SYSTEM` + tool descriptions + structured tools + extraction schema (`_METRICS`→data) + `case_issue_*` fact store + web `SITE_REGISTRY`.
**Gate:** **re-authored qa eval at P0 parity** on the regulatory vertical; `VerticalConformance` fully green for regulatory; success-invariant grep clean (all domain nouns now live only in `packages/vertical_regulatory/`).
**Dependency:** P2. **Design-panel pass first** (the gating/routing policy interface is the load-bearing abstraction).

### P4 — Synthesis, deliverables, project model, API/UI, observability
**Goal:** the full product surface on the kernel.
1. **PORT** `compose_comparison_table` (excerpt-source + verifier prompt vertical-configurable) + **MOVE** comparison-axis to vertical; **PORT/MOVE** collective-take templates (mechanism/regulatory); **REWRITE** deliverable-kind registration → manifest.
2. **REWRITE** `Project` (`default_scope JSONB`, vertical source policy); wire the 7 registries. **O3 — single vertical per deployment:** the deployment **activates exactly one vertical manifest at boot** (env/config), so scope/registry/prompt/tool loading is *deployment-level*, not per-request; no runtime multi-vertical routing or cross-vertical registry isolation. All projects in a deployment share that vertical. (Tenant/workspace isolation from P2 still applies *within* the vertical for BYOD.)
3. **apps/api + apps/web:** vertical-neutral shells rendering declared entities/deliverables; **W4** admin/observability (WAF-breaker, pipeline-settings, ingestion dashboards, cost metrics).
**Gate:** end-to-end product flow on regulatory (create project → ingest → ask/orchestrator → deliverable draft → comparison table → monitoring); all service roles boot; single-vertical activation verified (a second manifest present but inactive changes nothing); conformance still green.
**Dependency:** P3.

### P5 — Financial vertical conformance stub (prove the seam is real) + hardening
**Goal:** demonstrate the abstraction holds for **financial** (O5) — the hardest stress test — without shipping it.
1. **Financial manifest + EDGAR connector** (`HttpStrategy` — EDGAR is http, **no residential worker needed**, so the fetch layer is exercised on the easy path while the *data model* is exercised on the hard path).
2. **XBRL content-type parser** (validates the content-type-keyed parser registry from P1/P3 — structured data, not prose/PDF).
3. **Fact-coordinate verification** (validates the structured-fact-store + locator/citation contracts from P2/P3): financial facts are identified by coordinate — `CIK/accession/statement/period/unit/decimals/context_ref` — and verified against the XBRL fact, not just a prose span. **Version-lineage** exercised via amended filings/restatements.
4. Financial entity model: `issuer(CIK) → filing(accession, form_type) → period`; scope facets `{issuer, period, form_type}`.
5. 1+ held-out eval case (a `value` lookup + a `refuse` case) through the re-authored qa + lookup harnesses.
6. Run `VerticalConformance`; **fix any kernel contract that turns out secretly regulatory** (the point). Hardening: soak, cost-budget tuning, deferred-ETL migration-spec kickoff (O4).
**Gate:** financial vertical passes conformance + its eval cases against the SAME kernel with **zero kernel edits that name financial** (the success invariant holds for a 2nd domain); regulatory eval unchanged. **De-risk earlier:** the XBRL/fact-coordinate hooks are *designed* (stubbed) in P2 (locator/citation) and P3 (structured-fact-store) precisely because financial is the confirmed 2nd vertical — P5 fills stubs, not redesigns.
**Dependency:** P4. Ship **regulatory only**; financial stays a conformance proof until its own build.

---

## E. Sequencing, dependencies, parallelism
- Hard chain: **P0 → P1 → P2 → P3 → P4 → P5.**
- Parallelizable within: P1 http-connectors ∥ OH-strategy ∥ document-spine; P2 retrieval ∥ ReAct-mechanics (join at the gate); P3 contract-items fan out per seam.
- W1–W5 run continuously; W3 (qa re-author) is the P0 critical path; W2 grows one check per phase.
- **Panel design-pass gates:** before P2 (span-check split), before P3 (gating/routing policy). Before P1's OH-strategy if the first residential soak fails.

## F. Verification ladder (strongest per phase — Rule 16)
P0 eval-verdict reproduction · P1 live OH soak + boot · P2 lookup eval + tenant probe · P3 qa parity + conformance · P4 e2e product flow · P5 cross-vertical conformance. **Prod-shadow** after P4 cutover is the definition of done for the regulatory product.

## G. Risks & checkpoints
- **qa re-author drifts a verdict (P0)** → the eval is the contract; stop and reconcile.
- **OH residential soak fails (P1)** → tune strategy; escalate to panel; never reintroduce legacy bridge.
- **A "port" turns out domain-welded on contact** → reclassify to "rewrite," design-panel the seam.
- **Kernel grep gate flags a leak late** → the seam wasn't cut; fix before the phase gate, not after.
- **Scope creep** → kernel stays minimal; anything domain goes to the vertical; the conformance suite is the arbiter.
- **Rollback:** the current prod system remains live and untouched throughout; cutover is a P4 event gated on prod-shadow parity.

## H. Remaining inputs
- **O3 [RESOLVED]** single vertical per deployment → P4 activates one manifest at boot; separate deployments + DBs per vertical; no runtime cross-vertical isolation needed.
- **O5 [RESOLVED]** Financial is the 2nd vertical → P5; its XBRL + fact-coordinate hooks are pre-designed in P2/P3.
- **O4 [OPEN, non-blocking]** historical-OH ETL vs re-ingest → deferred migration spec; P1 re-ingests OH fresh regardless, so this only affects whether pre-existing OH facts are back-filled to save re-extraction cost.

## I. Design implications of the two new decisions
- **Single-vertical-per-deployment (O3)** simplifies the kernel: vertical activation is a boot-time config, registries load once, and the "10th seam" gating/routing policy resolves against one vertical — not a per-request dispatch. It does **not** relax the success invariant (kernel still names no domain noun) or tenant isolation (BYOD workspaces still isolate within a deployment). Financial and regulatory each get their own Railway project + corpus DB + workers.
- **Financial-second (O5)** front-loads the two hardest kernel contracts — the **content-type-keyed parser** (XBRL ≠ PDF) and **fact-coordinate verification** (structured fact identity ≠ prose span-check). Designing their stubs in P2/P3 (not deferring to P5) is what keeps P5 a fill-in rather than a redesign; EDGAR being http means the fetch layer stays on the easy path, isolating the stress to the data/verification model where the real generalization risk lives.
