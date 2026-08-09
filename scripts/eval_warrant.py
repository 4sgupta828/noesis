"""Warrant eval — measure how often Noesis answers break the Answer-Warrant Contract (W1–W9).

This is STEP 1 of docs/specs/answer-warrant-contract.md: before building the auditor, measure whether
the failure modes are actually frequent. It runs each case-shaped question through the live product,
then an LLM judge scores the answer against the nine warrant failure modes (the SAME rubric the auditor
will later enforce and the feedback log will accumulate — one contract, three uses).

Every judged answer is appended to an accumulating JSONL (NOESIS_EVAL_LOG, default
data/eval/warrant_runs.jsonl) with the git SHA, judge model, and full inputs/outputs — so the signal
builds up over time and each run is reproducible (Rule 11). Provenance note (Rule 6): the judge is fed
each claim's surrounding source TEXT, not just the verbatim quote — a quote-only judge rubber-stamps.

Usage:
    # baseline over the seed set (hits prod for answers; one judge call per case)
    NOESIS_URL=https://noesis-api-production.up.railway.app .venv/bin/python scripts/eval_warrant.py
    SUBSET=nms_delirium,digoxin_toxicity  MODE=research  .venv/bin/python scripts/eval_warrant.py
    MODE=panel  .venv/bin/python scripts/eval_warrant.py     # judge the specialist-panel answer instead

Needs ANTHROPIC creds for the judge (source ./.env.medical). The CASE SET below is a SEED skeleton —
the gold, clinically-reviewed set must be curated with a physician; these are structural placeholders.
"""
import datetime as _dt
import json
import os
import subprocess
import sys
import urllib.request
from typing import Literal

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "packages", "kernel"))
from pydantic import BaseModel, Field  # noqa: E402
from noesis_kernel.runtime.build import build_llm  # noqa: E402

BASE = os.environ.get("NOESIS_URL", "https://noesis-api-production.up.railway.app").rstrip("/")
MODE = os.environ.get("MODE", "research")            # "research" (Quick Q&A) | "panel"
TENANT = os.environ.get("TENANT", "demo")
SUBSET = {s.strip() for s in os.environ.get("SUBSET", "").split(",") if s.strip()}
LOG = os.environ.get("NOESIS_EVAL_LOG", os.path.join(os.path.dirname(__file__), "..", "data", "eval", "warrant_runs.jsonl"))
REQ_TIMEOUT = int(os.environ.get("REQ_TIMEOUT", "420"))

# Case-shaped questions where warrant failures are most likely to surface. SEED skeleton — replace/grow
# with a physician-curated gold set. Kept deliberately terse; the point is to exercise the judge.
CASES = {
    "nms_delirium":      "72-year-old on a new antipsychotic develops fever, rigidity, and confusion — what is the initial diagnostic workup and management?",
    "digoxin_toxicity":  "Elderly patient on digoxin and a new diuretic presents with nausea and a slow irregular pulse — how should this be evaluated and managed?",
    "afib_anticoag":     "70-year-old with new atrial fibrillation, CKD stage 4, and prior GI bleed — how should anticoagulation be approached?",
    "peds_fever":        "3-week-old infant with a fever of 38.5°C and no obvious source — what is the recommended evaluation and management?",
    "sepsis_source":     "68-year-old diabetic with hypotension, confusion, and leukocytosis — how should suspected sepsis be worked up and treated in the first hour?",
    "serotonin_vs_nms":  "Patient on an SSRI and a newly added antiemetic develops agitation, clonus, and hyperthermia — how do you distinguish and manage the likely cause?",
}

# ---- the ONE rubric: W1–W9 (see docs/specs/answer-warrant-contract.md §2) ----
_W = {
 "W1": "Unwarranted: the cited source does not actually establish the claim (mentions the topic only).",
 "W2": "Descriptive→normative: a description of what happened ('X was done') used to justify a recommendation ('do X').",
 "W3": "Inapplicable: the source is real/supportive but for the wrong population, setting, or purpose.",
 "W4": "Tier-mismatch: a weak source (case report/anecdote) driving a routine/strong recommendation where better evidence should exist.",
 "W5": "Coverage gap: a materially plausible, actionable option/branch is omitted.",
 "W6": "Salience distortion: the answer over-weights whatever had the most evidence rather than what matters most.",
 "W7": "Conditionality collapse: a 'do only if X' action presented as routine/unconditional.",
 "W8": "Contradiction: a recommendation conflicts with a stated safety caveat elsewhere in the answer.",
 "W9": "Miscalibration: stated confidence does not match the evidence's strength/applicability.",
}


class ClaimVerdict(BaseModel):
    claim_index: int
    recommendation_bearing: bool = False
    warranted: bool = True
    failure_modes: list[Literal["W1", "W2", "W3", "W4", "W7"]] = Field(default_factory=list)
    note: str = ""


class AnswerVerdict(BaseModel):
    claim_verdicts: list[ClaimVerdict] = Field(default_factory=list)
    coverage_gap: bool = False        # W5
    salience_distortion: bool = False  # W6
    contradiction: bool = False        # W8
    miscalibration: bool = False       # W9
    summary: str = ""


