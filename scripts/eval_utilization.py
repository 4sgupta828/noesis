"""Held-out UTILIZATION eval (gates the claims-first extraction pipeline).

Broad, well-covered questions should GROUND a large share of the evidence they retrieve — not 2 of
18. Runs the LIVE /research endpoint and asserts the cited/retrieved ratio (and a web-utilization
floor) WITHOUT weakening provenance: every counted citation still had to pass the verbatim span gate
AND the entailment gate server-side, so the score can only be earned by real, supported claims.

Run it deliberately (credits): compare with NOESIS_CLAIMS_FIRST off vs on in prod.
  .venv/bin/python scripts/eval_utilization.py [--base URL] [--n 1] [--min-util 0.35]
"""
from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.request

GOLD = [
    {"q": "What treatments exist for obesity in adults?", "sources": ["clinicaltrials", "web"]},
    {"q": "What treatments are being studied for rheumatoid arthritis?", "sources": ["clinicaltrials", "web"]},
    {"q": "What treatments exist for type 2 diabetes in adults?", "sources": ["clinicaltrials", "web"]},
]


def _ask(base, q, sources, timeout=200.0):
    body = json.dumps({"question": q, "tenant_id": "demo", "sources": sources}).encode()
    req = urllib.request.Request(base.rstrip("/") + "/research", data=body,
                                 headers={"content-type": "application/json"}, method="POST")
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode())


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default="https://noesis-api-production.up.railway.app")
    ap.add_argument("--n", type=int, default=1)
    ap.add_argument("--min-util", type=float, default=0.35)
    args = ap.parse_args()

    worst = 1.0
    print(f"Utilization eval — base={args.base} n={args.n} min-util={args.min_util}\n")
    for case in GOLD:
        for _ in range(args.n):
            t0 = time.time()
            try:
                d = _ask(args.base, case["q"], case["sources"])
            except Exception as e:   # noqa: BLE001
                print(f"  [ERR] {case['q'][:50]!r}: {e}"); worst = 0.0; continue
            el = round(time.time() - t0)
            ss = d.get("source_stats", {})
            ret = sum(v.get("retrieved", 0) for v in ss.values())
            cited = sum(v.get("cited", 0) for v in ss.values())
            util = (cited / ret) if ret else 0.0
            web = ss.get("web", {})
            worst = min(worst, util)
            flag = "OK " if util >= args.min_util else "LOW"
            print(f"  [{flag}] {el}s util={cited}/{ret}={util:.0%} "
                  f"web={web.get('cited', 0)}/{web.get('retrieved', 0)} "
                  f"grounded={d.get('grounded')} rejected={d.get('rejected')} | {case['q'][:48]}")
    ok = worst >= args.min_util
    print(f"\nworst utilization: {worst:.0%} (min {args.min_util:.0%}) → {'PASS' if ok else 'FAIL'}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
