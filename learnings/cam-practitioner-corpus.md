# CAM practitioner corpus & contract — plan of record (2026-08-16)

**Goal reframe (owner directive):** not "defensive complement to modern medicine" but **Noesis as a
working tool a practicing acupuncturist / acupressure therapist / Ayurveda vaidya can run with** — deep
enough to answer practice-level questions (point selection/meridians, acupressure points, Ayurvedic
dosha/diagnosis/classical-formulation/dravyaguna/panchakarma), while keeping every grounding invariant
(fail-closed verbatim span gate + no-new-facts + misattribution judge) and honest evidence+safety labeling.

Decided by a 3-model panel (Codex GPT-5.5 + Gemini 3 Pro + a code-grounded subagent that verified
file:line). All three converged; the code panelist corrected two premises, Gemini+Codex caught a license
blocker. This doc is the decision of record.

## Decided constraints (do NOT reopen)
- **Modality is at-ingest PROVENANCE, never a regex.** An ingest job carries `modality:"alternative"`;
  the worker stamps it on every block (`apps/api/app.py:2454` → `runtime/ingest.py`). Exactly like the
  modern-medicine corpus was never regex-classified — it simply IS the corpus. The journal-name retro-tag
  `_CAM_JOURNAL_PATTERNS` (`app.py:2466`, `postgres.py:tag_modality_by_journal`) is a Rule-18 violation
  (LIKE on `journal` facet, mis-catches *Chinese Medical Journal* / *J Chinese Medical Assoc* = 600
  conventional blocks) → **RETIRE it, do not narrow.**
- **WHO IRIS manuals are OUT.** WHO Standard Acupuncture Point Locations, WHO TCM terminologies, WHO
  medicinal-plant monographs are **CC BY-NC-SA 3.0 IGO = non-commercial** → excluded on the same rule as
  StatPearls (Noesis is commercial). Substitute the practice-reference layer with OA PMC literature that
  publishes/validates the standard points, public-domain classical translations, and the GoI Ayurvedic
  Pharmacopoeia (pending a license check).
- **Rule 20:** the practitioner behavior ships behind a new default-OFF flag, server-authoritative and
  echoed to the FE (mirror `modality_mode_enabled` / `cam_contract_enabled`).

