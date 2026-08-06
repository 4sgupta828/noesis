"""Held-out FOLLOW-UP subject-tracking eval (Rule 4) — gates the answer-focus / question-condensation fix.

The bug it guards: an elliptical follow-up ("What dose?") after a subject was established
("prophylaxis for PCP is TMP-SMX") loses the subject — the agent compiles doses for every unrelated
drug instead of answering about TMP-SMX. Each case seeds the prior turn via the request `history`
(so it's ONE POST, no need to actually run turn 1) and scores the COMPOSED ANSWER PROSE (not the
verified claims — a compile-and-dump bug hides in the claims but shows in the prose).

Assertions per case (deterministic, no LLM judge):
  - subject_any: the answer mentions the intended subject (any-of substrings), AND
  - not_dominated: intended-subject mentions >= the total mentions of the `distractors`
    (so a dump of unrelated drugs fails).
Controls guard OVER-rewriting: a topic-CHANGE follow-up must be about the NEW subject, and a
self-contained follow-up must stay correct.

Requires prod (or a local server) with NOESIS_ANSWER_FOCUS=1 and NOESIS_CONVERSATION=1.

Usage:
  .venv/bin/python scripts/eval_followup.py [--base URL] [--n 1]
Each case is a real LLM call (costs credits); keep N modest. Exit 1 if any case fails.
"""
from __future__ import annotations

import argparse
import json
import sys
import urllib.request

# Each: history (prior turns) + the follow-up `q`; subject_any = intended-subject substrings (lowercased),
# distractors = unrelated subjects whose dominance signals a compile-and-dump.
GOLD = [
    {
        "name": "elliptical-dose (the reported bug)",
        "history": [{"question": "What is the prophylaxis for pneumocystis pneumonia?",
                     "answer": "Trimethoprim-sulfamethoxazole (TMP-SMX / co-trimoxazole) is first-line "
                               "prophylaxis for Pneumocystis pneumonia."}],
        "q": "What dose?",
        "subject_any": ["tmp-smx", "trimethoprim", "sulfamethox", "co-trimoxazole", "cotrimoxazole"],
        "distractors": ["pentamidine", "acyclovir", "aspirin", "zolpidem", "donepezil"],
    },
    {
        "name": "elliptical-adverse-effects",
        "history": [{"question": "First-line drug for type 2 diabetes?",
                     "answer": "Metformin is the first-line pharmacologic therapy for type 2 diabetes."}],
        "q": "What are its common side effects?",
        "subject_any": ["metformin"],
        "distractors": ["insulin", "sulfonylurea", "glipizide", "empagliflozin"],
    },
    {   # CONTROL: topic change → must be about the NEW subject, not grafted onto the old one
        "name": "control-topic-change",
        "history": [{"question": "What is the prophylaxis for pneumocystis pneumonia?",
                     "answer": "TMP-SMX is first-line for PCP prophylaxis."}],
        "q": "What about prophylaxis for influenza?",
        "subject_any": ["influenza", "oseltamivir", "flu"],
        "distractors": ["pneumocystis", "tmp-smx", "co-trimoxazole"],
    },
    {   # CONTROL: self-contained follow-up → must stay correct (no over-rewrite)
        "name": "control-self-contained",
        "history": [{"question": "What is the prophylaxis for pneumocystis pneumonia?",
                     "answer": "TMP-SMX is first-line for PCP prophylaxis."}],
        "q": "What are alternative PJP prophylaxis options for patients with a sulfa allergy?",
        "subject_any": ["atovaquone", "dapsone", "pentamidine"],
        "distractors": [],
    },
]


def _ask(base: str, case: dict, timeout: float = 600.0) -> dict:
    body = json.dumps({"question": case["q"], "tenant_id": "demo",
                       "history": case["history"]}).encode()
    req = urllib.request.Request(base.rstrip("/") + "/research", data=body,
                                 headers={"content-type": "application/json"}, method="POST")
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode())


def _score(ans: str, case: dict) -> tuple[bool, str]:
    a = (ans or "").lower()
    subj = sum(a.count(s) for s in case["subject_any"])
    dist = sum(a.count(d) for d in case["distractors"])
    if subj == 0:
        return False, f"subject not mentioned (subject={subj}, distractors={dist})"
    if case["distractors"] and dist > subj:
        return False, f"distractors dominate (subject={subj}, distractors={dist})"
    return True, f"ok (subject={subj}, distractors={dist})"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default="https://noesis-api-production.up.railway.app")
    ap.add_argument("--n", type=int, default=1, help="runs per case (sampling)")
    args = ap.parse_args()

    failures = 0
    for case in GOLD:
        for i in range(args.n):
            try:
                r = _ask(args.base, case)
            except Exception as e:  # noqa: BLE001
                print(f"FAIL  {case['name']} — request error: {e}")
                failures += 1
                continue
            ok, why = _score(r.get("answer", ""), case)
            rq = r.get("resolved_question")
            tag = "PASS" if ok else "FAIL"
            if not ok:
                failures += 1
            print(f"{tag}  {case['name']}  [{why}]" + (f"  resolved→ {rq!r}" if rq else ""))
    print(f"\n{'ALL PASS' if failures == 0 else str(failures) + ' FAILURE(S)'}")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
