# Noesis — Phased Implementation Plan (v2, panel-reviewed)

**Companion to:** `architecture-spec.md`. **Repo:** `~/noesis` (scaffolded).
**Decisions locked:** O1 clean-OH-no-legacy · O2 lift-and-refactor · O3 single-vertical-per-deployment · O5 Financial 2nd vertical.
**Panel:** Codex + Gemini 3 Pro + code-grounded subagent — all three returned; v2 folds in their corrections.
**Date:** 2026-07-29

---

## A. Approach & ground rules
- **Kernel-first, vertical as the forcing function.** Regulatory vertical proves each kernel contract.
- **Lift-and-refactor (O2), with a THIRD disposition the panel forced:** many modules are **PORT-mechanics / REWRITE-contract** — the algorithm lifts, but its data shape / DTOs / storage keys / SQL filters are domain-welded and must be rewritten. Pure "PORT" is reserved for genuinely domain-free code (verified list in §C).
- **Every phase ends at a hard gate** (an eval on the *retained* gold subset, a throughput soak, a boot check). Code-complete ≠ done.
- **Success invariant, enforced two ways** (W5): (1) a regex grep gate over the kernel for *unambiguous* domain nouns — implemented as `\bstate_code\b`, NOT bare `\bstate\b`, because "state" collides with mutation-state / circuit-breaker-state / `StateSnapshot` (panel finding — already reflected in `tools/check_kernel_invariant.sh`); (2) an **AST import-graph check** for ambiguous concepts (no kernel module imports a vertical package; "state"-like nouns judged structurally, not by regex).
- **Execution:** subagent-driven development; **judge-panel design pass before P2 and each P3 sub-phase** (security-critical span-check split + the load-bearing policy interface).
- **Definition of done (regulatory product):** re-authored qa + lookup evals at parity on the retained gold subset; all service roles boot; OH ingests via the residential strategy (multi-day throughput soak); tenant-isolation probe passes; financial conformance stub compiles; prod-shadow parity at cutover.

## B. Cross-cutting workstreams
- **W1 — Vertical Contract SPI** (`packages/kernel/noesis_kernel/contract/`): the manifest + typed Protocols. Grows per phase.
- **W2 — Conformance suite** (`.../conformance/`): one check per contract + tenant-isolation probe. CI gate.
- **W3 — Eval harness**: port `lookup` scoring; **re-author `qa`** vertical-parameterized; **persist frozen graded-answer artifacts** (prose + cited_by_origin + cited_snapshot_ids + refused + resolved_expected + law_audit) so P0 reproduction doesn't require re-running the live stack.
- **W4 — Observability/admin**: cost-governor metrics, breaker/pipeline-settings admin API, ingestion dashboards — **including replacements** for today's operator surfaces (see §C dis_client/remote-download note).
- **W5 — Success-invariant CI**: grep gate (safe nouns) + AST import-graph check (ambiguous nouns) + boot-all-roles.
- **W6 — Auth / RBAC / secrets / config (NEW)**: session + tenant mapping + org isolation (today `deps.py` + `RequireCapability.tsx`), single-vertical manifest-activation env (O3), secret injection incl. the **per-connector proxy-off** config OH needs.
- **W7 — Migrations / schema bootstrap / seeding (NEW)**: new-repo alembic harness, `create_all` bootstrap, pre-deploy wiring, the 7-registry + default-scope seeder. Un-owned in v1 — now W7 from P1.
- **W8 — Frontend architecture (NEW, its own design sub-project)**: how a vertical **declares its UI** (entity views, deliverable renderers) and how much of `web/research_system` is a generic shell vs. per-vertical components. Panel: this "rivals the kernel in complexity" — do a design pass before P4.
- **W9 — New-repo CI/CD + cutover (NEW)**: Railway service defs, committed-dist rebuild step, dual-run / traffic-shift / backfill for the prod-shadow cutover.
- **W10 — Provider ports + cassettes: ZERO-CREDIT dev posture (NEW, foundational — starts P0)**: put every metered external call behind a kernel Provider Port (`llm`, `embeddings`, `web_search`) with a `NOESIS_PROVIDER_MODE ∈ {replay, record, live}` config, default **`replay`** for dev/CI/eval. PORT the existing `llm/interface.py` + `llm/fake.py` (`FakeLLM`) + `eval/cassette.py`/`record_cassettes.py` (`CassetteLLM`) + `eval/runner.py`. Add an **embeddings port with a local `sentence_transformers` backend** (already used in `snapshot_search.py`) so ingestion/embedding costs nothing in dev — and optionally in prod (retrieval-quality tradeoff validated by the P2 retrieval eval; the pgvector dim is chosen once to match the chosen backend). Add a **web-search cassette**. **Reality check:** credits are spent ONLY to (a) record/refresh cassettes, (b) run a rare live smoke test, (c) run real production ingestion/answers — every test, eval, and local dev loop is offline and free. A CI guard fails any test that attempts a `live` call.

