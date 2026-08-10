# Evidence Pulse — Handoff: what's built, what remains, and how to build it

**Audience:** the next engineer/agent picking this up cold.
**Companion docs:** `learnings/evidencepulse.md` (the panel-reviewed spec v2.1 — its Panel
Amendments A1–A7 override the body where they conflict; read it first) ·
`learnings/engineprimitives.md` (the answer-engine design this plugs into).
**Status date:** 2026-08-10. Everything in "BUILT" below is deployed and prod-verified.

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
- Public: `GET /pulse/recent` (approved events; the coverage-page rendering of it is NOT built).

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

### Verification state (honest)
- Unit: ledger lifecycle, claim partition (incl. early-return), clean-replace, detector batching/
  titles/doc-id mapping, registry canonical-wins. DOM harness: all panel/picker/banner behaviors.
- Prod: retraction sweep on real corpus (4 events), watch→inbox→seen E2E, topic-activity E2E.
- NOT yet exercised anywhere: a real supersession pair end-to-end (none exists yet — see §3.4).

---

## 3. REMAINING WORK (priority order, each with design + acceptance)

### 3.1 The change-brief composer (biggest content gap; LLM, ~1 call per event)
Events carry empty `brief_md`/`brief_claims`. The inbox shows *that* something changed, not *what*.
- **Design (spec "LLM contracts #2"):** on event APPROVAL (not creation — shadow events get no
  brief), compose "what changed / what it means for practice / what it replaced" from the NEW
  document's blocks (and old's, for supersessions). Every claim must pass the EXISTING span-
  verification gate (reuse the kernel verifier — see `research/react.py` claim verification; the
  brief's quotes must be locatable in the source blocks). Verification failure → event stays
  approved with empty brief + retry next scan; NEVER ship an unverified brief.
- **Touchpoints:** vertical prompt in `noesis_vertical_medical/pulse.py`; manifest field;
  compose+verify helper in kernel `currency/` (mechanism) called from the approval path and a
  backfill admin trigger; FE already renders `brief_md` when present.
- **Acceptance:** the rosacea retraction event carries a cited brief whose quotes locate in the
  retraction notice/paper record; a deliberately corrupted quote is rejected (unit test with fake
  LLM); briefs backfill via `/admin/pulse/scan` for the 4 existing events.

### 3.2 LLM supersession judge (shadow-first; prerequisite A5 below)
Auto-detect edition pairs beyond curator declaration.
- **Prereq (spec A5):** guideline blocks lack subject facets (conditions live only in the
  connector registry). Add `conditions`→facets stamping in `global_guidelines.py::_facets` (and
  india_guidelines) + re-ingest, OR build a doc-metadata view. Candidate generation needs
  (issuer, subjects, year) per document.
- **Design:** periodic sweep (admin-triggered first): candidates = same issuer + overlapping
  subjects + different years, guideline tier only. LLM judge → {supersedes, materiality,
  subjects}; events recorded as **shadow**; admin approves via the existing queue (spec A4 —
  unanimous panel requirement; do NOT auto-approve judge output). Chains stamp each edition with
  its immediate successor. Partial supersession (one chapter) → `minor`, no stamp.
- **Held-out eval BEFORE trusting (spec eval section):** (a) true pair (KDIGO 2012 vs 2026 anemia)
  → supersedes; (b) translation/reprint of the same edition → NO; (c) adjacent-but-distinct
  (KDIGO CKD vs KDIGO BP-in-CKD) → NO. Wire as unit tests with recorded/fake LLM responses plus
  a small live-judged set. The judge does not ship to auto-run until these pass.
- **Cost:** ~1 small call per candidate pair; guideline ingests are a handful/week.

### 3.3 Label-change detector (structural; second real detector)
DailyMed/openFDA re-ingests silently replace label content (clean-replace now makes the old
version vanish). Detect actionable-section changes → `amended_by` events.
- **Design:** at ingest time (or a diff sweep), compare the new label's actionable sections
  (boxed warning / contraindications / warnings / dosing — SPL section codes are structural)
  against the previous version's blocks BEFORE clean-replace deletes them. Simplest robust order:
  compute the diff inside `materialize`'s clean-replace step (it knows old vs new block sets), emit
  a candidate; materiality of the section change can start structural (which section changed) with
  an LLM materiality judge later. Note: label events are `amended_by` with old==new document id —
  the ledger supports empty `new_document_id`; consider a `version` field in `subjects` or extend
  the schema additively if needed.
- **Acceptance:** re-ingesting a label fixture with an added boxed warning yields exactly one
  `amended_by` event naming the section; a cosmetic reflow yields none.

### 3.4 First real supersession pair + the answer-currency surfaces that wait on it
The demotion machinery is live but has never seen a real pair (declared lineage list is empty).
- **Action:** next time ANY watched guideline updates (or deliberately: re-add KDIGO 2012 Anemia
  as `kdigo-anemia-2012-fulltext` and mark the 2026 entry `"supersedes"` it), follow the edition
  policy, run `/admin/pulse/scan`, then verify end-to-end: old blocks stamped → a question on the
  topic cites the new edition (or names the old as prior) → `/pulse/recent` shows the event.
- **Then build the two deferred surfaces:** (a) superseded-title annotation ("[superseded by …]")
  — verify the compose path actually carries document titles into findings first (panel flagged
  this as unreliable); (b) the answer-page currency chip ("◉ guidance in this area changed
  <month>") — subject-level match between an answer's cited docs/subjects and recent events
  (the integrity banner's structural sibling, for FRESH answers).

### 3.5 Coverage-page rendering of `/pulse/recent`
The public feed is raw JSON. Render "What changed this month" on `apps/web/admin.html` (coverage
page) — titles, relation badges, dates, briefs when 3.1 lands. Pure FE, ~an hour.

### 3.6 Digest delivery (P2 — only after precision is proven)
Weekly email of `major` events on watched topics. Needs: a mail provider (none integrated),
per-user digest opt-in, hard item cap, and the spec's launch condition — human-approved events
only until the held-out precision gates hold. The in-app inbox is deliberately the only push-free
channel until then. CME wrapper and institutional dashboards are further out (spec P2).

### 3.7 Hygiene / smaller items
- **Per-replica scan status:** `GET /admin/pulse/retraction-scan` reads this replica's memory;
  with 2 replicas polls can hit the other one ("never_run"). Move scan state into
  `noesis_change_event`-adjacent storage or a `noesis_worker_setting`-style row.
- **Periodic re-scans:** retractions are checked only on manual trigger. Add a scheduled sweep
  (weekly) — the app has no scheduler; simplest is an admin-cron hitting the endpoint, or a loop
  in the gap-processor thread with a long interval.
- **Watch-data privacy (spec A6):** `noesis_watch` topics are clinician-interest data tied to
  user ids — needs a retention statement and deletion on account removal (no account-deletion
  flow exists yet either).
- **Inbox matching upgrade:** containment matching misses paraphrases ("HFpEF" watch vs an event
  subject "heart failure with preserved ejection fraction"). The canonical registry narrows this;
  the principled fix is embedding-similarity gate + LLM confirm for borderline (spec C2), batched
  at digest cadence. Keep precision-biased.
- **`new_documents` cold start:** time axis exists only from 2026-08-10; windows fill organically.
  Do not backfill dates.

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
1. 3.1 brief composer (immediate user-visible value on existing events; exercises the verify path
   the judge will also need).
2. 3.5 coverage-page feed (an hour; makes the system publicly visible).
3. 3.4 first real supersession pair (proves the core promise end-to-end; unblocks the chip/title
   surfaces).
4. A5 subject facets → 3.2 judge (shadow) → its held-out gates → approval workflow in anger.
5. 3.3 label-change detector.
6. 3.7 hygiene as you touch each area; 3.6 only after precision is demonstrated.
