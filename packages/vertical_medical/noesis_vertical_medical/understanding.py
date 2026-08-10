"""The UNDERSTANDING engine — the middle of Discover · Understand · Act.

Answers WHY/HOW questions with an explicit, cited CAUSAL MODEL: the chain that makes discovered facts
cohere and makes clinical action make sense. Two opaque directives (Rule 18):
  - UNDERSTANDING_ANSWER_FORMAT: the causal-chain compose contract. Its signature discipline is the
    PER-LINK evidence status (established / supported / hypothesized) — causal explanation is the most
    fabrication-prone genre in medicine, so every link is cited AND honesty-labeled.
  - UNDERSTANDING_QUERY_HINT: retrieval steering toward mechanism/pathophysiology/review evidence.

The grounding invariant is unchanged: every link needs a span-verified quote; a smooth mechanistic
story without sources cannot ship.
"""

UNDERSTANDING_ANSWER_FORMAT = """\
STRUCTURE (understanding answer — a CAUSAL MODEL, not an evidence list and not a plan):

## The core mechanism
The "why" in ONE tight paragraph — the central causal insight that makes everything else cohere.

## The causal chain
The chain as explicit steps: **A → B → C**, one line per link. EVERY link cites [n] findings AND
carries an evidence-status label:
- **established** — RCT-level or mechanistic consensus support in the findings;
- **supported** — observational/pharmacologic support;
- **hypothesized** — plausible but unproven in the findings — SAY SO explicitly.
Never smooth over a weak link: a chain is only as honest as its weakest labeled step. Branch the
chain where the biology branches.

## Why the evidence looks this way
Connect the model to the data: why trials showed what they showed, why results conflicted where they
did, where the mechanism PREDICTS benefit vs. where a claim is extrapolation beyond the mechanism.

## How the dots connect
Cross-domain links the chain reveals (shared pathways, why one intervention touches several organ
systems, why two conditions travel together). Only links the findings support — this section earns
the "aha", it must not become speculation.

## Where the model breaks
Boundary conditions and known unknowns: populations/settings where the chain is untested, links that
are actively debated, observations the model does NOT explain. One honest line each.

DISCIPLINE (this engine's failure mode is the confident mechanism story):
- A citation must support the CAUSAL link drawn, not merely mention both endpoints.
- "Biologically plausible" is never presented as established — label it hypothesized.
- Prefer the strongest mechanistic evidence in the findings (mechanistic substudies, physiology
  reviews, guideline rationale sections) over narrative assertions.
- If the findings cannot support a coherent chain, say exactly that and show the fragments that ARE
  supported — an honest partial model beats a smooth invented one.
"""

UNDERSTANDING_QUERY_HINT = (
    "This is a WHY/HOW question: investigate the underlying mechanism and causal pathway — "
    "pathophysiology, mechanism of action, mediators, mechanistic substudies and physiology reviews, "
    "why the intervention affects the outcome, and where the causal evidence is strong vs. merely "
    "hypothesized.")
