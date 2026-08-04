"""Held-out QUANTITATIVE-RECALL eval — the instrument for the evidence-selection work.

The panel's Rule-4 blind spot: NO existing eval measures whether a specific effect size / CI that
EXISTS in a corpus block actually reached the answer. `eval_utilization` measures cited/retrieved
ratio; `eval_clinical_synthesis`'s quant_fidelity only checks figures ALREADY in the findings — so a
number silently truncated by `_ATOM_CAP` (before it could ever become a finding) scores fine. This
eval closes that gap: for held-out questions, assert a specific numeric figure appears in the ANSWER.

It separates the two failure modes honestly (Rule 6 — provenance vs correctness):
  - CORPUS-GAP: the figure isn't anywhere in the retrieved evidence → not a recall failure, a coverage
    gap. (Detected via the cited quotes, and — if NOESIS_CORPUS_DSN is set — a direct corpus probe.)
  - RECALL-MISS: the figure IS in the retrieved/cited evidence but NOT in the answer → the exact thing
    the atom-cap + claim-ranking fixes target.

A/B usage (server-authoritative flag, Rule 20):
  .venv/bin/python scripts/eval_evidence_recall.py --variant off --out /tmp/recall_off.json
  # set NOESIS_EVIDENCE_SELECT=1 (+ NOESIS_ATOM_CAP), redeploy, then:
  .venv/bin/python scripts/eval_evidence_recall.py --variant on  --out /tmp/recall_on.json
  .venv/bin/python scripts/eval_evidence_recall.py --compare /tmp/recall_off.json /tmp/recall_on.json

Costs credits — run deliberately. Gold targets figures expected in the OA full-text corpus; tune the
patterns against the live corpus if a case is a persistent CORPUS-GAP (that means we lack the source,
not that the pipeline missed it).
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import time
import urllib.request

# Held-out gold — the DISCRIMINATING set. Each figure was verified (via a direct corpus probe) to
# live ONLY past char ~1600 of a full-text europepmc block — i.e. inside the zone the old _ATOM_CAP
# truncated. Sources are CORPUS-ONLY (no web) so the figure can't sneak in via a news page — it can
# reach the answer only if the full-text extractor actually saw it. `known_in_corpus=True` means a
# miss is a true HAD-BUT-DROPPED, not a coverage gap. (A saturated "headline figures" set — semaglutide
# 15%, SELECT HR 0.80 — scored 6/6 OFF and could NOT measure the fix; that's why it was replaced.)
_CORPUS = ["europepmc", "clinicaltrials", "openfda", "faers"]
GOLD = [
    {"q": "What was the estimated effectiveness of 2024-2025 COVID-19 vaccination against "
          "COVID-19-associated hospitalization?",
     "pat": r"\b40\s?%|95%\s*CI[,:]?\s*27", "label": "COVID 2024-25 VE 40% (CI 27-51)",
     "known_in_corpus": True, "sources": _CORPUS},
    {"q": "How did thrombolysis costs with tenecteplase compare to alteplase for acute ischaemic "
          "stroke in elderly patients?",
     "pat": r"\b30\s?%\s*lower|\b30\s?%", "label": "tenecteplase ~30% lower cost",
     "known_in_corpus": True, "sources": _CORPUS},
    {"q": "What was the specificity of point-of-care HPV DNA testing for detecting cervical disease?",
     "pat": r"\b63\.3\s?%|\b6[0-3](?:\.\d)?\s?%", "label": "HPV POC test specificity 63.3%",
     "known_in_corpus": True, "sources": _CORPUS},
    {"q": "What was the magnitude and significance of symptom reduction with psilocybin-assisted therapy "
          "in the reported pilot outcomes?",
     "pat": r"\b27\.5\b|d\s*=\s*2\.3|p\s*<\s*0?\.001", "label": "psilocybin MD 27.5 / d=2.30 / p<0.001",
     "known_in_corpus": True, "sources": _CORPUS},
    {"q": "In the malaria vector-control combination study, how much faster was the reduction in test "
          "positivity rate compared with the reference district?",
     "pat": r"\b5\s*times faster|0\.006|0\.56\s?%", "label": "malaria TPR ~5x faster / 0.56%/mo",
     "known_in_corpus": True, "sources": _CORPUS},
]


def _ask(base, q, sources, timeout=240.0):
    body = json.dumps({"question": q, "tenant_id": "demo", "sources": sources}).encode()
    req = urllib.request.Request(base.rstrip("/") + "/research", data=body,
                                 headers={"content-type": "application/json"}, method="POST")
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode())


def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", (s or "")).strip()


def _run(args):
    base, pat_flags = args.base, re.IGNORECASE
    print(f"Evidence-recall eval — base={base} variant={args.variant}\n")
    results = []
    for case in GOLD:
        pat = re.compile(case["pat"], pat_flags)
        t0 = time.time()
        try:
            d = _ask(base, case["q"], case["sources"])
        except Exception as e:  # noqa: BLE001
            print(f"  [ERR] {case['label'][:34]}: {e}")
            results.append({"case": case, "error": str(e)}); continue
        el = round(time.time() - t0)
        ans = _norm(d.get("answer") or "")
        quotes = _norm(" ".join(c.get("quote", "") for c in (d.get("claims") or [])))
        in_answer = bool(pat.search(ans))
        in_evidence = bool(pat.search(quotes))     # figure present in a CITED quote
        # Classify. For known-in-corpus gold, a non-answer is a true HAD-BUT-DROPPED (MISS) — the
        # figure provably exists in a corpus block, so failing to surface it is the pipeline, not
        # coverage. (Otherwise fall back to the cited-evidence heuristic to separate gap vs miss.)
        if in_answer:
            verdict = "RECALL"
        elif case.get("known_in_corpus"):
            verdict = "MISS"
        else:
            verdict = "CORPUS-GAP" if not in_evidence else "MISS"
        tag = {"RECALL": "OK  ", "MISS": "MISS", "CORPUS-GAP": "GAP "}[verdict]
        print(f"  [{tag}] {el}s claims={len(d.get('claims') or [])} in_answer={in_answer} "
              f"in_evidence={in_evidence} | {case['label']}")
        results.append({"case": case, "verdict": verdict, "in_answer": in_answer,
                        "in_evidence": in_evidence, "answer": ans[:600]})
    scored = [r for r in results if "verdict" in r]
    recall = sum(1 for r in scored if r["verdict"] == "RECALL")
    misses = sum(1 for r in scored if r["verdict"] == "MISS")
    gaps = sum(1 for r in scored if r["verdict"] == "CORPUS-GAP")
    print(f"\nRECALL {recall}/{len(scored)} · MISS(had-but-dropped) {misses} · CORPUS-GAP {gaps}")
    print("  (MISS is the number the atom-cap + claim-ranking fixes should drive DOWN;")
    print("   CORPUS-GAP is a sourcing problem, not a pipeline problem.)")
    payload = {"variant": args.variant, "base": base, "recall": recall, "misses": misses,
               "gaps": gaps, "n": len(scored), "results": results}
    if args.out:
        json.dump(payload, open(args.out, "w"), indent=2); print(f"wrote {args.out}")
    return 0 if misses == 0 else 1


def _compare(a_path, b_path):
    a, b = json.load(open(a_path)), json.load(open(b_path))
    print(f"COMPARE {a['variant']} → {b['variant']}\n")
    print(f"  RECALL {a['recall']}/{a['n']} → {b['recall']}/{b['n']}  ({b['recall']-a['recall']:+d})")
    print(f"  MISS   {a['misses']} → {b['misses']}  ({b['misses']-a['misses']:+d})  <- want DOWN")
    print(f"  GAP    {a['gaps']} → {b['gaps']}  (sourcing, not pipeline)")
    reg = b["recall"] < a["recall"] or b["misses"] > a["misses"]
    print(f"\n  {'REGRESSION' if reg else 'no regression'}; "
          f"{'ON improves recall' if b['recall'] > a['recall'] else 'no recall gain'}")
    return 1 if reg else 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default="https://noesis-api-production.up.railway.app")
    ap.add_argument("--variant", choices=["off", "on"], default="off")
    ap.add_argument("--out", default="")
    ap.add_argument("--compare", nargs=2, metavar=("OFF_JSON", "ON_JSON"))
    args = ap.parse_args()
    return _compare(*args.compare) if args.compare else _run(args)


if __name__ == "__main__":
    sys.exit(main())
