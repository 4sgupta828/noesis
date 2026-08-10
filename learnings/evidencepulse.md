# Evidence Pulse — the corpus-currency subsystem

**Status:** SPEC (panel review pending) · **Owner flags:** `NOESIS_PULSE*` (all default OFF, Rule 20)

## The idea in one paragraph

Evidence Pulse is NOT a notification feature. It is a **change-detection layer over the corpus**
(the factra pattern: snapshot → diff → change event) whose events feed three consumers, in priority
order: (1) the **answer engine** — answers mechanically prefer current guidance and can never quote
superseded guidance as if current ("most up-to-date and precise" becomes a property, not a hope);
(2) **watchlists + digests** — the engagement/retention loop (clinicians follow topics; material
changes reach them as cited change-briefs); (3) the **coverage story** — "what changed this month"
becomes a live, public proof of corpus vitality. One subsystem, three payoffs; the answer-engine
payoff ships first and needs zero UI.

## Why this ordering is strategic

The Q&A currency layer de-risks the whole build: it is valuable even if the digest product never
finds an audience, it exercises the same change events the digests need, and it directly attacks
the top failure mode external evals found (stale/wrong-version evidence winning by semantic fit).
The digest product then launches on infrastructure already proven in production.

## Contract (Rule 1)

- **Given** a new ingest that lands a document materially superseding an existing one (e.g. KDIGO
  2026 Anemia replacing KDIGO 2012), **the system must** (a) record a change event with a cited,
  span-grounded change brief, (b) mark the old document's blocks superseded, and (c) from that
  moment, answers touching that subject must cite the NEW guidance — or explicitly name the old
  version as prior — never present superseded guidance as current.
- **Given** a re-ingest of the same or an immaterial variant (translation, reprint, summary of the
  same edition), **no event fires** (precision guarantee — alert fatigue is existential).
- **Given** a user watching "anemia in CKD", **when** a material event matching that topic lands,
  their next visit shows the change brief (P1: in-app inbox; P2: digest email).
- **Invariants preserved:** grounding (briefs are span-verified against the new document);
  Rule 18 (LLM judges supersession/materiality/topic-match; code owns joins, dates, dedup);
  additive-only schema; every flag default OFF with the OFF path byte-identical.

## Architecture

```
ingest completes (gap-queue processor)
        │  candidate generation (STRUCTURAL: same issuer/subject facets, newer year,
        │  guideline/label/safety tiers only — literature volume never triggers alone)
        ▼
  LLM supersession + materiality judgment (Rule 18)  ──rejected──▶ no event
        │ confirmed
        ▼
  noesis_change_event  (+ span-grounded change brief, cited to the NEW doc)
        │
        ├─▶ [C1] supersession stamp: old doc's blocks get facets.superseded_by=<new_doc_id>
        │        → retrieval demotion (code) + "[superseded by …]" visible in title (composer)
        ├─▶ [C2] watch matching (embedding similarity + LLM confirm) → user inbox / digest
        └─▶ [C3] /pulse/recent — public "what changed" feed (coverage page + marketing surface)
```

### Data model (additive; lives beside noesis_user / noesis_corpus_gap_queue)

```sql
CREATE TABLE noesis_change_event (
  id            text PRIMARY KEY,
  kind          text NOT NULL,          -- guideline_new | guideline_superseded | label_change
                                        -- | safety_signal | trial_landmark (P2)
  subjects      jsonb NOT NULL,         -- conditions/drugs the event is about (LLM-extracted)
  old_document_id text,                 -- null for guideline_new
  new_document_id text NOT NULL,
  materiality   text NOT NULL,          -- major | minor  (LLM judgment; only major notifies)
  brief_md      text NOT NULL,          -- the cited change brief (span-verified at creation)
  brief_claims  jsonb NOT NULL,         -- claim/quote/locator set backing the brief
  created_at    timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE noesis_watch (
  user_id     text NOT NULL,            -- FK noesis_user
  topic       text NOT NULL,            -- free-text topic ("anemia in CKD", "apixaban")
  source      text NOT NULL DEFAULT 'manual',   -- manual | suggested (from session history)
  created_at  timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (user_id, topic)
);
CREATE TABLE noesis_watch_delivery (     -- what each user has SEEN (idempotent delivery)
  user_id text NOT NULL, event_id text NOT NULL, seen_at timestamptz,
  PRIMARY KEY (user_id, event_id)
);
```

Supersession lives IN the block facets (`superseded_by`), not a separate join table, so retrieval
pays zero extra queries — the stamp is applied once per event by an UPDATE on the old document's
blocks.

### [C1] Answer currency (P0 — powers Noesis itself)