## Answer contract — practitioner mode (Phase 2)
The current `alt_modality.py` / `INTEGRATIVE_CAM_CONTRACT_LENS` register is evidence-SKEPTIC ("benefit
attributed to placebo… be honest about what isn't supported") — correct for a physician appraising CAM,
**wrong as the default for a practitioner**. Don't rewrite it; **add** a practitioner mode alongside it.
- **Distinct lenses, not one mode.** `acupuncture_practice` (acupuncture + acupressure share the
  meridian/point ontology) and `ayurveda_practice` (separate system: dosha / dravyaguna / panchakarma —
  needs its own `focus` so retrieval steers into the right blocks). Keep `integrative_cam` as the
  evidence-appraisal seat. Roster is declarative `SpecialistConfig`s (`specialists.py`).
- **Split-ontology answer_format:** (1) traditional framework grounded in classical/terminology blocks,
  worded "traditionally indicated for…"; (2) modern efficacy as a separate labeled layer; (3) safety
  invariant (herb–drug interactions, hepatotoxicity, contraindications) always. Reuse the existing
  "VOCABULARY DISCIPLINE" + "SAFETY independent of efficacy" clauses (`specialists.py:404`).
- **Gating:** new flag `NOESIS_CAM_PRACTICE`, hot-swapped via the existing `_apply_cam_contract` pattern
  (`app.py:732`). Conventional specialists keep strict `source_keys` so traditional blocks never leak
  into a cardiology answer (allopathic view already excludes `modality:alternative`, `app.py:508`).

## The #1 risk — "efficacy laundering" (all 3 panelists) and its fix
The span gate proves a quote is REAL, not that the source is a *traditional-use* source; the no-new-facts
guard only blocks novel numbers (`react.py:382`). So a verbatim classical span "ST36 is indicated for
digestion" can be laundered into "ST36 **treats** digestion [n]" — passes both gates, unsupported
efficacy wearing a citation (our Rule 6: provenance ≠ correctness). Fix = **three composed layers**:
1. **Data contract (Rule 8):** stamp `source_role` / `evidence_kind:"traditional_reference"` at ingest on
   classical/terminology connectors; extend `evidence_kind.classify` (structural, Rule-18-clean) and
   surface it on every evidence card (the "evidence typed, not text — identity on every surface" invariant).
2. **LLM claim-type judge (Rule 18, owns meaning, no regex):** an efficacy verb whose basis set is
   traditional-only sources is blocked / down-worded; efficacy verbs require an evidence-source (RCT/SR).
   Also require an explicit source for biomedical mappings ("amlapitta = GERD" can't be inferred).
3. **Vocabulary discipline (directive):** reserve "proven / effective / reduces risk" for modern trial
   data; classical/terminology → "traditionally used for / described as."
Second risk (Gemini): classical vocabulary contaminating conventional vector retrieval → strict
`source_keys` isolation (only practitioner lenses opt into traditional source_keys).

## Ranked source tranches (value × datacenter-feasibility)
- **Phase 1 — evidence + safety backbone (near-zero code, zero license risk, proven channels):**
  - EuropePMC OA CAM journals via the existing `europepmc` connector (runs arbitrary EPMC `query=`),
    stamped `modality:"alternative"`: `JOURNAL:"Journal of Ayurveda and Integrative Medicine"`,
    `"AYU"`, `"Journal of Acupuncture and Meridian Studies"`, `"Integrative Medicine Research"`,
    `"Acupuncture in Medicine"`, `"Journal of Acupuncture and Tuina Science"` — with `OPEN_ACCESS:y`.
  - Cochrane CAM systematic-review abstracts via EPMC (`PUB_TYPE:"systematic-review"` + modality topic).
  - Herb–drug interaction / hepatotoxicity SRs via EPMC; **LiverTox** (NIH public domain) as the safety
    spine — confirm the NCBI Bookshelf channel is datacenter-fetchable, else EPMC-indexed proxy.
- **Phase 2 — the practitioner product:** the two lenses + `NOESIS_CAM_PRACTICE` flag + split contract +
  `source_role` facet + LLM claim-type judge + a held-out practitioner eval slice before flip-ON.
- **Phase 3 — practice depth (gated on license):** public-domain classical translations (Bhishagratna
  1907 Sushruta, Charaka) + Ayurvedic Pharmacopoeia of India via a **curated-registry connector** (the
  `global_guidelines.py` pattern — ingests authoritative non-crawlable content datacenter-safe, no
  bridge). The local→prod bridge is ONLY needed for bulk copyrighted full-text → deferred, behind a
  license review. There is NO endpoint today that accepts externally-parsed blocks (`/ingest` and
  `/admin/corpus/ingest` only run connectors) — the bridge is a genuine build, sequenced last.

## Ingest license policy (from the panel, adopt going forward)
Make `license` + `source_role` required ingest metadata; refuse commercial corpus ingest unless
public-domain, CC BY / CC0, or explicitly `licensed=true`. NC (CC BY-NC*) is excluded (StatPearls, WHO IRIS).

## Phase 1 execution log (2026-08-16, done)
- Retired the regex retro-tag in prod (`/admin/corpus/tag-modality` now 404; `_CAM_JOURNAL_PATTERNS` +
  `tag_modality_by_journal` deleted). Modality is at-ingest provenance only.
- Validate-first: 1 JAIM OA job (limit 20) → **1,228 blocks** (full-text OA is dense). `/search` on tenant
  `demo` for "Ayurvedic management of amavata RA" returned the new JAIM practice papers at the top
  (Multimodal Ayurveda regimen for knee OA, Vardhamana Pippali Rasayana) — mechanism confirmed end-to-end.
- Full tranche (8 jobs, all stamped `modality:"alternative"`) → **~9,900 blocks**; ~**11,100 CAM blocks**
  total incl. validation. Per-job: JAIM 1228+1409, AYU/ayurveda 2304, acupuncture (JAMS/AiM) 1216+23,
  Integrative Medicine Research 1447, acupuncture-SR 2119, ayurveda/herbal-SR (still fetching), herb-drug
  safety 1380. Block density tracks OA full-text availability (some journals abstract-only → low counts).
- Learnings: EPMC full-text OA pulls hit **429 rate limits** during the tranche (some full-text drops to
  abstract) — pace/re-queue; not fatal. Journal-scoped `JOURNAL:"..." AND OPEN_ACCESS:y` is the reliable
  query shape.
- NEXT: Phase 2 (practitioner lenses + `NOESIS_CAM_PRACTICE` flag + split contract + `source_role` facet +
  LLM claim-type judge + held-out practitioner eval). Phase 3 (classical texts / API) pending license check.

## Phase 2 execution log (2026-08-16, mechanism done — behind flag, OFF pending eval)
- Two PRACTITIONER panel lenses added (`specialists.py`): `acupuncture_practice` (acupuncture+acupressure,
  TCM pattern/point framework) and `ayurveda_practice` (dosha/samprapti/classical-formulation/dravyaguna/
  panchakarma). Shared `_CAM_PRACTICE_ANSWER_FORMAT` = 3 separated layers (1 traditional framework, worded
  "traditionally indicated for"; 2 modern evidence, tier+direction labeled, the ONLY layer allowed
  "effective/proven"; 3 safety & integration) + hard vocabulary discipline = the prompt-layer
  efficacy-laundering guard. Fabrication gate unchanged.
- Flag `NOESIS_CAM_PRACTICE` (default OFF) + `_apply_cam_practice()` INJECTS the two lenses into the roster
  only when ON (they are NOT in default SPECIALISTS) → triage/manual-select/FE-echo all see them; OFF
  returns the same object (byte-identical). Echoed to /config as `cam_practice_enabled`. FE surfaces them
  from `panel_specialists` (index.html:1778) with no FE change. `integrative_cam` kept as evidence seat.
- Tests: `test_api.py` — flag reads env; `_apply_cam_practice` OFF=identity, ON appends exactly the two,
  idempotent. All pass. (Pre-existing unrelated fails: test_panel.py::{no_evidence_says_so,
  deadline_cancels_stragglers} — message-drift + 1s-timing, fail on clean tree too.)
- PROD-VERIFIED both states: OFF → `cam_practice_enabled:false`, lenses absent. Flipped ON → lenses in
  roster; `/panel/plan` routed acupuncture-LBP Q → [acupuncture_practice, integrative_cam, ebm,
  primary_care], amavata Q → [ayurveda_practice, rheumatology, ebm, gastro], conventional HTN Q → NO
  practitioner lens (clean). Flag reset to OFF pending the held-out practitioner eval (Rule 20 gate).
- OUTSTANDING before flip-ON for users: (1) held-out practitioner eval slice (acupuncture + Ayurveda
  practice cases, gold = correct traditional framing + correctly-separated evidence layer + no
  efficacy-laundering); (2) the structural guard (source_role/evidence_kind facet + LLM claim-type judge)
  — lands with Phase 3 classical texts, until then the split-ontology contract is the guard.

## Phase 2b — main-Q&A CAM auto-scope + distinct CAM panelists (2026-08-16, LIVE)
Answering the "do I have to pick the panel + manual mode?" gap: plain Q&A defaulted to Allopathic which
EXCLUDES `modality:alternative`, and the modality toggle was removed → CAM was unreachable in the main box.
- **CAM auto-scope** (flag `NOESIS_CAM_AUTOSCOPE`, default OFF; requires `NOESIS_MODALITY_MODE`): the shared
  `_do_research` helper runs ONE small LLM CAM-intent call (`MEDICAL_CAM_INTENT_SYSTEM`, wired via manifest
  `cam_intent_prompt`, Rule 18, conservative/prefer-false) and, for a primarily-CAM question, sets
  `body.modality="alternative"` → the existing exclusion-off + alt-directive machinery scopes to the CAM
  corpus. Covers `/research` AND `/research/stream` (one injection in the shared helper). Fail-safe: no
  LLM/prompt/error → default Allopathic scope, never a keyword guess. Echoed `cam_autoscope_enabled`.
- **Distinct CAM panelists**: `_apply_cam_practice` (flag ON) now also NARROWS `integrative_cam` →
  specialty "Herbal & Mind-Body Medicine", focus = herbal/naturopathy/homeopathy/mind-body/energy, +a
  scope line on the lens, so the three CAM seats don't overlap (acu→acupuncture_practice, ayurveda→
  ayurveda_practice, rest→integrative_cam). Idempotent; OFF byte-identical.
- Tests: autoscope flag, `_detect_cam_intent` fail-safe, panelist distinctness, practice OFF=identity/
  ON=append+idempotent — all pass.
- PROD-VERIFIED (both flags ON): main-Q&A "acupuncture points for chronic LBP" → grounded, europepmc 31
  retrieved/11 cited (CAM corpus reached), answer names BL23/GV3/BL20/BL40/BL25 + evidence — auto-scope
  works. Conventional "first-line antihypertensive, T2DM+CKD3" → NOT rerouted (ACE/ARB, dailymed-cited) —
  no over-trigger. `/config` shows `cam_autoscope_enabled:true` + integrative_cam as "Herbal & Mind-Body
  Medicine".
- Same eval caveat as Phase 2: on for users without the held-out eval yet; behavior is safe (span-gated,
  conservative router) but unmeasured.

Related: learnings/corpusfirst.md, learnings/competitive-landscape.md, learnings/evidencecontract.md,
learnings/noesisindia.md.
