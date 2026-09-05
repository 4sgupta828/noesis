# Noesis

**An evidence-grounded research engine.** You ask a real question; Noesis searches a curated
corpus (plus the live web), reasons over what it finds, **verifies every claim and number against
its source before it ships**, and returns a decision-shaped answer with citations you can click
back to the exact passage.

The active domain is **medical** — evidence-grounded clinical decision support for healthcare
professionals — but the engine itself knows no medicine. Noesis is a **domain-agnostic kernel**
(ingest → corpus → retrieval → research → synthesis) with a **vertical plug-in** on top; a legal or
financial vertical would reuse the kernel untouched.

> ⚕️ *Medical use is for informational purposes for healthcare professionals — not medical advice.
> Every answer is AI-generated; verify against the cited primary sources before any clinical
> decision.*

---

## Table of contents
- [What it does](#what-it-does)
- [How it works (the big picture)](#how-it-works-the-big-picture)
- [The research loop — how one answer is made](#the-research-loop--how-one-answer-is-made)
- [The one rule that defines the architecture](#the-one-rule-that-defines-the-architecture)
- [Data pipeline — how the corpus is built](#data-pipeline--how-the-corpus-is-built)
- [Feature surfaces](#feature-surfaces)
- [Repository layout](#repository-layout)
- [Running it](#running-it)
- [Model providers](#model-providers)
- [Configuration & feature flags](#configuration--feature-flags)
- [Key design decisions (locked)](#key-design-decisions-locked)
- [Deeper reading](#deeper-reading)

---

## What it does

For a clinician (the medical vertical), Noesis turns a question into a **grounded, cited answer** —
and offers several ways to interrogate the evidence:

| Surface | What it gives you |
|---|---|
| **Q&A** | A grounded clinical-decision answer (Bottom line → Do now), every claim quote-verified. Two engines: **Clinical Decision** (reason to a decision) and **Research** (what does the evidence show). |
| **Specialist Panel** | Several AI specialists (cardiology, ID, pharmacology, …) each answer through their own lens, then a grounded synthesis reconciles them. |
| **Evidence Pulse** | A living "what changed" feed — retractions and guideline supersessions in the corpus, each with a span-verified **change brief** ("what changed / what it means / what it replaced"). |
| **Case Board** | Curated real landmark medical cases (historical + last 4–5 decades), each with a Noesis answer and a clinician evaluation rubric. |
| **Corpus Explorer** | Pure keyword + semantic retrieval over the ingested corpus — read the sources first-hand, with links back to the full document. |
| **People** | 1.27M US physicians (all NUCC taxonomies) + CMS affiliations/metrics; a conversational "find the right specialist" concierge. |
| **Add-ons** | Grounded conceptual diagrams below an answer, a plain-language rewrite, a term glossary, voice input/output, and an answer-to-video generator. |

Everything user-facing is **flag-gated** and **grounding is non-negotiable** — the engine abstains
or flags a gap rather than shipping an unverified claim.

---

## How it works (the big picture)

```mermaid
flowchart LR
    subgraph SOURCES["Sources"]
      OA["Open-access literature<br/>(Europe PMC, PubMed)"]
      GUI["Society / gov guidelines<br/>(curated registry)"]
      TRIALS["ClinicalTrials.gov · FDA<br/>DailyMed · FAERS · CDC"]
      WEB["Live web<br/>(Brave / Exa / Tavily)"]
    end

    subgraph KERNEL["Domain-agnostic kernel"]
      ING["Ingestion<br/>connectors · queue · WAF breaker"]
      COR[("Corpus<br/>Postgres + pgvector<br/>blocks · facets · embeddings")]
      RET["Retrieval<br/>hybrid: tsvector + vector<br/>fusion · rerank"]
      RES["Research<br/>ReAct loop · span-verify gate<br/>cost governor"]
      SYN["Synthesis<br/>compose · tables · deliverables"]
    end

    subgraph VERT["Medical vertical (plug-in)"]
      MAN["VerticalManifest<br/>prompts · connectors · policies · vocabulary"]
    end

    OA & GUI & TRIALS --> ING --> COR
    WEB -.retrieval-time.-> RES
    COR --> RET --> RES --> SYN --> ANS["Grounded, cited answer"]
    MAN -. teaches via typed contract .-> KERNEL

    LLM["LLM provider<br/>Anthropic · DeepSeek · OpenAI"] -. drafting / judging .-> RES & SYN
    EMB["Embeddings<br/>OpenAI text-embedding-3-small"] -. vectors .-> COR & RET
```

- **The corpus is the moat.** Public + legally-reusable evidence is *downloaded and indexed*
  (never just linked), so answers are grounded in first-party text with stable citations. The live
  web fills only what the corpus can't (breaking/undownloadable material).
- **Postgres does double duty** — `tsvector` full-text **and** `pgvector` cosine — so retrieval is
  hybrid (keyword + semantic) in one store.
- **The LLM is swappable** (see [Model providers](#model-providers)); embeddings stay on OpenAI.

---

## The research loop — how one answer is made

A question enters as an HTTP request and leaves as a grounded, citation-bearing answer. Under the
hood it's a bounded **ReAct loop** (reason → act → observe) with a **hard span-verification gate**:
no claim ships unless its quote is found verbatim in a real source block.

```mermaid
flowchart TD
    Q["Question (+ history, attachments)"] --> SCAFFOLD["Scaffold / route<br/>classify: management · lookup · understanding · diagnostic"]
    SCAFFOLD --> LOOP{{"ReAct loop<br/>bounded by cost governor"}}
    LOOP -->|search| RET["Hybrid retrieval<br/>corpus blocks + web"]
    RET --> ATOMS["Mine passages into candidate atoms"]
    ATOMS --> CLAIMS["Draft claims (LLM)"]
    CLAIMS --> GATE{"Span-verify gate<br/>quote verbatim in source?"}
    GATE -->|no| DROP["Drop / retry / re-retrieve"] --> LOOP
    GATE -->|yes| KEEP["Verified claim + locator<br/>document · block · offsets"]
    KEEP --> ENOUGH{"Enough to answer?"}
    ENOUGH -->|no| LOOP
    ENOUGH -->|yes| RANK["Rank findings, keep top-N most relevant"]
    RANK --> COMPOSE["Compose answer (LLM)<br/>Bottom line · Do now · evidence"]
    COMPOSE --> AUDIT{"Provenance audit<br/>answer cites a verified claim;<br/>no new facts / numbers"}
    AUDIT -->|fail| COMPOSE
    AUDIT -->|pass| OUT["Answer + citations + diagnostics trace"]
```

**Why this shape:**
- **Grounding is a code gate, not a prompt request.** `BlockSpanVerifier` checks each quote against
  the stored block text; an unverifiable claim is dropped, not trusted.
- **Provenance ≠ correctness.** The span gate proves a quote is *real*; separate no-new-facts and
  drift checks guard against citing the *wrong* real passage.
- **Every run emits a diagnostics trace** — which model served each call, candidates seen, claims
  kept/rejected — so a wrong answer is debuggable without re-running blind.
- **Bounded cost.** A cost governor caps steps/tokens per question.

See `understand/03-answering-questions.md` for the line-by-line walkthrough.

---

## The one rule that defines the architecture

**The kernel names no domain noun.** All domain vocabulary and policy live in a vertical package and
reach the kernel only through typed `VerticalManifest` contracts
(`packages/kernel/noesis_kernel/contract/`). This is what lets a legal or financial vertical reuse
the engine without touching it.

```mermaid
flowchart LR
    subgraph K["noesis_kernel — domain-FREE"]
      direction TB
      k1["documents · blocks · facets"]
      k2["retrieval · ReAct · span-verify"]
      k3["synthesis · eval · conformance"]
    end
    subgraph V["noesis_vertical_medical — the plug-in"]
      direction TB
      v1["prompts: compose · panel · pulse briefs"]
      v2["connectors: Europe PMC · guidelines · FDA"]
      v3["policies · specialists · vocabulary · gold evals"]
    end
    V ==>|"VerticalManifest (typed Protocols)"| K
    K -. never imports a vertical .-> V
```

Enforced three ways in CI (any failure = failing build):
- `tools/check_kernel_invariant.sh` — grep gate for unambiguous domain nouns (`drug`, `dose`,
  `condition`, `NCT`, …).
- `tools/check_kernel_imports.py` — AST gate: the kernel imports no `noesis_vertical_*` package.
- Ambiguous words (`state`, `case`) that legitimately mean non-domain things are judged
  structurally in review + by the typed contract, not by a noisy regex.

**Litmus test:** a legal vertical should reuse the kernel untouched.

---

## Data pipeline — how the corpus is built

Ingestion is **prod-direct**: connectors run in production, hit open APIs, and stream results into
the shared corpus, where new blocks are immediately searchable via the live index.

```mermaid
flowchart LR
    SRC["Connector<br/>Europe PMC · guidelines<br/>ClinicalTrials · FDA"] --> FETCH["Fetch artifact<br/>datacenter egress · WAF breaker"]
    FETCH --> PARSE["Parse into ParsedDoc<br/>docling · markdown · XML"]
    PARSE --> SPLIT["Split into blocks<br/>content-addressed · size-capped"]
    SPLIT --> FACET["Stamp facets<br/>license · source_role · pub_type · year · modality"]
    FACET --> EMBED["Embed new blocks<br/>OpenAI text-embedding-3-small"]
    EMBED --> STORE[("rs_block · Postgres<br/>text + tsvector + vector + facets")]
```

- **License discipline.** Every block records its reuse rights; only commercially-reusable content
  (CC0 / CC-BY / public-domain / society-free) is ingested. "Free to read" ≠ "reusable."
- **Content-addressed dedup.** A block's id is a hash of its text, so re-ingesting the same passage
  is a no-op (and re-running backfills facets cheaply).
- **A gap-fill queue** drains ingest jobs in the background so a bulk pull never blocks serving.
- **Evidence Pulse** watches the corpus for retractions/supersessions and composes span-verified
  change briefs on approval.

---

## Feature surfaces

| Surface | Entry point(s) | Notes |
|---|---|---|
| Q&A | `POST /research`, `/research/stream` | Clinical-Decision vs Research engine; resumable streaming SSE |
| Specialist Panel | `POST /panel/ask[/stream]`, `/panel/plan` | Per-specialist lenses + grounded synthesis |
| Evidence Pulse | `/pulse/recent`, `/pulse/inbox`, `/admin/pulse/scan` | "What changed" feed + change briefs |
| Case Board | `/cases`, `/cases/generate`, `/cases/{id}/eval` | Curated landmark cases + clinician rubric |
| Corpus Explorer | `/corpus`, `/admin/corpus/search` | Keyword + semantic retrieval, source links |
| People | `/people/converse`, `/people/entity`, `/people/search` | 1.27M physicians + CMS data |
| Add-visuals | `POST /visuals/augment` | Grounded flow / tree / timeline diagrams |
| Glossary | `/glossary`, `/terms/explain` | Accumulating term web |
| Voice | `/voice/tts` + browser STT | Voice input everywhere; neural TTS |
| Video | `/videos` + `apps/video` | Answer → narrated video |

The web UI (`apps/web/`) is a single served `index.html` (no build step) plus `/admin`, `/corpus`,
and `/admin/perf` pages.

---

## Repository layout

```
packages/kernel/               # noesis_kernel — the domain-agnostic platform
  noesis_kernel/
    contract/                  # the VerticalManifest SPI (typed Protocols)
    ingestion/                 # Source, Connector, FetchStrategy, queue, storage, WAF breaker
    corpus/                    # Document -> ParsedDoc -> Block spine + parser registry + splitter
    retrieval/                 # hybrid fusion (tsvector + pgvector), rerank, generic BlockHit
    research/                  # ReAct loop, generic tools, span-check gate, cost governor
    synthesis/                 # comparison tables, templates, deliverable kinds
    currency/                  # Evidence Pulse: change events, stamps, brief composer
    graph/                     # grounded relationship graph (curated edges)
    people/                    # specialist inventory (NPPES/CMS loaders + store)
    providers/                 # LLM (Anthropic/OpenAI/DeepSeek), embeddings, web search, cassettes
    runtime/                   # build_llm/embedder/web seam + ResearchService
    eval/  conformance/  observability/
packages/vertical_medical/     # noesis_vertical_medical — the active clinical vertical
apps/
  api/                         # FastAPI app (app.py) — wires kernel + vertical, all endpoints
  web/                         # single-file UI (index.html) + admin/corpus/perf pages
  video/                       # answer-to-video generator (Node)
tools/                         # kernel-invariant CI gates
understand/                    # architecture walkthrough (start at 01-architecture.md)
evals/  docs/  learnings/      # held-out evals, vertical docs, engineering notes
```

---

## Running it

Requirements: Python 3.11+, Postgres with the `pgvector` extension, and API keys for your chosen
LLM provider + OpenAI (embeddings).

```bash
# 1. install the kernel (with serve + postgres extras) and the active vertical
pip install -e "packages/kernel[serve,postgres]" -e packages/vertical_medical

# 2. configure (see .env.medical): the corpus DSN + provider keys
export NOESIS_CORPUS_DSN="postgresql://user:pass@localhost:5432/noesis"
export ANTHROPIC_API_KEY=...        # or DeepSeek / OpenAI — see Model providers
export OPENAI_API_KEY=...           # embeddings

# 3. run the API + UI (hardened launcher: frees the port, loads .env.medical, LIVE if keys present)
bash scripts/serve.sh               # -> http://localhost:8000

# CI gate — the kernel domain-noun invariant
bash tools/check_kernel_invariant.sh

# tests (offline via cassettes — no credits needed)
python -m pytest packages/kernel
```

**Provider modes** (`NOESIS_PROVIDER_MODE`): `replay` (default — offline, free, cassette-backed for
dev/CI/eval), `record`, or `live` (real API calls). The same code path serves dev and prod; credits
are opt-in.

**Deploy:** the app runs on Railway (`railway.toml`, `deploy/`); the committed `apps/web` is served
as-is. Corpus ingestion runs prod-direct via `POST /admin/corpus/ingest`.

---

## Model providers

The LLM family is a swappable seam (`runtime/build.py`); **embeddings always stay on OpenAI**.
Default is Anthropic; DeepSeek is OpenAI-protocol-compatible via `base_url`.

```bash
# Anthropic (default — no provider env needed)
NOESIS_LLM_MODEL=claude-sonnet-5

# DeepSeek (OpenAI-compatible endpoint)
NOESIS_LLM_PROVIDER=deepseek
DEEPSEEK_API_KEY=sk-...
NOESIS_LLM_MODEL=deepseek-chat            # or deepseek-reasoner

# OpenAI
NOESIS_LLM_PROVIDER=openai
OPENAI_API_KEY=sk-...
NOESIS_LLM_MODEL=gpt-4o
```

A model **name** overrides the provider, so an explicit `claude-*` stays on Anthropic even when the
global default is DeepSeek (and vice versa). Structured output uses OpenAI's `json_schema` with a
`json_object` fallback for DeepSeek. The switch is reversible with no redeploy (unset the env), and
the per-answer diagnostics trace records which model served each call.

### Web search providers

The web leg is the same kind of seam (`build_web`). `NOESIS_WEB_PROVIDER` selects explicitly
(`brave` / `exa` / `tavily`); unset, the first funded key wins in that order.

```bash
BRAVE_API_KEY=BSA...        # Brave Search API — ranked results + query-aware extra snippets; page
                            # bodies are fetched directly (bot-walled pages fall back to snippets)
EXA_API_KEY=...             # Exa neural search — serves its own cached page text + highlights
TAVILY_API_KEY=...          # Tavily — fallback when no other key is set
```

All three return the same `WebResult` (url, title, snippet, body, published, highlights) and the
vertical's trusted-domain whitelist applies to each (Exa: `includeDomains`; Brave: post-filter over an
over-fetched result set). Brave's entry plans allow ~1 request/s; calls are throttled in-process
(`NOESIS_BRAVE_MIN_INTERVAL`, default 1.0s) and 429s are retried.

---

## Configuration & feature flags

Every user-visible feature is a flag, **default OFF**, echoed on `GET /config`, so it rolls out and
back in prod without a redeploy (and OFF is byte-identical to before). Examples:

| Flag | Feature |
|---|---|
| `NOESIS_ASK_PANEL` | Specialist Panel |
| `NOESIS_HISTORICAL_CASES` | Case Board |
| `NOESIS_VISUAL_AUGMENT` | Add-visuals |
| `NOESIS_TERM_GLOSSARY` | Term glossary |
| `NOESIS_MODALITY_MODE` | Allopathic / Alternative (CAM) modality |
| `NOESIS_VOICE_EVERYWHERE` | Voice input across surfaces |
| `NOESIS_LLM_PROVIDER` | LLM provider seam (anthropic / deepseek / openai) |

Build-time flags are `Field(default=False)` booleans in `config.py`; live-toggle flags live in a DB
setting row with an `/admin/...` endpoint (no redeploy).

---

## Key design decisions (locked)

- **Grounding is non-negotiable** — every claim/number is code-validated against its source
  (verbatim span gate + no-new-facts guards) before it ships. Abstain over fabricate.
- **The LLM owns meaning; code owns structure** — classification, attribution, and interpretation
  are the model's; parsing, IDs, dedup, and validation are code's. No regex/keyword heuristic ever
  makes a semantic decision.
- **Corpus-first** — download and index all public + legally-reusable evidence; the web leg is only
  for what the corpus can't hold.
- **Single vertical per deployment** — a deployment activates one vertical manifest at boot.
- **Ship behind flags, default OFF** — the flag is the rollout seam and the rollback path.
- **Provenance ≠ correctness** — a verifier that confirms a quote is real does not prove the right
  source was chosen; semantic correctness needs held-out gold evals.

---

## Deeper reading

- `understand/01-architecture.md` — the kernel/vertical split and the layer stack
- `understand/02-ingestion.md` — sources, connectors, the corpus spine
- `understand/03-answering-questions.md` — the research loop, end to end
- `understand/04-medical-vertical.md` — what the medical plug-in supplies
- `understand/05-design-philosophy.md` — the principles above, in depth
- `CLAUDE.md` — the operating rules for agents working in this repo
- `learnings/` — engineering notes and post-mortems (corpus tranches, evals, incidents)
