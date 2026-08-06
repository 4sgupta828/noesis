"""Held-out REFINEMENT eval (Rule 4) — gates the pre-answer question-refinement fix.

Deterministic, no LLM judge. Hits POST /refine and asserts the two contract properties:
  - a BROAD/underspecified question → >= MIN distinct options (near-dup check via token-Jaccard),
  - an already-PRECISE question → [] (the load-bearing over-triggering gate).
/refine is one fast-model call (cheap). Requires prod with NOESIS_REFINE=1.

Usage: .venv/bin/python scripts/eval_refine.py [--base URL]
Exit 1 if any case fails.
"""
from __future__ import annotations

import argparse
import json
import sys
import urllib.request

BROAD = [
    "tell me about diabetes drugs",
    "how do I treat high blood pressure",
    "what about antibiotics",
]
PRECISE = [
    "What is the recommended adult dose of trimethoprim-sulfamethoxazole for PCP prophylaxis?",
    "What was the HbA1c reduction with empagliflozin versus placebo in the EMPA-REG trial?",
]
MIN_OPTIONS = 3


def _refine(base: str, q: str, timeout: float = 60.0) -> list[str]:
    body = json.dumps({"question": q}).encode()
    req = urllib.request.Request(base.rstrip("/") + "/refine", data=body,
                                 headers={"content-type": "application/json"}, method="POST")
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode()).get("refinements", [])


def _toks(s: str) -> set:
    return {w for w in "".join(c.lower() if c.isalnum() else " " for c in s).split() if len(w) > 3}


def _distinct(opts: list[str]) -> bool:
    for i in range(len(opts)):
        for j in range(i + 1, len(opts)):
            a, b = _toks(opts[i]), _toks(opts[j])
            if a and b and len(a & b) / len(a | b) > 0.8:   # near-duplicate
                return False
    return True


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default="https://noesis-api-production.up.railway.app")
    args = ap.parse_args()
    fails = 0
    for q in BROAD:
        try:
            opts = _refine(args.base, q)
        except Exception as e:  # noqa: BLE001
            print(f"FAIL  broad   '{q[:40]}' — request error: {e}"); fails += 1; continue
        ok = len(opts) >= MIN_OPTIONS and _distinct(opts)
        print(f"{'PASS' if ok else 'FAIL'}  broad   '{q[:40]}' → {len(opts)} opts, distinct={_distinct(opts)}")
        if not ok:
            fails += 1
    for q in PRECISE:
        try:
            opts = _refine(args.base, q)
        except Exception as e:  # noqa: BLE001
            print(f"FAIL  precise '{q[:40]}' — request error: {e}"); fails += 1; continue
        ok = len(opts) == 0
        print(f"{'PASS' if ok else 'FAIL'}  precise '{q[:40]}' → {len(opts)} opts (want 0)")
        if not ok:
            fails += 1
    print(f"\n{'ALL PASS' if fails == 0 else str(fails) + ' FAILURE(S)'}")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
