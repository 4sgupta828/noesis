# Clinical-Decision / Differential-first answers — spec + implementation plan (2026-08-17)

**Goal (owner):** clinician-facing CLINICAL DECISION answers — a clear decision framework (ranked
differential + discriminating workup + what-changes-management), from SOTA/decision-grade sources with
SOTA reasoning, so a clinician can make an informed decision with the evidence in front of them. MUST be
PROVEN (held-out eval) to beat the current answers on clinician decision-usefulness before flip-ON.

**Panel verdict (Codex + Gemini + code-grounded, 2026-08-17): UPGRADE the reasoned engine, do NOT add a
separate top-level mode.** The decision machinery already exists and is live (reasoned engine:
scaffold classifier + `REASONED_ANSWER_FORMAT` decision gates). A new mode duplicates it for zero new
capability. The gap is three surgical additions inside the reasoned engine.

## The gap (grounded in code + a live prod DDx answer)
1. No first-class **ranked differential** — likelihood language + discriminators + most-discriminating
   next test + threshold. It's buried in `## Assessment` prose (`reasoned.py:50`).
2. Sourcing is research-literature-first — the authority lever exists but is a weak bounded compose boost
   (`_EVIDENCE_FITNESS_WEIGHT=0.15`, `react.py:428`, gated on `evidence_fitness`), not a retrieval
   preference/anchor. Config gap, not from-scratch.
3. Reasoning is implicit (retrieval→compose); no separable, inspectable differential artifact.

## Grounding realities that shape the design (code-grounded audit)
- The FINAL PROSE answer is NOT per-sentence span-gated — grounding is enforced at the ATOM level
  pre-compose (span gate `provenance.py:44` + misattribution `react.py:1315`); prose only gets a
  citation-FORMAT check (`_refs_valid`, `react.py:410`). → a grounded decision framework is SHIPPABLE,
  but prose synthesis is weakly policed → the hazard is a QUANTITATIVE differential (invented pre-test
  probabilities / LRs). **Mandate QUALITATIVE likelihood language.** If we emit the differential as a
  STRUCTURED field it rides the no-new-facts validator (`react.py:382`) — the one place code catches a
  fabricated number.
- Case facts from the vignette ("orthopnea") are FRAMING, not citable findings (`react.py:780`). A DDx
  table will under-cite or over-rely on uncited prompt facts unless we treat case facts as a labeled,
  non-citable ledger the answer may reference as "the patient's" facts (v1: instruct compose to cite
  only retrieved findings for CLINICAL claims and reference case facts as given, never as `[n]`).

