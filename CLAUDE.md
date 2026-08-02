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
