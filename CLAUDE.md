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
