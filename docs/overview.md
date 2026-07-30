# Noesis — Overview (plain language)

A plain-English companion to `architecture-spec.md` (the design) and
`implementation-plan.md` (the build steps). Read this first.

## The core idea

Today's system does one job: it reads regulatory filings from state utility
commissions, understands them, and answers research questions with evidence.
The problem is that "utility regulation" knowledge is baked into *everything* —
you can't reuse the smart parts for a different kind of research without
untangling it.

The new design splits the system into two clean halves:

- **The kernel** — the "brain and plumbing" that has *no idea* what industry
  it's working in. It knows how to: fetch documents from anywhere, store and
  chunk them, search them, run an AI research loop that answers questions with
  citations, check that every claim is actually backed by a real source, and
  write up findings. None of it knows the words "docket," "utility," or "Ohio."
- **A vertical** — a plug-in that teaches the kernel one specific domain. It
  supplies the vocabulary, where to fetch from, what facts to extract, and how
  to talk about them.

Think of the kernel as a **games console** and each vertical as a **game
cartridge**. The console is generic; the cartridge makes it play a specific
game. Regulatory commissions is cartridge #1. Financial filings (SEC) will be
cartridge #2.

## The decisions we locked in

1. **Fresh start, clean repo** (this repo), not a patch-up of the old one. The
   old tangled code keeps running untouched until the new one is proven.
2. **Everything comes in through one front door.** Today most states are fetched
   one way, but Ohio has a messy special pipeline running on a laptop because
   Ohio's website blocks datacenters. The new design has **no special Ohio
   pipeline** — Ohio is just a normal connector that happens to need a
   "home-internet-like" worker and a careful knock-on-the-door routine. Same
   path as every other state.
3. **Reuse the proven brain, rewrite the tangled wiring.** The AI research loop,
   the citation-checking, and the search-ranking are hard-won and well-tested —
   we *lift and refactor* those, not rewrite them from scratch. What we *do*
   rewrite is the "wiring" that has Ohio-specific decisions hard-coded into it.
4. **One industry per deployment.** A given running copy serves one vertical.
   Financial and regulatory each get their own separate deployment and database.
5. **Prove it works on a second, harder industry** (financial/SEC) before
   declaring the design truly reusable — even though we only ship the regulatory
   one. If the abstraction is secretly still "regulatory in disguise," building
   financial exposes it.

## The one rule that keeps it honest

**The kernel is never allowed to mention a domain word.** There's an automated
check in the build (`tools/check_kernel_invariant.sh`) that fails if "docket,"
"utility," "ohio," etc. ever sneak into the kernel code. If they do, that's proof
a domain concept leaked where it shouldn't. This one rule is what stops the
system from slowly re-tangling itself over time.

## How it gets built (six stages, each with a "prove it" gate)

- **P0** — Set up the measuring tools first (the tests that define "is it still
  correct?").
- **P1** — Build the generic document-fetching pipeline; prove it by ingesting a
  few states *including Ohio* cleanly.
- **P2** — Build the search + the AI research loop + the citation checker; prove
  it against the precision tests.
- **P3** — Plug in the regulatory "cartridge"; prove the answers match today's
  quality.
- **P4** — Build the product surface (API, web UI, admin).
- **P5** — Build a thin financial "cartridge" to prove the design is genuinely
  reusable.

Each stage has to pass a real test before the next one builds on it — no
"it compiles, ship it."

## What the review panel changed (worth knowing)

Three independent reviewers (two external AI models + one that reads the actual
code) stress-tested every version. The big saves:

- Caught that "just retire the Ohio pipeline" would have **broken the Ohio data
  feed**, because the new multi-state ingestion hasn't actually replaced it yet.
- Caught that the citation-checker we'd called "reusable as-is" is actually
  tangled with which-database-it-reads-from and **holds a security guarantee**
  (keeping one customer's private docs from bleeding into another's answers) —
  so it needs careful surgery, not a copy-paste.
- Caught that Ohio's website-evasion trick is subtle: a naive version once
  **silently stalled for 21 hours** without any error, so "no error" isn't proof
  it's working — we need a multi-day throughput test.

## Building it without burning API credits

The whole build and test loop is designed to run **offline, at zero cost**.
Every paid call — to the AI models, the embedding service, and web search —
goes through a single "switch" with three settings:

- **replay** (the default): use previously-recorded answers from disk. No
  network, no credits. This is what every test, every eval, and every local dev
  run uses.
- **record**: make the real call once and save the result to disk (a
  "cassette"). Costs credits that one time.
- **live**: call the real service (production).

So you pay for credits only deliberately and rarely — to record a fresh
cassette, to run an occasional real smoke test, or to run real production. The
day-to-day work costs nothing, and the build even fails if a test tries to make
a live call by accident. Document parsing already runs locally for free, and
embeddings can use a local model too — so even real ingestion can avoid credits,
trading a little search quality (which we measure).

## What's still open (not blocking)

Just one real item: whether to **carry over the existing Ohio data** into the new
system, or re-fetch it fresh. That's a separate, later decision (the deferred
migration spec).
