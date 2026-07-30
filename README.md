# Noesis

A **vertical-agnostic evidence & research platform**. A domain-agnostic **kernel**
(ingest → corpus → retrieval → research → synthesis) with a **vertical plug-in
contract** on top. The first vertical is **regulatory commissions**; the platform
is designed so other verticals (financial/SEC, legislative) plug in without
touching the kernel.

> This repo is the ground-up rebuild of the prior `factra` system, extracting a
> clean kernel from an entangled regulatory product. See `docs/` for the full
> architecture spec and phased implementation plan.

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
packages/vertical_regulatory/  # noesis_vertical_regulatory — vertical #1 (reference impl)
apps/{api,web,workers}/        # vertical-neutral product shells
evals/                         # held-out eval gold + runners
tools/                         # check_kernel_invariant.sh (+ dev tooling)
docs/                          # architecture-spec.md, implementation-plan.md
```

## Key decisions (locked)

- **Ingestion-based for all sources incl. Ohio** — OH is a clean connector +
  `WarmedResidentialBrowserStrategy` on the generic pipeline; **no legacy DB,
  pipeline, or download-bridge carryover.**
- **Lift-and-refactor** the proven research core (ReAct loop, span-check,
  retrieval fusion, comparison composer, cost governor) under clean contracts;
  **rewrite** only the domain-welded control flow (gating/routing/coverage).
- **Single vertical per deployment** — a deployment activates one vertical
  manifest at boot; verticals get separate deployments + DBs.
- **Second vertical = Financial** (XBRL + fact-coordinate verification), built
  as a conformance proof to keep the abstraction honest.

## Status

Bootstrapping (plan phase **P0**). See `docs/implementation-plan.md` for the
P0–P5 phases and gates, and `docs/architecture-spec.md` for the full design.

## Dev

```bash
bash tools/check_kernel_invariant.sh    # the kernel domain-noun gate
```