- **Ranking (code, structural):** `_rank_claims_by_relevance` treats `facets.superseded_by` as a
  hard demotion *below* un-superseded claims of the same tier (stronger than the recency boost —
  recency is a preference, supersession is a fact).
- **Compose visibility (LLM, semantic):** superseded blocks' titles gain "[superseded by <new title>
  (<year>)]" — so if one IS cited (e.g. to narrate what changed), the composer knows and must not
  present it as current. One directive line (additive) makes this explicit.
- **Answer currency chip (FE, P1):** when an answer's cited subjects intersect a change event from
  the last 90 days, the answer shows "◉ Guidance in this area changed <month>" linking the brief —
  the visible proof of freshness that competitors' answers don't carry.

### [C2] Watchlists + digests (P1)

- Watch sources: manual add (a "watch this" chip on any answer — one tap, seeded with the
  session's subjects) + suggested (LLM proposes topics from the user's session history; opt-in).
- Matching: batch job per digest cycle — embed watch topics × event subjects, cosine gate, LLM
  confirms borderline matches (precision over recall; a missed minor match is acceptable, a
  wrong match is not).
- Delivery: in-app inbox first (a "Pulse" bell in the header; unseen-count badge; each item = the
  change brief with citations, one-tap "ask about this" into Q&A — the loop back into engagement).
  Email digests are P2 (needs a mail provider; weekly cadence, hard cap of items, only `major`).

### [C3] Public pulse feed (P1, trivial)

`GET /pulse/recent` — last N major events, no auth. Rendered on the coverage page. This is the
marketing surface ("the corpus that visibly stays current") and costs nothing beyond C2.

## LLM contracts (all opaque directives, vertical-owned)

1. **Supersession judge**: given old/new doc metadata + lead text → {supersedes: bool, materiality,
   subjects[]}. Held-out eval cases: true supersession (KDIGO 2012→2026), same-edition variant
   (translation/reprint → NO), adjacent-but-distinct (BP-in-CKD vs CKD guideline → NO).
2. **Change-brief composer**: given both docs' relevant blocks → "what changed / what it means for
   practice / what it replaced", every claim span-verified against the new doc (reuse the existing
   verification gate). Failure → event records without brief; retry next cycle (never an
   unverified brief).
3. **Watch matcher** (borderline confirm) and **watch suggester** (from session history) — both
   precision-biased.

## Costs (bounded by construction)

- Detection triggers only on guideline/label/safety-tier ingests (a handful per week), never on
  bulk literature. Per event: 1 judge call + 1 brief compose (~$0.05–0.15). Watch matching:
  embeddings + rare confirm calls per cycle. Total steady-state: dollars per month, not per day.

## Flags (Rule 20)

- `NOESIS_PULSE` — master: detection + events + supersession stamping. OFF = no writes, no reads.
- `NOESIS_PULSE_ANSWER_CURRENCY` — C1 ranking demotion + title annotation (needs PULSE).
- `NOESIS_PULSE_WATCH` — C2/C3 surfaces (needs PULSE).
- All resolve via the live `SettingStore` so prod can flip without redeploy.

## Held-out eval gates (before trusting; Rules 4/5/7)

- Detection: the 3 supersession cases above + 2 label-change cases; zero false events on a
  replayed no-change ingest.
- Answer currency: questions whose corpus contains BOTH guideline versions — the answer must cite
  the new version (or name the old as prior); measured on ≥5 held-out subjects.
- Digest precision: seeded watchlist × replayed event stream → every delivered item human-checked
  relevant (target: 100% precision on `major`; recall is secondary).

## Phasing

- **P0 (ship first):** change events + supersession stamping + ranking demotion + title
  annotation. Zero UI. Immediately makes Q&A supersession-proof.
- **P1:** answer currency chip · watch chip on answers · Pulse inbox · /pulse/recent on coverage.
- **P2:** email digests · CME wrapper · institutional currency dashboard · trial_landmark events.

## Risks & honest unknowns

- **Precision is existential** (one noisy digest kills trust): mitigated by major-only delivery,
  precision-biased matching, and the held-out gates — but real-world materiality judgment needs
  clinician calibration (same open item as the warrant eval).
- **Coverage asymmetry**: we can only detect changes in sources we ingest; a watched topic whose
  guideline lives outside the corpus silently never fires. Mitigation: watch topics get a coverage
  check at creation ("we track KDIGO/AHA/… for this — X is not yet covered") — honest, and it
  feeds the corpus roadmap.
- **Fast-follow risk** (OpenEvidence could ship generic alerts): our moat is personalization from
  session history + grounded diffs; speed of P0→P1 matters more than perfection.
