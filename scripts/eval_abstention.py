"""Held-out ABSTENTION-RATE eval (Rule 4) — gates the anti-abstention fix.

The agent must NOT return 0 grounded claims on questions the corpus provably covers. Because the
abstention is run-to-run sampling variance, a replay cassette (identical prompt → identical result)
cannot measure it — this runs the LIVE /research endpoint N times per question and reports the
abstention rate. Fails (exit 1) if any question abstains more than the allowed threshold.

Usage:
  .venv/bin/python scripts/eval_abstention.py [--base URL] [--n 5] [--max-abstain 0]
Default base = prod. Each run is a real LLM call (costs credits); keep N modest.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.request

# Corpus-provable SURVEY questions (covered conditions with obvious intervention evidence) + the
# HPB "criteria/recommendation" anchor that reproduced the abstention on real (europepmc+web) evidence.
GOLD = [
    {"q": "What treatments are being studied for rheumatoid arthritis?", "sources": ["clinicaltrials"]},
    {"q": "What treatments are being studied for asthma?", "sources": ["clinicaltrials"]},
    {"q": "What treatments are being studied for multiple sclerosis?", "sources": ["clinicaltrials"]},
    {"q": "What treatments are being studied for psoriasis?", "sources": ["clinicaltrials"]},
    {"q": "What treatments are being studied for gout?", "sources": ["clinicaltrials"]},
    {"q": ("Which criteria should our HPB team adopt, from published evidence and guidelines, to "
           "guide biliary drain removal timing after subtotal cholecystectomy?"),
     "sources": ["clinicaltrials", "web"]},
]


def _ask(base: str, q: str, sources: list[str], timeout: float = 180.0) -> dict:
    body = json.dumps({"question": q, "tenant_id": "demo", "sources": sources}).encode()
    req = urllib.request.Request(base.rstrip("/") + "/research", data=body,
                                 headers={"content-type": "application/json"}, method="POST")
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode())


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default="https://noesis-api-production.up.railway.app")
    ap.add_argument("--n", type=int, default=5)
    ap.add_argument("--max-abstain", type=int, default=0, help="allowed abstentions per question")
    args = ap.parse_args()

    total_abstain = 0
    worst = 0
    print(f"Abstention eval — base={args.base} n={args.n}\n")
    for case in GOLD:
        abstains = 0
        for i in range(args.n):
            t0 = time.time()
            try:
                d = _ask(args.base, case["q"], case["sources"])
            except Exception as e:   # noqa: BLE001
                d = {"grounded": False, "claims": [], "rejected": 0, "atoms_gathered": 0,
                     "_err": str(e)}
            el = round(time.time() - t0)
            grounded = bool(d.get("grounded"))
            if not grounded:
                abstains += 1
            flag = "OK " if grounded else "ABSTAIN"
            print(f"  [{flag}] {el}s claims={len(d.get('claims', []))} "
                  f"rej={d.get('rejected')} atoms={d.get('atoms_gathered')} "
                  f"retried={d.get('retried_empty')}{' ERR='+d['_err'] if d.get('_err') else ''}")
        total_abstain += abstains
        worst = max(worst, abstains)
        print(f"  → {case['q'][:70]!r}: {args.n - abstains}/{args.n} grounded "
              f"({abstains} abstain)\n")

    print(f"TOTAL abstentions: {total_abstain} across {len(GOLD)*args.n} runs; "
          f"worst-case per question: {worst}/{args.n} (allowed {args.max_abstain})")
    ok = worst <= args.max_abstain
    print("PASS" if ok else "FAIL — abstention exceeds threshold")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
