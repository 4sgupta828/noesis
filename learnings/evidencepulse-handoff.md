# Evidence Pulse — Handoff: what's built, what remains, and how to build it

**Audience:** the next engineer/agent picking this up cold.
**Companion docs:** `learnings/evidencepulse.md` (the panel-reviewed spec v2.1 — its Panel
Amendments A1–A7 override the body where they conflict; read it first) ·
`learnings/engineprimitives.md` (the answer-engine design this plugs into).
**Status date:** 2026-08-10 (updated same day, post supersession-E2E). Everything in "BUILT"
below is deployed and prod-verified — including the FIRST REAL SUPERSESSION, end to end.

---

## 1. One-paragraph orientation

Evidence Pulse is the **corpus-currency subsystem**: change detection over the evidence corpus
(supersessions, retractions, label changes), an auditable event ledger, and three consumers —
(1) the answer engine (superseded sources demoted, retracted sources excluded from grounding),
(2) per-user watches/inbox with per-topic rolling-window activity, (3) a public what-changed feed.
It is deliberately **domain-generic** (spec A7): all mechanism lives in
`packages/kernel/noesis_kernel/currency/`; all judgment (what supersedes what, what a topic is)
comes from the vertical via prompts/declared data. The medical vertical is the proving instance;
the same kernel is meant to serve any vertical (regulatory, legal, enterprise docs — "change
management over a dense corpus over time").

## 2. What is BUILT (map, so you don't rebuild it)

### Kernel (`packages/kernel/noesis_kernel/currency/store.py` — `CurrencyStore`)
- `noesis_change_event` — the SOURCE OF TRUTH. Typed relations: `superseded_by · retracted ·
  amended_by · clarified_by`; status: `shadow → approved → retracted_event`; idempotent on
  (relation, old, new); re-record enriches EMPTY `subjects` only, never touches status/audit.
- Derived block stamps: approved events stamp `facets.superseded_by` / `facets.retracted` onto the
  old document's rows in `rs_block`. Stamps are a CACHE — re-ingest overwrites facets, so
  `apply_stamps()` re-derives from the ledger (runs after every gap-queue ingest job + manually
  via `POST /admin/pulse/scan`). `retract` un-stamps and is never resurrected by a re-sweep.
- `noesis_topic` — the CANONICAL TOPIC REGISTRY. **Stability contract:** LLM calls are shown the
  registry and must prefer exact verbatim reuse; a novel topic is minted ONCE (`ensure_topics`,
  case/whitespace-insensitive) and becomes the stable form for all later runs/users. Seeded from
  the vertical's covered-condition names on first use.
- `noesis_watch` / `noesis_watch_seen` — per-user watches + seen tracking; `inbox_summary()`
  (per-topic unseen/in-window rollup), `events_for_topic()` (containment matching),
  `docs_first_seen()` (time-axis window query).

### Corpus time axis (`packages/kernel/noesis_kernel/retrieval/postgres.py`)
- `rs_block.created_at` (additive, indexed). Pre-existing rows are NULL = unknown age, **honestly
  excluded** from windows — never backfill fake dates. Every ingest from 2026-08-10 onward is dated.
- Clean-replace on re-ingest (`delete_stale_blocks`, wired in
  `retrieval/materialize.py::materialize_to_postgres`) — fixes the mixed-edition bug (content-
  addressed block ids meant an edited document kept BOTH editions' rows forever). Upserts also
  refresh `document_title`/`content_type`/`source_key` on conflict.

### Detection sources
- **Curator-declared lineage** (zero-LLM, highest confidence → auto-approved):
  `global_guidelines.py::declared_lineage()` reads registry entries carrying
  `"supersedes": "<old-entry-id>"` / `"retracts": true`. **EDITION IDENTITY POLICY** (comment in
  that file, non-negotiable): a new guideline edition is a NEW year-scoped registry entry
  declaring `supersedes`; NEVER edit an existing entry's url/year in place (same registry id →
  same `document_id` → the pair that detection needs never exists).
- **Retraction detector** (structural, zero-LLM):
  `packages/vertical_medical/noesis_vertical_medical/retractions.py` — batched Europe PMC
  `PUB_TYPE:"Retracted Publication"` lookups over held `europepmc:*` document ids; returns
  {ext_id: title} (title becomes the event subject). Auto-approved (publisher-declared fact).
  First prod run found 4 genuinely retracted papers; their blocks are excluded from grounding.

### Ranking integration (`research/react.py`, `retrieval/postgres.py`)
- Retrieval: `currency_demote=True` (fed by the flag) drops `retracted` hits and stable-partitions
  `superseded_by` hits to the bottom of the candidate pool.
- Claim selection (`_rank_claims_by_relevance`): superseded/retracted-source claims are sort-
  partitioned below current ones **unconditionally** — including the `len(claims) <= top`
  early-return path (a panel-caught trap), implemented as a partition because the function is
  otherwise boost-only and a negative additive term can't express a hard fact.

### API (`apps/api/app.py`)
- Admin (X-Admin-Token): `POST /admin/pulse/scan` (declared sweep + re-stamp, idempotent),
  `POST+GET /admin/pulse/retraction-scan` (BACKGROUND task — a sync scan outlives the edge's
  request window and gets its response cut; status is per-replica, ledger is shared),
  `GET /admin/pulse/events`, `POST /admin/pulse/event` {approve|retract}.
- User (x-noesis-token): `POST/DELETE /pulse/watch` (manual adds are LLM-canonicalized against the
  registry, response returns `stored_as`), `GET /pulse/inbox` (per-topic summary), `GET
  /pulse/topic-activity?topic&days` (topic-as-query: existing retrieval finds relevant docs, time
  axis filters to the window — one embedding, zero LLM), `POST /pulse/topics` (watch picker
  suggestions for one Q&A), `GET /pulse/watch-suggestions` (cross-session, from the user's own
  question history), `POST /pulse/seen`.
- Public: `GET /pulse/recent` (approved events; rendered on the coverage page as 'What changed recently').

### FE (`apps/web/index.html`)
- Gold "◉ Pulse" header button + unseen badge (`maybeShowPulseBell` — shows whenever the flag is
  on; tokenless click opens the sign-in gate). Panel v3: per-topic rows → lazy expansion showing
  Changes + New-sources timeline; NL add with "✓ added as …"; cross-session suggestion chips
  (cached: max one suggestion call per page visit). "⊕ Watch topic" picker on answers (canonical
  chips + free text). Structural answer-integrity banner: cited document_id ∩ event
  old_document_id → "Evidence has changed since this answer" (fires mostly on past sessions).

### Flags / config
- `NOESIS_PULSE` env flag (static, default OFF; currently ON in prod). OFF = no ledger, no stamps,
  no demotion, no UI — true no-op. `/config` echoes `pulse_enabled`.

### Also built (added after the first handoff draft)
- **THE FIRST REAL SUPERSESSION PAIR — E2E-verified in prod.** KDIGO Anemia 2012 re-ingested as
  its own edition entry (`kdigo-anemia-2012-fulltext`); the 2026 entry declares `supersedes`.
  Verified live: scan → approved `superseded_by` event → stamps → RETRIEVAL DEMOTION (search
  "ESA therapy hemoglobin target anemia CKD": 2026 holds top positions, 2012 absent from top-8,
  yet still in the corpus per demote-never-delete) → event leads the public feed.
- **Subject facets on guideline blocks** (A5 prerequisite done): `_facets` now carries
  `conditions`; both anemia editions ingested with them (older guideline docs get facets on their
  next re-ingest).
- **Shadow supersession judge deployed** (`POST/GET /admin/pulse/detect`, background): structural
  candidate pairing in `currency/candidates.py` (same issuer + overlapping subjects + different
  years; decided pairs excluded; held-out pairing tests) → vertical `SUPERSESSION_JUDGE_PROMPT` →
  SHADOW events only (confidence "judge"); human approval via the existing event endpoint is the
  ONLY path to stamps. Never yet run against prod (see §3.2).
- **Weekly automatic retraction sweep** on the ingest thread's idle path (DB clock
  `last_retraction_sweep` in `noesis_pulse_state` — replica-safe, free).
