# UI look & feel + answer formatting panel — decision of record (2026-09-05)

Owner's ask: make the UI feel like roster, fix answers that render as compressed blocks
(enumerations back to back), and bring "state of the art" answer formatting with a fresh look.
Three independent lenses reviewed both apps' CSS, the renderer, real answers, and screenshots:
visual design system, answer typography / reading experience, front-end implementation.

## Diagnosis (all three converged)
1. **Console chrome.** Every button and label was mono, uppercase, 0.7rem — it read as a terminal;
   roster's sans 0.8rem/550 buttons are why it reads as a product.
2. **No owned typeface** — three system stacks; a serif lede over a system-sans body looked pasted.
3. **Rules instead of whitespace** — every section carried a full hairline + 3rem of separator while
   body text sat at 13.8px with no reading measure.
4. **Compression is upstream of CSS.** The model writes enumerations inline — "(1) …; (2) …; (3) …"
   and semicolon chains — and the renderer joined consecutive lines into one paragraph, so "Basis:"
   was swallowed by the lede and lists arrived as walls.
5. **Citation jitter** — superscript refs pushed line boxes apart.

## Decision
- **Type**: Newsreader (display: h1, question, lede) · Inter (body/UI) · JetBrains Mono (data only:
  citations, ordinals, diagnostics). Google Fonts, swap, system fallbacks. Root 16px.
- **Tokens per theme** (accent keeps the `--gold` name): light #1D5FD6 on #F5F7FA/#FFFFFF, ink
  #0F1B2A, muted #4C5D6E, hair #DDE4EC; dark #7FA6FF on #0B1220/#121B2E; editorial parchment kept
  with accent #7A5C14 (contrast ≥ 6:1 on paper). `--accent-soft`, `--sh-sm/--sh-md`, `--ring` added.
- **Chrome**: sans buttons (10px radius, 38–40px tall, panel bg, hairline shadow); primary = filled
  accent; mode switch = pill segment; composer radius 20 + soft shadow + focus ring.
- **Answer**: 42rem measure; sentence-case section headings with a 22×3px accent bar (no hairlines);
  serif lede with a left accent rule; muted "Basis:" line; list rhythm .62rem; second em-dash clause
  demoted to a muted note; zebra tables in a rounded scroll container with tabular numerals; refs in
  mono at the baseline in a soft pill. Section semantics tagged: lead / watch (amber) / gap (muted).
- **Renderer** (`mdToHtml`): one line = one block; inline enumerations → stem + numbered list when the
  markers start at 1, increase strictly, ≥3 items (or 2 after a colon), each ≥3 words, never inside
  [brackets], never splitting a highlight pair; ≥3 top-level semicolon segments in a long block → list;
  `Basis:` → its own muted paragraph with " · ". Nine structural cases in `tools/test_md_render.js`.
- **Directives**: every format family now forbids inline enumeration and requires one point per
  paragraph, a blank line between paragraphs, and "Basis:" as its own line.
- **Mobile**: nav wraps at 40px tall; mode switch full width; composer icons drop under the text at
  ≤400px; tables scroll inside their container; verified at 390px (no horizontal scroll).

## Not done (deliberate)
- Answer as an elevated card: skipped — the sessions pane and public page already frame it.
- Grouped refs "1 · 6" in one pill: skipped — per-ref click targets matter more than compactness.
- Contrast CI assertion across theme × surface pairs: recommended; not yet wired.