## C. Port / Rewrite / Discard map (v2 — panel-corrected)
Dispositions: **PORT** (domain-free lift) · **PORT-mech/REWRITE-contract** (algorithm lifts, data-shape rewritten) · **REWRITE** · **MOVE→vertical** · **DISCARD**.

| Existing module | Disposition | Notes (panel file:line) |
|---|---|---|
| `commission_ingest/breaker.py` | **PORT** | verified clean; per-source CLOSED→OPEN→HALF_OPEN, successor to the global WAF breaker (`breaker.py:6-10`) |
| `commission_ingest/browser.py` `BrowserSession` | **PORT** | domain only in comments; **but** add per-connector **proxy-off** (today `_proxy_config` injects proxy globally `:24-34` — OH needs proxy OFF) |
| `commission_ingest/storage.py` | **PORT-mech/REWRITE-contract** | sha256 dedup is clean; `readable_key(state,case_number)` keys are domain (`:38,91`) → generic facets in the key |
| `commission_ingest/queue.py` | **PORT** | generic SKIP-LOCKED job table |
| `commission_ingest/pipeline.py` (run loop) | **PORT-mech/REWRITE-contract** | 3-phase loop shell ports; **handlers rewrite** (persist `IngestCase/Filing/CaseCollection`); generic Connector SPI must keep the **4th verb `fetch_case_detail`** (`:472-484`) + **n:m case↔filing membership** (`ingest_filing_case_link`) — the genericized verb list dropped both |
| `connectors/base.py` (verbs/DTOs) | **REWRITE** | `CaseRef/FilingRef/native_case_number/discover_cases/list_filings` (`:31-102`) → generic `Connector`/`EntityRef`/`DocumentRef` + `FetchStrategy` (encoding per-op session lifetime, warm-on-reject, proxy-off) |
| `connectors/*` (ohio, indiana, …) | **MOVE→vertical** | OH gets `WarmedResidentialBrowserStrategy`; **port the OH golden config** (Firefox, homepage warm-on-reject, fresh-session-per-op, 1 concurrency, 1 job/min, proxy-off) — these are control-flow invariants, not just knobs (`ohio.py:118-121,381,571-601`) |
| `search/{parse_loop,embed_loop,reranker,classify_block}` | **PORT-mech/REWRITE-contract** | mechanics clean; strip domain assumptions |
| `search/block_builder.py` | **PORT-mech/REWRITE-contract** | strip the `state/native_case_number` **text-prefix** (`:51`) |
| `search/engine.py` + `search_models.py` | **PORT-mech/REWRITE-contract** | fusion clean; `ingest_search(states,native_case_number,doc_families)` + hard-filter `b.state` (`engine.py:7,77`) + denorm dims (`search_models.py:141`) → generic `facets` |
| `services/retrieval/dispatcher.py` | **PORT-mech/REWRITE-contract** | fusion ports; default-origin resolution rewritten |
| `services/retrieval/structured_leg.py` | **MOVE→vertical** | regulatory structured-fact retrieval (case-issue tables, metric keywords, lifecycle stages `:1,58,185`); kernel keeps only the **fusion-slot interface** |
| `retrieval/sources/base.py` `BlockHit`/`CorpusSource` | **REWRITE** | `jurisdictions/ready_states/states` + "never default to OH" (`:27,33,44,55`) → generic `facets`/`domain_metadata` |
| `retrieval/sources/registry.py`, `oh_corpus.py` | **REWRITE / DISCARD** | oh_corpus is the **default source/fallback** woven through registry/authority_floor/block_retrieval/dispatcher — replace default-origin resolution everywhere, not just the DTO |
| `retrieval/plan_intent.py`, `allowlists.py`, `authority_floor.py` | **MOVE→vertical** | retrieval-intent + authority contracts |
| `research_orchestrator/loop.py` (loop mechanics, generic tools) | **PORT-mech/REWRITE-contract** | **gate-activation (`_DOCKET_RE`, `:85-148`) + coverage/termination (`:791-880`) are INTERLEAVED in the ported functions** → the gating/coverage **policy interface must exist in P2**; **cut `loop.py:44-52` import-time PUCO imports first** or the research role won't boot |
| `verify.py` span-check `:452-454,:483-488` | **PORT** | the tiny locator-shortcut + normalized-substring check — the genuinely domain-free core |
| `verify.py` `make_origin_block_loader_v2` `:566-611` | **REWRITE** | it's the **origin router** (corpus→strata_rs SQL, ingest→doc_object_id, workspace→tenant); "retire origin routing" ⇒ rewrite to (unified-corpus loader + workspace-tenant loader). **Keep only the workspace branch (`:585-590`) as the tenant guard** — security-critical, P2 design-panel |
| `verify.py` web path, authority_floor_check, judge prompts | **MOVE→vertical** | authority/gate + locator/citation contract |
| `tool_impls.py` structured tool impls (`:1080,1234`) + `tools.py` schemas + `_SYSTEM` prompt + `SITE_REGISTRY` | **MOVE→vertical** | prompt + schemas + **implementations** move as ONE unit (impls are in `tool_impls.py`, not `tools.py`) |
| `application/commands/compose_comparison_table.py` | **PORT** | verified clean (0 domain nouns; "state" hits are mutation-state); make excerpt-source + verifier prompt vertical-configurable; `utility_axis` (`canonicalize_table_schema.py:47`) → vertical comparison-axis hook |
| collective-take templates, `builtin_templates.py` | **PORT (mech) / MOVE (content)** | template engine kernel; regulatory templates vertical |
| `extensions/{fetcher,parser}.py`, `models/source_kind.py` | **PORT (mechanism)** | registry mechanisms kernel; registrations → manifest |
| `extensions/deliverable_kinds/__init__.py` `KIND_REGISTRY` | **REWRITE (mech) / MOVE (classes)** | manifest-registered kinds |
| `services/case_issue_core.py` `_METRICS`, `case_issue_*` models | **MOVE→vertical** | extraction schema (data) + structured-fact-store |
| `budget.py` cost governor | **PORT** | verified clean (`:1-40`) |
| `llm/interface.py`, `llm/fake.py` (`FakeLLM`), `eval/cassette.py`, `eval/record_cassettes.py`, `eval/runner.py` | **PORT** | the provider-port + cassette basis for the zero-credit posture (W10) — domain-free infra |
| `services/embedder.py` (OpenAI) + `snapshot_search.py` local `sentence_transformers` | **PORT-mech / REWRITE-contract** | unify behind one embeddings port with `{local, hosted}` backends; pick pgvector dim once |
| `eval/lookup/scoring.py` | **PORT** | verified pure |
| `eval/qa/scoring.py` | **REWRITE** | welded to OH-cutover (`state_bleed`, corpus-vs-ingest recall `:171-198,269-327`) → vertical-parameterized; OH-cutover gold cases **retired/migrated**, not reproduced |
| `models/project.py` | **REWRITE** | `default_scope JSONB`, vertical source policy (`:118,166`) |
| legacy `app/{api,services,models,core,workers,main.py}` | **DISCARD** | — |
| `dis_client` | **DISCARD scraper / REIMPLEMENT callers** | not just the OH scraper — **product features** call it: `case_monitoring.py:295,478`, `threads.py:899`, `source_refine.py:185`, `fetch_source.py:647`. Monitoring + thread source-refine need reimplementation on the connector path (P3/P4 work items), not silent discard |
| `poll_sources`, `corpus_ingest_loop`, sentinel, `oh_corpus` pipeline | **DISCARD** | superseded by generic residential ingestion |
| `document_sweep`, `remote_bridge/ship`, `/admin/remote-download/*` | **DISCARD** | genuinely dark (default-OFF `rs_doc_sweep`/`rs_remote_download_bridge_enabled`) — clean discards |
| companion app, voice, active-questions, OFF-flag dead code | **DISCARD** | — |

