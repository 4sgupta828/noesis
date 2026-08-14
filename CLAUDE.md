# CLAUDE.md — Noesis

Guidance for Claude Code when working in this repo (the vertical-agnostic research platform).

## UI must be mobile-friendly — always

Every user-facing UI change (any edit to `apps/web/**` or a new page) MUST work and look good
on a phone, not just a laptop. This is a hard requirement, not a nice-to-have — verify it, don't
assume it.

Rules:
- **Responsive by default.** Use relative units, flexbox/grid, `max-width:100%`, and
  `flex-wrap`. The page body must never scroll horizontally; wide content (tables, code, videos,
  diagrams) scrolls inside its own `overflow-x:auto` container.
- **Set the viewport** (`<meta name="viewport" content="width=device-width, initial-scale=1">`)
  on every page.
- **Add a small-screen media query** (`@media (max-width:560px)` is the project convention):
  full-width primary controls, tuned type scale, stacked layouts, hidden/《collapsed》 non-essential
  chrome. Master/detail views stack (list then detail); drag-to-resize dividers hide on mobile.
- **Touch targets ≥ ~40px**, inputs don't zoom unexpectedly, modals/overlays fit the viewport
  (respect `env(safe-area-inset-*)` where relevant).
- **Verify visually at a phone width** before declaring done — e.g. a headless screenshot at
  `--window-size=390,1700` (Chrome), or the CDP flow used elsewhere in this repo. Reading the CSS
  is not enough; look at the rendered result at ≤400px wide.
- Keep it **minimal** on mobile: fewer words, larger tap targets, one clear primary action.

When in doubt, design mobile-first and let the desktop layout be the enhancement.

## API-Credit Discipline (STANDING DIRECTIVE — spend very carefully)

Anthropic/OpenAI API credits are a scarce, shared resource: prod user answers, evals, and
campaigns all draw on the SAME account. An exhausted balance degrades PROD, not just the
experiment. Rules, always:

1. **Free checks first.** Structural tests, jsdom QA, retrieval-only probes (`/search`,
   embedder-only), TestClient runs, and DB integration tests cost nothing — exhaust them
   before ANY LLM-spending run.
2. **Every spending run is projected + gated.** Scripts that answer questions or judge
   outputs must print a projected call budget and refuse to run without `--confirm-spend`.
   The ANSWER side dominates (~10–20 calls per research answer) — price it, not just grading.
3. **Targeted before broad.** One flagship prod verification beats a 50-question sweep;
   stage campaigns in tranches with a review between; reuse banked arms/results instead of
   re-running (e.g. `--off-from` on the masquerade eval).
4. **Never launch a spending run while another is in flight** against shared state, and
   never re-run a failed batch before diagnosing WHY it failed (the tenant-id bug burned a
   full eval run that measured nothing).
5. **Validate the pipeline on 1–2 items before the batch.** A bug found after 20 answers
   costs 20 answers.
6. **Big spends need an explicit user go** with the projected number in front of them
   (per-run, not per-session). When in doubt, ask with the number.

## Kernel/Vertical Split (STANDING DIRECTIVE — nothing hardwired to the medical vertical)

Noesis is a GENERAL AI-platform kernel with verticals applied on top. Every feature is built
kernel-first: `packages/kernel/` owns MECHANICS (retrieval, grounding, graph, currency, evals
plumbing) with ZERO domain vocabulary — no "clinical", "patient", "drug" in kernel code or
kernel prompts. The vertical (`packages/vertical_medical/`) supplies VOCABULARY and JUDGMENT
via the manifest: prompts/directives, relation vocabularies, curated data, authority policies,
domain flavor for kernel-neutral judges (e.g. `domain_directive` params, `graph_map_prompt`).
Dataset adapters (K-QA, HealthBench) are instances plugged into generic harness mechanics.
Litmus test before landing anything: "could a legal or regulatory vertical reuse this by
supplying its own manifest entries, with the kernel untouched?" If not, move the domain part
into the vertical. When a kernel judge/prompt needs domain nuance, take it as a caller-supplied
directive — never bake it in.

## Corpus-First Sourcing (STANDING DIRECTIVE)

DOWNLOAD everything downloadable (public + legal, API-accessible) into the corpus — internal
semantic + keyword search with our own relevance/ranking/currency beats answer-time web
retrieval. Use the WEB LEG only for content that is (a) frequently changing (news-grade,
living pages) or (b) not legally/technically downloadable (bot-walled, licensed). When a
source is available both ways, corpus wins: durable, tier-classified, Pulse-tracked,
reproducible. Inventory + phased tranches: `learnings/corpusfirst.md`.

