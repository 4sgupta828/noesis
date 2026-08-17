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

## Phase 1 execution log
- (fill in as jobs land: journal → blocks, validation query on tenant `demo`, credit spend)

Related: learnings/corpusfirst.md, learnings/competitive-landscape.md, learnings/evidencecontract.md,
learnings/noesisindia.md.