## D. Phases

### P0 — Foundations, baselines, eval re-authoring *(critical path)*
1. Repo/CI (done: scaffold + invariant gate). Add the **AST import-graph check** (W5), the empty `VerticalConformance` runner (W2), and **the Provider Port + cassette layer (W10) with `replay` as the default + a CI guard that fails any `live` call** — this is what makes every subsequent phase's tests and evals cost zero credits.
2. **Capture prod eval baselines AND persist frozen graded-answer artifacts** (W3) — the full graded objects, not just `answer_prose` (today `results/*.json` drops them), so verdicts are reproducible offline (Rule 11: model/prompt/SHA). **This capture IS the cassette recording** (a one-time, budgeted `record`/`live` run against current prod); every eval run thereafter is `replay` = free.
3. **Re-author the qa scorer** vertical-parameterized: keep generic correctness/citation-grounding; **remove** `LEGAL_SOURCE_FAMILIES`-in-core + corpus-vs-ingest recall + `state_bleed`; **retire/migrate the OH-cutover gold cases** (their verdicts are defined by the removed gates — they cannot and should not be "reproduced").
4. Port `lookup` scorer unchanged.
**Gate (fixed):** re-authored qa reproduces frozen verdicts **on the retained vertical-agnostic gold subset only**, with a **"same verdict for same reason" diff** (not just pass/fail) + a contamination audit; OH-cutover cases explicitly retired; lookup green; grep + AST gates live.
**Risk:** the plan's original "no verdict drift on *every* case" was mathematically impossible (removed gates ⇒ guaranteed drift) — scoping to the retained subset is the fix.