- **DB-backed scan statuses** (`noesis_pulse_state`) — the per-replica "never_run" quirk is fixed.
- **Coverage page renders `/pulse/recent`** ("What changed recently" section on admin.html).
- **Panel v3 per-topic activity**: corpus time axis (`rs_block.created_at`), per-topic rolling
  window (`/pulse/topic-activity` — topic-as-query + time filter), per-topic rows with lazy
  expansion, canonical topic registry (`noesis_topic`, seeded, stability contract), NL add with
  server canonicalization, cross-session watch suggestions.
- (Adjacent, not Pulse: sessions now carry a `real_patient` flag — orange ◉ marker in the session
  list, toggle in the session toolbar, `POST /sessions/{id}/patient-flag`.)

### Verification state (honest)
- Unit: ledger lifecycle, claim partition (incl. early-return), clean-replace, detector batching/
  titles/doc-id mapping, registry canonical-wins, edition-candidate pairing. DOM harness: all
  panel/picker/banner/row behaviors.
- Prod: retraction sweep on real corpus (4 events) · watch→inbox→seen E2E · topic-activity E2E ·
  **full supersession loop E2E (scan → event → stamps → retrieval demotion → public feed)**.
- NOT yet exercised: the LLM judge against prod (§3.2); `new_documents` windows are cold-starting
  (time axis began 2026-08-10; only newly-ingested docs are dated).

