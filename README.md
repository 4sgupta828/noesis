# Noesis

A **vertical-agnostic evidence & research platform**. A domain-agnostic **kernel**
(ingest → corpus → retrieval → research → synthesis) with a **vertical plug-in
contract** on top. The active vertical is **medical** (evidence-grounded clinical
research); the platform is designed so other verticals plug in without touching
the kernel.

> The kernel is domain-agnostic by construction; all clinical vocabulary and
> policy live in the medical vertical. See `understand/` for the architecture
> walkthrough and `docs/verticals/` for medical-vertical specifics.

## The one rule that defines the architecture

**The kernel names no domain noun.** All domain vocabulary and policy live in a
vertical package and reach the kernel only through typed `VerticalManifest`
contracts (`packages/kernel/noesis_kernel/contract/`). Enforced three ways in CI:

- `tools/check_kernel_invariant.sh` — grep gate for unambiguous domain nouns
  (`docket`, `utility`, `puco`, `ohio`, `jurisdiction`, `case_number`,
  `doc_family`, `filing`, `rate_base`, `roe`, …).
- `tools/check_kernel_imports.py` — AST gate: the kernel imports no
  `noesis_vertical_*` package.
- Ambiguous words (`state`, `case`) that legitimately mean non-domain things
  (mutation state, `switch` case) are judged structurally in review + by the
  typed contract, not by a noisy regex.

Any failure is a failing build.

## Layout

```
packages/kernel/               # noesis_kernel — the domain-agnostic platform
  noesis_kernel/
    contract/                  # the VerticalManifest SPI (14 typed Protocols)
    ingestion/                 # Source, Connector, FetchStrategy, queue, storage, breaker
    corpus/                    # Document→ParsedDoc→Block→BlockContent spine + parser registry
    retrieval/                 # hybrid fusion, rerank, generic BlockHit
    research/                  # ReAct loop, generic tools, span-check gate, cost governor
    synthesis/                 # comparison table, templates, deliverable kinds
    registries/                # data-driven registry tables + Project
    eval/                      # generic scoring (lookup port; qa re-authored)
    conformance/               # VerticalConformance suite (CI gate for any vertical)
    observability/             # cost/breaker metrics + admin API
packages/vertical_medical/     # noesis_vertical_medical — the active clinical vertical
apps/{api,web,workers}/        # vertical-neutral product shells
tools/                         # check_kernel_invariant.sh (+ dev tooling)
understand/                    # architecture walkthrough
docs/verticals/                # medical-vertical specifics (sources, coverage)
```

## Key decisions (locked)

- **Grounding is non-negotiable** — every claim/number is code-validated against
  its source (verbatim span gate + no-new-facts guards) before it ships.
- **The LLM owns meaning; code owns structure** — classification, attribution,
  and interpretation are the model's; parsing, IDs, and validation are code's.
- **Single vertical per deployment** — a deployment activates one vertical
  manifest at boot.
- **Ship behind flags, default OFF** — user-visible changes are flag-gated so
  they roll out and back in prod without a redeploy.

## Dev

```bash
bash tools/check_kernel_invariant.sh    # the kernel domain-noun gate
```