### P1 — Kernel ingestion + document spine + FetchStrategy (the O1 proof)
1. **PORT/REWRITE** queue (PORT) + storage/pipeline (PORT-mech/REWRITE-contract): `Source`/`source_id`; generic Connector SPI carrying **all four verbs** (`discover_entities|list_documents|fetch_artifact|fetch_entity_detail`) + **n:m entity↔document membership**.
2. **FetchStrategy** (egress-placement) encoding **per-op session lifetime, warm-on-reject, per-connector proxy-off**; PORT `BrowserSession` + add per-connector proxy-off.
3. **Document spine** (+version/supersedes; content-type-keyed parser registry, pdf now). **Embeddings via the W10 port with a local `sentence_transformers` backend as the dev default (zero credit); pgvector dim fixed to the chosen backend.**
4. **W7:** new-repo migration/seed harness (schema bootstrap owned here).
5. Regulatory-minimal: 2 http connectors + **OH connector + golden config** on the residential worker; **scheduler egress-placement** (NEW infra — today per-state loops, not pools).
**Gate (fixed — absence-of-block ≠ liveness; the 21h deadlock produced no block):** **multi-DAY soak with a throughput FLOOR** (N docs/hr over M days), asserting fresh-session-per-op, proxy-off, breaker stability, PDF capture, dedup + version-lineage, no wedged session; boot-all-ingest-roles green; zero legacy `strata_rs`/bridge refs.