## Output spec — `MEDICAL_DIFFERENTIAL_FORMAT` (differential-first)
Leads with the differential; every clinical claim carries `[n]`; likelihood is QUALITATIVE only.
- `## Ranked differential` — per candidate: qualitative likelihood IN THIS PRESENTATION (most likely /
  worth considering / can't-miss), the discriminating features present/absent that move it (cited), and
  the single most-discriminating next test + what result confirms/refutes. Can't-miss items flagged and
  should carry a guideline/SR-tier citation.
- `## Initial workup` — red flags / immediate steps, first-line tests, branch triggers, escalation
  thresholds (ordered by probability × severity-if-missed × actionability, qualitative).
- `## What changes management` — explicit "if <trigger/result> → <action>" thresholds (admit, image,
  treat empirically, consult, observe, broaden).
- `## Evidence basis & uncertainty` — guideline/curated-synthesis first; primary studies only where
  guidelines are absent/conflicting; state "no guideline anchor found" as a real gap; separate (a)
  missing patient info, (b) clinical uncertainty, (c) weak/absent evidence.
- Carries the reasoned DECISION GATES (authority-outranks-semantic-fit, invasive-escalation bar,
  population-specificity) verbatim.
- CLINICIAN-FACING CDS framing: "conditions associated with these findings in the evidence", never an
  autonomous/definitive diagnosis. Not patient-facing.

## Routing + wiring (mirror reasoned_answer_format exactly)
- Kernel: add `differential_answer_format: str|None` to `Manifest` (`contract/manifest.py`) and
  `ResearchRuntime` (`runtime/research.py`).
- Extend `_Scaffold` (`research.py:198`) with `is_diagnostic: bool=False` (LLM-owned, Rule 18 — set true
  when the question asks for a differential / "what could this be" / initial workup of a presentation).
  In `ask_reasoned`: when `kind=="management"` AND `is_diagnostic` AND `self.differential_answer_format`
  → `answer_format_override = self.differential_answer_format` (else reasoned format, unchanged). Add a
  guideline-steering line to the coverage brief for diagnostic questions. Emit an `engine:"differential"`
  trace event.
- Vertical: `MEDICAL_DIFFERENTIAL_FORMAT` in `reasoned.py` (or `answer_format.py`); wire in
  `vertical_medical/manifest.py`.
- App/flag (Rule 20): `differential_format_enabled()` reads `NOESIS_DIFFERENTIAL_FORMAT` (default OFF);
  when ON, pass `differential_answer_format=MEDICAL_DIFFERENTIAL_FORMAT` to `build_default_service`; when
  OFF pass None → runtime always uses the reasoned format → byte-identical. Echo `differential_format_enabled`.
- Sourcing v1: recommend `evidence_fitness` ON in prod (already a flag) + the guideline-steering brief
  line. A HARD guideline-anchor requirement is a separate, larger build (deferred).
- UX (optional, later): a "Clinical decision" vs "Research" toggle is just a FE label that forces
  is_diagnostic routing — same engine, no parallel pipeline. Not required for v1 (auto-routing suffices).

## Implementation status (2026-08-17)
- BUILT + unit-tested: `MEDICAL_DIFFERENTIAL_FORMAT` (`reasoned.py`); `differential_answer_format` on
  `Manifest`, `ResearchService`, wired in vertical manifest; `_Scaffold.is_diagnostic` (LLM-owned) →
  `ask_reasoned` selects the differential format for diagnostic management questions + a guideline-steering
  coverage-brief line + `engine:"differential"` trace; flag `NOESIS_DIFFERENTIAL_FORMAT`
  (`differential_format_enabled`, default OFF) — OFF wires `differential_answer_format=None` so the
  reasoned engine always uses the reasoned format (byte-identical); echoed to `/config`.
- Tests (all green): `runtime/test_research_differential.py` (diagnostic→differential, non-diagnostic→
  reasoned, flag-off→reasoned); `test_api.py::test_differential_format_flag_reads_env`. 102 pass, no regr.
- EVAL PROD-FAITHFULNESS: prod routes clinical-decision questions through `svc.ask_reasoned` (not
  `svc.ask`). The harness `run.py` calls `svc.ask`; a minimal opt-in (`NOESIS_EVAL_REASONED=1` →
  `run.py` calls `ask_reasoned`) makes the A/B exercise the real path. Both arms set it; arms differ only
  on `NOESIS_DIFFERENTIAL_FORMAT`. Eval runs LOCAL code + PROD Postgres corpus (tenant demo) — no deploy
  needed to measure.

## EVAL FIRST (must prove better clinician decision answers) — build BEFORE coding
Held-out DDx slice `evals/realworld/slices/slice-ddx-clinical-<N>-2026-08-17.jsonl`, ~15-20 clinician
vignettes (presentation → asks for differential + workup + decision). Each record HELD OUT from every
prompt/few-shot (Rule 5). Gold per case (gold-DECISION anchors, Rule 6 — not just LLM judge):
`gold_top_dx` (the leading diagnoses), `gold_cant_miss` (dangerous must-not-miss), `gold_discriminator`
(the single most-discriminating next test), `gold_threshold` (a key management trigger).
Rubric (clinician decision-usefulness, judged A vs B pairwise + absolute):
  (1) ranked differential present & covers gold_top_dx + gold_cant_miss;
  (2) discriminators + gold_discriminator next-test named;
  (3) decision thresholds / what-changes-management present & correct;
  (4) evidence grounded, guideline-tier foregrounded where expected;
  (5) clarity/actionability for a clinician making the decision;
  (6) safety: can't-miss covered, qualitative likelihood, no fabrication/overconfidence.
A/B: arm A = `NOESIS_DIFFERENTIAL_FORMAT` OFF (current reasoned), arm B = ON. Same questions/tenant/flags
otherwise. WIN CONDITION to flip ON: arm B strictly better on (1)(2)(3) and coverage of gold_cant_miss /
gold_discriminator, with NO regression on grounding (4)(6). Also gold-coverage counts (did it name the
gold can't-miss / discriminator) as a hard, non-judge metric.

## Build order (subagent-driven where useful; eval before code)
1. Spec + plan (this doc). 2. Held-out DDx slice + gold (author carefully, contamination-checked).
3. DDx judge/rubric + A/B glue on the existing harness; BASELINE arm A. 4. Implement format + routing +
flag (byte-identical OFF). 5. Run A/B, prove B>A on decision dims + gold coverage, no grounding regression;
iterate the format if it loses. 6. Deploy OFF → prod-verify OFF no-op → flip ON → prod-verify a live DDx
answer → leave ON only if the eval win holds. 7. Log results here.

## Risks
1. FDA/liability — ranked DDx reads like autonomous diagnosis. De-risk: clinician-facing CDS framing,
   transparent citations, qualitative likelihood, non-autonomous, default-OFF, eval-gated.
2. False precision / ungrounded DDx — qualitative likelihood only, discriminators must carry `[n]`,
   can't-miss items carry guideline/SR-tier citation; quantitative claims ride the no-new-facts validator.
3. Regression on non-diagnostic questions — is_diagnostic must be precise; OFF byte-identical; the A/B
   must also spot-check that lookup/understanding/management-non-DDx are unchanged.

Related: learnings/competitive-landscape.md (#1 prove-it, DDx in-scope as CDS), reasoned.py, answer_format.py.
