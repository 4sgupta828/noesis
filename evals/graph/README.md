# Graph hard-case evals (KG spec v3, amendment C-7)

`masquerade_cases.jsonl` — HELD-OUT masquerade set: real hard-case questions whose correct
answer requires evidence about a hidden topic the question never names. Per Rule 5 these
exact questions must NEVER appear in any prompt, few-shot, fixture, or curated-edge note.

Protocol (LLM-spending — run on explicit go):
1. For each case, run `/research` (or kernel-direct) with graph expand OFF, then ON (late).
2. PASS for the graph arm = the answer's cited evidence contains the expected hidden-topic
   signals; the OFF arm establishes the baseline can't reach them (if OFF also passes, the
   case measures nothing — replace it).
3. Score: hidden-topic evidence recall ON vs OFF; no-harm on grounded rate.
Structural (free) pre-check: the expander must produce the expected masquerade leg for each
question — covered by `apps/api/test_graph_expander.py` for the flagship case.