### P2 — Retrieval + provenance/tenant gate + ReAct mechanics + POLICY interface + cost governor
*(moved earlier from P3 per panel: the loop can't boot or pass the grep gate without these)*
1. **Cut `loop.py:44-52` import-time PUCO coupling first** (else research role won't boot).
2. **Define in P2 (not P3):** the gating/coverage/routing **policy interface (10th seam)**; the **origin/tenant data model + locator/citation union** (incl. a **fact-coordinate stub** so financial isn't a P5 surprise — no XBRL parser exists today).
3. **PORT-mech/REWRITE** fusion + `BlockHit`(generic facets); **span-check: PORT the substring/locator check, REWRITE the loader routing** to unified+workspace-tenant, keeping the workspace branch as the tenant guard.
4. **PORT** ReAct mechanics + 4 generic tools + `budget.py`; MOVE `structured_leg` impl to vertical (keep fusion slot).
**Gate (strengthened):** ported **lookup eval** at baseline + **facet hard-filter tests** + **provenance test per locator type** + **tenant-isolation probe** + boot research role (post import-cut). **P2 design-panel first** (span-check/tenant rewrite is security-critical).

### P3 — Vertical contract + regulatory vertical + skeleton rewrite *(SPLIT — was a hidden multi-month phase)*
- **P3a — Data/retrieval/gating contracts + skeleton rewrite:** finish scope/routing, retrieval-intent, entity-resolution, structured-fact-store contracts; rewrite the domain-welded control flow (gate activation, coverage/termination, `agent.py` OH-router + capability gate) against the P2 policy interface; MOVE connectors/allowlists/structured-fact-store to the vertical.
  **Gate:** `VerticalConformance` data/retrieval checks green; grep+AST clean (domain nouns now only in the vertical); routing/structured-leg regression tests.
- **P3b — Persona/authority/tools + qa parity:** MOVE `_SYSTEM` + tool schemas + `tool_impls` + authority/judge prompts + extraction schema; **reimplement the `dis_client` product-feature callers** (monitoring, thread source-refine) on the connector path.
  **Gate:** **re-authored qa at parity on the retained gold subset** (weak baseline caveat stated); full conformance green.

### P4 — Product surface *(SPLIT into work packages — each was hiding real effort)*
- **WP-API/Auth (W6):** apps/api + auth/session/RBAC/org-isolation (no phase defined this before).
- **WP-Frontend (W8):** the vertical-UI-declaration contract + apps/web rebuild — **its own design sub-project** (panel: complexity rivals the kernel; the current SPA has monitor/admin/RBAC routes).
- **WP-Workers/Scheduling:** dispatch, redrafts, deliverable drift, egress-placement pools.
- **WP-Migrations/Deploy (W7/W9):** per-vertical Railway defs, committed-dist rebuild, pre-deploy.
- **WP-Observability/Admin (W4):** replace remote-download/pipeline-settings/WAF-breaker/monitor operator surfaces.
- **WP-Synthesis:** compose_comparison_table (+comparison-axis), templates, deliverable kinds, `Project`(default_scope), manifest boot-activation (O3).
**Gate:** e2e flow **including auth/RBAC/org isolation, worker scheduling, admin controls, frontend route coverage, deploy health**; then **prod-shadow parity** (W9 dual-run) = definition of done.

### P5 — Financial conformance stub (prove the seam) + hardening
As spec §P5 — EDGAR (http) connector + **XBRL parser (new code)** + **fact-coordinate verification** (validates the P2 stub) + issuer/accession/period entity model + version-lineage via restatements + held-out eval cases.
**Gate:** financial passes conformance + eval with **zero kernel edits naming financial**; regulatory eval unchanged. (XBRL fixture already spiked in P2/P3 so this is fill-in, not redesign.)

## E. Sequencing
Hard chain P0→P1→P2→P3a→P3b→P4(WPs, partly parallel)→P5. **Design-panel gates:** before P2, before P3a, before P3b. W6/W7 start at P1; W8 design before P4; W9 before cutover.

## F. Verification ladder
P0 retained-subset verdict reproduction (+reason diff) · P1 multi-day throughput soak · P2 lookup + facet + per-locator provenance + tenant probe + boot · P3a routing/structured regression + conformance · P3b qa parity (retained) · P4 e2e incl auth/admin/frontend + prod-shadow · P5 cross-vertical conformance.

## G. Top de-risks before writing feature code (panel consensus)
1. **Re-scope the P0 gate** to the retained gold subset + persist frozen graded artifacts (the original gate was impossible).
2. **Reclassify the port map** to PORT-mechanics/REWRITE-contract for ingestion/search/structured retrieval; reclassify span-check to "port the check, rewrite the router."
3. **Pull the gating/coverage policy interface + origin/tenant model + locator/fact-coordinate union into P2**, and cut `loop.py` import-time PUCO coupling first.
4. **FetchStrategy must encode session-per-op + warm-on-reject + proxy-off**; P1 soak is a multi-day throughput floor, not absence-of-block.
5. **Add the missing workstreams** (W6 auth/secrets, W7 migrations/seed, W8 frontend design, W9 CI/CD/cutover) and enumerate the `dis_client` product-feature callers as reimplementation work.

## H. Resolved / open inputs
- O1/O2/O3/O5 resolved (see header). **O4 [open, non-blocking]** historical-OH ETL vs re-ingest → deferred migration spec; P1 re-ingests OH fresh regardless.

## I. Panel provenance
Codex GPT-5.5 + Gemini 3 Pro + code-grounded subagent — all returned, strongly aligned. Verified-clean PORTs: `compose_comparison_table`, `budget.py`, `browser.py`, `breaker.py`, lookup scorer. Corrections integrated: PORT-mechanics/REWRITE-contract split; span-check-is-a-router; P0-gate-impossible; policy/origin/locator→P2; loop import-time coupling; FetchStrategy operational invariants; multi-day soak; P3/P4 splits; missing W6–W9; dis_client feature-callers; `\bstate\b` grep false-positive (scaffold already uses `\bstate_code\b`).
