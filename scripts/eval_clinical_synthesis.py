"""Held-out CLINICAL-SYNTHESIS eval — gates the NOESIS_CLINICAL_SYNTHESIS answer directive.

The synthesis flag sharpens HOW a grounded answer is written (scope-up-front, registry=protocol-
not-efficacy, surrogate≠clinical endpoint, preserve specific figures, no citation stacking, no vague
hype). "Synthesis quality" resists string-match, so this uses an LLM judge — but only AFTER hard,
deterministic gates, and the judge may credit a rubric dimension ONLY for content backed by a
verified finding. That keeps the score un-gameable by fluent-but-uncited prose (the panel's #1 risk):
every `claims[]` entry already passed the server-side span + entailment gates, and the answer's [n]
refs must resolve to them — so a high score is earnable only by real, supported claims.

A/B is SERVER-AUTHORITATIVE (Rule 20): the flag lives in the prod env, not the request. Run it once
per variant and diff:
  # baseline (flag OFF in prod):
  .venv/bin/python scripts/eval_clinical_synthesis.py --variant off --out /tmp/synth_off.json
  # after deploy + NOESIS_CLINICAL_SYNTHESIS=1:
  .venv/bin/python scripts/eval_clinical_synthesis.py --variant on  --out /tmp/synth_on.json
  # compare:
  .venv/bin/python scripts/eval_clinical_synthesis.py --compare /tmp/synth_off.json /tmp/synth_on.json

Provenance (Rule 11): each result records model, judge model, git SHA, timestamp, and the raw
(question, answer, claims, scores) so a run is reproducible. Costs credits — run deliberately.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import time
import urllib.request

# Held-out, DIVERSE question types — NONE appear in any prompt, few-shot, fixture, or eval_gold
# (Rule 5). The point is adversarial breadth (Rule 7): a fixed clinician template overfit to
# multi-option treatment questions should be PUNISHED here on mechanism/diagnosis/epidemiology/
# single-drug/no-direct questions, where it would force empty or fabricated sections.
GOLD = [
    {"q": "What treatments exist for Parkinson disease in adults?",
     "type": "treatment_multi_option", "sources": ["clinicaltrials", "europepmc", "web"], "budget": 4000},
    {"q": "What are the reported adverse effects of methotrexate?",
     "type": "single_drug_safety", "sources": ["europepmc", "faers", "web"], "budget": 3200},
    {"q": "What is the mechanism of action of SGLT2 inhibitors?",
     "type": "mechanism", "sources": ["europepmc", "web"], "budget": 2600},
    {"q": "How is systemic lupus erythematosus diagnosed?",
     "type": "diagnosis", "sources": ["europepmc", "web"], "budget": 3000},
    {"q": "How common is atrial fibrillation in adults?",
     "type": "epidemiology", "sources": ["europepmc", "cdc", "web"], "budget": 2400},
    {"q": "How does semaglutide compare to tirzepatide for weight loss?",
     "type": "comparative", "sources": ["clinicaltrials", "europepmc", "web"], "budget": 3600},
    # Deliberately thin/no-direct: honesty test — a good answer states the gap, does NOT fabricate a
    # criterion. Flag ON must not degrade this into invented clinical detail.
    {"q": "What criteria guide biliary drain removal timing after subtotal cholecystectomy?",
     "type": "no_direct_evidence", "sources": ["europepmc", "web"], "budget": 2200},
]

_RUBRIC_SYSTEM = (
    "You are a strict clinician-grade evaluator of a medical research answer. You are given the "
    "QUESTION, the VERIFIED FINDINGS (the ONLY facts the answer was allowed to use — each already "
    "verbatim-verified against a real source), and the ANSWER.\n"
    "Score each dimension 0 (poor), 1 (adequate), 2 (strong). Output STRICT JSON: "
    '{"scores":{"directness":n,"scope":n,"evidence_status":n,"quant_fidelity":n,"endpoint_discipline":n,'
    '"comparative":n,"scannability":n},"provenance_hard_fail":true|false,"notes":"<=40 words"}.\n'
    "RULES:\n"
    "- directness: does it answer the actual question, or clearly state what the evidence can't settle?\n"
    "- scope: does it scope to the population/intervention/setting the findings cover, without overreach?\n"
    "- evidence_status: does it label evidence honestly — trial-REGISTRY entries as protocol/design "
    "intent, NOT efficacy; respects guideline>SR>RCT>observational?\n"
    "- quant_fidelity: does it PRESERVE specific figures that are present in the findings (not restate "
    "them as vague prose), and INVENT no number absent from the findings?\n"
    "- endpoint_discipline: does it avoid presenting a surrogate (lab/index) as a clinical outcome "
    "(event/mortality) unless a finding says so?\n"
    "- comparative: ONLY applies when the question or findings involve multiple comparable options — "
    "then reward head-to-head/shared-outcome comparison and PENALIZE stacking many citations on one "
    "consensus claim. If no comparison is applicable, score 2 (not penalized).\n"
    "- scannability: concise, no filler, no empty headings, no boilerplate disclaimer. Do NOT reward length.\n"
    "- provenance_hard_fail = TRUE if the ANSWER asserts ANY specific clinical fact (a drug, dose, "
    "outcome, criterion, mechanism, number) that is NOT supported by the VERIFIED FINDINGS. This is the "
    "critical gate: fluent prose that goes beyond the findings must hard-fail regardless of style."
)


def _ask(base, q, sources, timeout=220.0):
    body = json.dumps({"question": q, "tenant_id": "demo", "sources": sources}).encode()
    req = urllib.request.Request(base.rstrip("/") + "/research", data=body,
                                 headers={"content-type": "application/json"}, method="POST")
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode())


def _config(base):
    try:
        with urllib.request.urlopen(base.rstrip("/") + "/config", timeout=20) as r:
            return json.loads(r.read().decode())
    except Exception:  # noqa: BLE001
        return {}


def _judge(client, model, question, claims, answer):
    findings = "\n".join(f"[{i+1}] {c.get('text','')}  (quote: \"{c.get('quote','')[:200]}\")"
                         for i, c in enumerate(claims)) or "(no verified findings)"
    user = (f"QUESTION:\n{question}\n\nVERIFIED FINDINGS:\n{findings}\n\nANSWER:\n{answer}\n\n"
            "Return ONLY the JSON.")
    resp = client.chat.completions.create(
        model=model, response_format={"type": "json_object"},
        messages=[{"role": "system", "content": _RUBRIC_SYSTEM}, {"role": "user", "content": user}])
    return json.loads(resp.choices[0].message.content)


_DIMS = ["directness", "scope", "evidence_status", "quant_fidelity",
         "endpoint_discipline", "comparative", "scannability"]


def _gates(case, d):
    """Deterministic gates BEFORE the judge. Returns (structural_ok, brevity_ok, notes)."""
    answer = d.get("answer") or ""
    claims = d.get("claims") or []
    refs = [int(m) for m in re.findall(r"\[(\d+)\]", answer)]
    # structural/provenance: every [n] resolves to a real verified finding; an answerable question
    # must actually be grounded. A no_direct question is allowed to be ungrounded (honest gap).
    refs_ok = all(1 <= r <= len(claims) for r in refs)
    answerable = case["type"] != "no_direct_evidence"
    grounded_ok = bool(d.get("grounded")) if answerable else True
    structural_ok = refs_ok and grounded_ok and (bool(refs) or not answerable)
    brevity_ok = len(answer) <= case["budget"]
    notes = []
    if not refs_ok:
        notes.append("dangling [n] ref")
    if answerable and not d.get("grounded"):
        notes.append("expected grounded, got none")
    if not brevity_ok:
        notes.append(f"len {len(answer)}>{case['budget']}")
    return structural_ok, brevity_ok, "; ".join(notes)


def _score_case(case, d, judge_out):
    """Overall 0..2. Zeroed by a provenance/structural hard-fail (un-gameable by verbose prose)."""
    structural_ok, brevity_ok, gate_notes = _gates(case, d)
    hard_fail = judge_out.get("provenance_hard_fail") is True or not structural_ok
    scores = judge_out.get("scores") or {}
    dims = [float(scores.get(k, 0)) for k in _DIMS]
    base = sum(dims) / len(dims) if dims else 0.0
    if not brevity_ok:
        base *= 0.75          # soft penalty for bloat (the opposite of the goal)
    overall = 0.0 if hard_fail else base
    return {"overall": round(overall, 2), "hard_fail": hard_fail, "structural_ok": structural_ok,
            "brevity_ok": brevity_ok, "gate_notes": gate_notes,
            "dims": {k: scores.get(k) for k in _DIMS}, "judge_notes": judge_out.get("notes", "")}


def run(args):
    base = args.base
    cfg = _config(base)
    server_flag = cfg.get("clinical_synthesis")
    if server_flag is not None and (server_flag is True) != (args.variant == "on"):
        print(f"  [WARN] server /config clinical_synthesis={server_flag} but --variant={args.variant} "
              f"— label may not match the deployed flag.\n")
    from openai import OpenAI
    client = OpenAI()
    jmodel = os.environ.get("NOESIS_EVAL_JUDGE_MODEL", "gpt-4o")
    try:
        sha = subprocess.check_output(["git", "rev-parse", "--short", "HEAD"]).decode().strip()
    except Exception:  # noqa: BLE001
        sha = "?"
    stamp = time.strftime("%Y-%m-%dT%H:%M:%S")
    print(f"Clinical-synthesis eval — base={base} variant={args.variant} judge={jmodel} "
          f"sha={sha} server_flag={server_flag}\n")
    results = []
    for case in GOLD:
        t0 = time.time()
        try:
            d = _ask(base, case["q"], case["sources"])
        except Exception as e:  # noqa: BLE001
            print(f"  [ERR] {case['type']:20} {e}")
            results.append({"case": case, "error": str(e), "score": {"overall": 0.0, "hard_fail": True}})
            continue
        try:
            jout = _judge(client, jmodel, case["q"], d.get("claims") or [], d.get("answer") or "")
        except Exception as e:  # noqa: BLE001
            jout = {"scores": {}, "provenance_hard_fail": False, "notes": f"judge error: {e}"}
        sc = _score_case(case, d, jout)
        el = round(time.time() - t0)
        tag = "FAIL" if sc["hard_fail"] else ("BLOAT" if not sc["brevity_ok"] else "OK  ")
        print(f"  [{tag}] {case['type']:20} score={sc['overall']:.2f} "
              f"claims={len(d.get('claims') or [])} grounded={d.get('grounded')} {el}s"
              + (f"  ⚠ {sc['gate_notes']}" if sc["gate_notes"] else ""))
        results.append({"case": case, "score": sc,
                        "answer": d.get("answer"), "claims": d.get("claims"),
                        "grounded": d.get("grounded"), "source_stats": d.get("source_stats")})
    scored = [r for r in results if "score" in r]
    mean = sum(r["score"]["overall"] for r in scored) / len(scored) if scored else 0.0
    hard_fails = sum(1 for r in scored if r["score"]["hard_fail"])
    print(f"\nmean score: {mean:.2f}/2.00 · provenance/structural hard-fails: {hard_fails}/{len(scored)}")
    payload = {"variant": args.variant, "base": base, "judge": jmodel, "sha": sha, "at": stamp,
               "mean": round(mean, 3), "hard_fails": hard_fails, "n": len(scored), "results": results}
    if args.out:
        with open(args.out, "w") as f:
            json.dump(payload, f, indent=2)
        print(f"wrote {args.out}")
    # A hard-fail is never acceptable; mean is informational for the A/B diff.
    return 1 if hard_fails else 0


def compare(a_path, b_path):
    a = json.load(open(a_path)); b = json.load(open(b_path))
    print(f"COMPARE  {a['variant']}(sha {a.get('sha')}) → {b['variant']}(sha {b.get('sha')})\n")
    print(f"  mean score   {a['mean']:.2f} → {b['mean']:.2f}  ({b['mean']-a['mean']:+.2f})")
    print(f"  hard-fails   {a['hard_fails']}/{a['n']} → {b['hard_fails']}/{b['n']}")
    ba = {r["case"]["type"]: r["score"]["overall"] for r in a["results"] if "score" in r}
    bb = {r["case"]["type"]: r["score"]["overall"] for r in b["results"] if "score" in r}
    print("\n  per question type:")
    for t in ba:
        d = bb.get(t, 0) - ba[t]
        print(f"    {t:20} {ba[t]:.2f} → {bb.get(t,0):.2f}  ({d:+.2f})")
    # Guard: flag ON must NOT introduce a hard-fail the OFF path didn't have (a regression on honesty).
    reg = b["hard_fails"] > a["hard_fails"]
    print(f"\n  {'REGRESSION — ON added hard-fails' if reg else 'no new hard-fails'}; "
          f"{'ON improves mean' if b['mean']>a['mean'] else 'ON does not improve mean'}")
    return 1 if reg else 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default="https://noesis-api-production.up.railway.app")
    ap.add_argument("--variant", choices=["off", "on"], default="off",
                    help="label for this run — must match the deployed server flag state")
    ap.add_argument("--out", default="")
    ap.add_argument("--compare", nargs=2, metavar=("OFF_JSON", "ON_JSON"))
    args = ap.parse_args()
    if args.compare:
        return compare(*args.compare)
    return run(args)


if __name__ == "__main__":
    sys.exit(main())