---

## 3. REMAINING WORK (priority order, each with design + acceptance)

### 3.1 The change-brief composer — DELIBERATELY DEFERRED by the product owner
Do not build without an explicit go. Events carry empty `brief_md` — the inbox shows *that*
something changed, not *what*. When green-lit: compose on event APPROVAL from the new (and old)
document's blocks, every claim through the EXISTING span-verification gate; verification failure →
approved event, empty brief, retry next scan; NEVER an unverified brief. Vertical prompt in
`pulse.py`; backfill via `/admin/pulse/scan`. Acceptance: the rosacea retraction and the KDIGO
supersession both carry cited briefs whose quotes locate; a corrupted quote is rejected (fake-LLM
unit test).

### 3.2 First REAL run of the supersession judge + its held-out gates
The judge is deployed (shadow-only, `/admin/pulse/detect`) but has never run against prod, and its
LLM verdicts have no eval coverage yet. Before trusting it on real candidates:
- Wire the spec's three held-out cases as tests (recorded/fake LLM): true pair (KDIGO 2012 vs 2026
  anemia) → supersedes; translation/reprint of one edition → NO; adjacent-but-distinct (KDIGO CKD
  vs KDIGO BP-in-CKD) → NO.
- Then one admin-triggered prod run (`POST /admin/pulse/detect`; cost ≈ 1 small call per candidate;
  today's candidate count is tiny — most old guideline docs lack `conditions` facets until
  re-ingested). Review shadow events at `/admin/pulse/events?status=shadow`; approve/reject via
  `/admin/pulse/event`. The declared KDIGO pair is already decided, so a correct run should mostly
  find nothing — that null result is itself the first precision datum.

### 3.3 Label-change detector (structural; second real detector)
DailyMed/openFDA re-ingests silently replace label content — and clean-replace now DELETES the old
rows, so the diff must be computed BEFORE deletion (inside `materialize_to_postgres`'s clean-replace
step, which knows old vs new block sets). Emit `amended_by` candidates when actionable sections
(boxed warning / contraindications / dosing — SPL section identification is structural) change;
cosmetic reflow emits nothing. Ledger supports empty `new_document_id`; extend additively if a
version marker is needed. Acceptance: a label fixture with an added boxed warning → exactly one
event naming the section; reflow → none.

### 3.4 Answer-currency surfaces now UNBLOCKED by the real pair
- **Superseded-title annotation**: verify the compose path actually carries document titles into
  findings (panel flagged this as unreliable), then append "[superseded by <new> (<year>)]" so a
  deliberately-cited old edition can never read as current.