_JUDGE_SYS = (
    "You are a rigorous attending physician auditing an AI-generated clinical answer for WARRANT — "
    "not for whether it cites sources (it does), but for whether each recommendation is actually "
    "justified by evidence that applies and supports the specific inference. Judge ONLY what the "
    "provided findings support; you are checking warrant, not writing a better answer. Be conservative: "
    "flag a failure only when clearly present. These are semantic judgments — reason about meaning, do "
    "not pattern-match words.\n\nFailure modes:\n" + "\n".join(f"{k}: {v}" for k, v in _W.items())
)


def _final_from_stream(url, body):
    req = urllib.request.Request(url, json.dumps(body).encode(), {"Content-Type": "application/json"})
    final = None
    with urllib.request.urlopen(req, timeout=REQ_TIMEOUT) as r:
        buf = b""
        for chunk in r:
            buf += chunk
            while b"\n\n" in buf:
                frame, buf = buf.split(b"\n\n", 1)
                for line in frame.decode(errors="replace").split("\n"):
                    if line.startswith("data:"):
                        ev = json.loads(line[5:].strip())
                        if ev.get("type") == "final":
                            final = ev.get("result")
    return final


def get_answer(question):
    if MODE == "panel":
        r = _final_from_stream(BASE + "/panel/ask/stream", {"question": question, "tenant_id": TENANT})
        return (r or {}).get("synthesis", ""), (r or {}).get("claims", []) or []
    r = _final_from_stream(BASE + "/research/stream", {"question": question, "tenant_id": TENANT})
    return (r or {}).get("answer", ""), (r or {}).get("claims", []) or []


def _sha():
    try:
        return subprocess.check_output(["git", "rev-parse", "--short", "HEAD"],
                                       cwd=os.path.dirname(__file__)).decode().strip()
    except Exception:
        return "?"


def main():
    import asyncio
    llm = build_llm(mode="live")
    sha, model = _sha(), os.environ.get("NOESIS_LLM_MODEL", "default")
    os.makedirs(os.path.dirname(LOG), exist_ok=True)
    cases = [(cid, q) for cid, q in CASES.items() if not SUBSET or cid in SUBSET]
    tally = {k: 0 for k in _W}
    total_recs = 0
    print(f"warrant eval · mode={MODE} · {len(cases)} cases · log={LOG}\n")
    for cid, q in cases:
        try:
            answer, claims = get_answer(q)
            if not answer:
                print(f"  {cid:18s} NO ANSWER"); continue
            v = asyncio.run(_judge_async(llm, q, answer, claims))
        except Exception as e:  # noqa: BLE001
            print(f"  {cid:18s} ERROR {e}"); continue
        rec = [cv for cv in v.claim_verdicts if cv.recommendation_bearing]
        total_recs += len(rec)
        modes = {m for cv in v.claim_verdicts for m in cv.failure_modes}
        for lvl in ("coverage_gap", "salience_distortion", "contradiction", "miscalibration"):
            if getattr(v, lvl):
                modes.add({"coverage_gap": "W5", "salience_distortion": "W6",
                           "contradiction": "W8", "miscalibration": "W9"}[lvl])
        for m in modes:
            tally[m] += 1
        # persist (accumulating feedback log — the same store the auditor + user feedback will feed)
        with open(LOG, "a") as f:
            f.write(json.dumps({
                "ts": _dt.datetime.now(_dt.timezone.utc).isoformat(), "git_sha": sha,
                "judge_model": model, "mode": MODE, "case_id": cid, "question": q,
                "n_claims": len(claims), "n_recs": len(rec), "answer": answer,
                "verdict": v.model_dump(),
            }) + "\n")
        print(f"  {cid:18s} recs={len(rec):2d}  flags={','.join(sorted(modes)) or '—'}")
    print("\n=== warrant failure counts (cases flagged / total) ===")
    n = len(cases)
    for k in _W:
        print(f"  {k}  {tally[k]:2d}/{n}   {_W[k][:60]}")
    print(f"\nrecommendation-bearing claims judged: {total_recs}")
    print(f"log now has {sum(1 for _ in open(LOG))} total records (accumulating).")


async def _judge_async(llm, q, a, c):
    findings = "\n".join(
        f"[{i+1}] {cl.get('text','')}\n     quote: \"{cl.get('quote','')}\"  — {cl.get('source','')}"
        for i, cl in enumerate(c))
    user = (f"QUESTION:\n{q}\n\nANSWER:\n{a}\n\nFINDINGS (surrounding source text + verbatim quote — "
            f"judge against the TEXT):\n{findings}\n\nFor each recommendation-bearing claim decide warrant "
            "and list W1–W4/W7 with claim_index; then set coverage_gap(W5)/salience_distortion(W6)/"
            "contradiction(W8)/miscalibration(W9).")
    comp = await llm.complete(system=_JUDGE_SYS, messages=[{"role": "user", "content": user}],
                              response_format=AnswerVerdict, max_tokens=1500)
    return comp.parsed


if __name__ == "__main__":
    main()