## Evidence Is Typed, Not Text (STANDING DIRECTIVE — earned 2026-08-13, the sitagliptin failure)

A prod answer attributed renal-dosing quotes from sitagliptin/gabapentin labels to
"antibiotic labels." Every check passed, because every check verified STRINGS: the quote was
verbatim-real (span-check), the quote supported the claim sentence (entailment) — and the
one fact that made the claim false (whose label it was) was stripped at the atom boundary
and shown to no model and no judge. The system was maximally rigorous about text and blind
to meaning. These rules exist so that class of failure cannot be rebuilt:

1. **Never strip identity from evidence.** Anywhere a model or judge sees evidence text, it
   sees the evidence's identity with it — source document, subject/entity, evidence kind
   (label-dosing / trial-efficacy / resistance-surveillance / guideline / ...), population
   when known. De-contextualized snippets are forbidden as LLM inputs. If a surface (planner
   obs, extractor batch, entailment item, compose finding, panel synthesis) renders evidence
   without its identity, that is a bug, not a style choice.

2. **Provenance is never correctness.** "The quote exists" and "the quote supports the
   sentence" are string-level facts. A claim additionally requires CONGRUENCE: the evidence's
   subject is the claim's subject, and the evidence's kind matches what the claim asserts
   (safety claims need safety/dosing evidence — resistance or efficacy data can never back a
   safety statement). A claim that cannot bind congruent evidence is not demoted — it does
   not exist. Fail-safe is abstain/gap, never "close enough."

3. **Checks and evals must not share assumptions.** For every gate we run, the eval suite
   must contain at least one held-out case DESIGNED to pass the gate while being wrong
   (off-subject boilerplate, outcome-type crossover, wrong-population match). If all our
   checks would bless an answer, at least one eval case must exist that proves that's not
   sufficient. An eval that only measures what the checks enforce confirms blind spots
   instead of exposing them.

4. **A recognized gap is work, not a footnote.** If the system itself produces a
   coverage-gap that names a retrievable deficiency (wrong-shaped evidence, unnamed
   entities, missing axis) while budget remains, it must spend budget on targeted
   re-retrieval before composing — never write the answer around evidence it has already
   diagnosed as wrong. Publishing a self-diagnosed-broken answer with an honest footnote is
   still publishing a broken answer.

5. **Red-team the standing system, not just new features.** Panel reviews of new specs do
   not cover old assumptions. On a recurring basis (and after every externally-reported
   quality failure): have an independent model review real prod answers end-to-end against
   primary sources, and re-derive "what could pass all our checks and still be wrong?" for
   the core pipeline. Correlated blind spots are never found from inside the system that
   shares them.

6. **Working well on average proves nothing about structure.** The sitagliptin failure had
   a low base rate — most questions retrieve on-subject evidence, so aggregate eval scores
   hid the flaw. Boundary-shaped questions (generic boilerplate vocabulary shared across
   thousands of documents, enumerable practical asks, cross-population traps) must be
   first-class in every eval slice, weighted by harm, not by frequency.

## Never Normalize a Failing Test (earned 2026-08-13, the hijacked /research route)

POST /research served the wrong function in prod for days (a helper was inserted between the
route decorator and its handler). Two API tests failed with 422 the whole time — and were
repeatedly dismissed as "pre-existing failures, unrelated" by every session that saw them,
including during work that touched the same file. A persistently failing test is a CLAIM
about the system; "pre-existing" describes when it broke, not whether it matters. Rule:
before dismissing any failing test as known/unrelated, spend the five minutes to find WHAT
it is actually asserting and why it fails — or file it as a tracked bug with an owner. A
test suite with tolerated red is a test suite that cannot catch the next regression.

## Route the Next Dollar with the Coverage Diagnostic (STANDING METHOD)

Before building machinery to "improve answers", run the coverage diagnostic
(`learnings/diagnosticprocess.md`; harness `evals/realworld/diag_axes.py`): real questions +
gold must-cover axes → three buckets (covered / uncovered-retrievable / uncovered-absent)
→ the dominant bucket routes the fix (machinery vs ingestion vs nothing). ~$4 converts the
build debate into data; the end-to-end re-run (not the probe) is the truth. Keep evolving
the method in its doc — every use should leave it sharper.