- **Currency chip on fresh answers**: "◉ guidance in this area changed <month>" when an answer's
  cited docs/subjects intersect recent events — the structural sibling of the past-session
  integrity banner. Both are small now that a live supersession exists to test against.
- Also verify the claim-stage partition on a REAL answer citing both editions (retrieval demotion
  is prod-proven; the claim-stage path has unit coverage only).

### 3.5 Digest delivery (P2 — only after precision is proven)
Weekly email of `major` events on watched topics. Needs a mail provider (none integrated), opt-in,
hard item cap, and human-approved events only until the held-out precision gates hold. CME wrapper
and institutional dashboards further out.

### 3.6 Hygiene / smaller items
- **Judge candidate coverage**: older guideline documents lack `conditions` facets until
  re-ingested — a one-time re-ingest sweep of the guideline registry would give the judge a real
  candidate pool.
- **Inbox matching upgrade**: containment misses paraphrases ("HFpEF" vs the spelled-out subject).
  The registry narrows it; the principled fix is embedding-similarity gate + LLM confirm for
  borderline, batched at digest cadence, precision-biased.
- **Watch-data privacy (spec A6)**: retention statement + deletion on account removal (no
  account-deletion flow exists yet either).
- **`new_documents` cold start**: time axis began 2026-08-10; windows fill organically. Never
  backfill dates.
- **Periodic judge/declared sweeps**: retractions are weekly-automated; declared-lineage scan still
  manual after re-ingests (the per-job hook re-stamps, but new registry declarations need one
  `/admin/pulse/scan`) — could join the weekly idle-path clock.

## 4. Invariants you must not break (hard-earned)
1. **Ledger over stamps** — never treat block facets as the truth; anything that rewrites facets
   must be followed by `apply_stamps()` (the ingest hook does this; keep it).
2. **Demote, never delete** — superseded evidence remains retrievable (it's the brief's citation
   base and sometimes the only source for an unrevised topic). Only `retracted` is excluded.
3. **Edition identity policy** — new editions are NEW registry entries. Editing an entry in place
   destroys the old/new pair silently.
4. **Approval gates anything user-visible** (A4): declared/publisher facts auto-approve; LLM
   judgments are shadow until a human approves. One-click retract must always work.
5. **Stability contract on topics** — every LLM touching topics sees the registry and prefers
   exact reuse; never mint variants.
6. **Rule 18 split** — kernel = mechanism (joins, stamps, time windows, containment); vertical =
   judgment (prompts, declared lineage, seeds). No semantic regex heuristics anywhere.
7. **Rule 20** — everything rides `NOESIS_PULSE` (OFF = byte-identical no-op); new risky surfaces
   get their own flag.
8. **Cost discipline** — LLM calls only on user action or rare ingest events; suggestion calls are
   cached per page visit; detection is structural wherever the fact is structural.

## 5. Operational runbook
- After ANY bulk re-ingest: `POST /admin/pulse/scan` (idempotent re-stamp; the per-job hook covers
  queue ingests automatically).
- Retraction sweep: `POST /admin/pulse/retraction-scan` (background; poll the GET; events land in
  the shared ledger regardless of which replica ran it). Free (Europe PMC API).
- Wrong event shipped: `POST /admin/pulse/event {"event_id": "...", "action": "retract"}` —
  un-stamps immediately, survives future sweeps.
- Flag off (kill switch): unset `NOESIS_PULSE` env in Railway → redeploy; UI, endpoints, and
  demotion all vanish; the ledger data is retained.
- Test account for E2E: `pulse-e2e-test@noesis.dev` (register endpoint re-issues its token).

## 6. Suggested sequencing for the next builder
1. 3.2 judge eval gates + one reviewed prod run (cheap; produces the first precision data).
2. 3.6 guideline re-ingest sweep (gives the judge a real candidate pool; also refreshes facets).
3. 3.4 answer-currency surfaces (small, unblocked, user-visible).
4. 3.3 label-change detector.
5. 3.1 brief composer — ONLY once the owner green-lights it.
6. 3.5 digests only after precision is demonstrated; hygiene items as you touch each area.
