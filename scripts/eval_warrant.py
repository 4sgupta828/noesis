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

# Wide (every specialty) + deep (multi-system) case set, each tagged with the warrant modes it probes.
# Curated in the vertical so it evolves with the roster; falls back to a tiny inline seed if unavailable.
try:
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "packages", "vertical_medical"))
    from noesis_vertical_medical.eval_warrant_cases import WARRANT_CASES as _CASES
except Exception:   # noqa: BLE001
    _CASES = {"nms_delirium": {"q": "72-year-old on a new antipsychotic develops fever, rigidity, and "
              "confusion — what is the initial diagnostic workup and management?",
              "specialties": ["psychiatry"], "probes": ["W5"], "depth": "focused"}}
DEPTH = os.environ.get("DEPTH", "")   # "" = all · "focused" · "multisystem"
CASES = {cid: m for cid, m in _CASES.items() if not DEPTH or m.get("depth") == DEPTH}

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


class Flag(BaseModel):
    """One warrant failure the judge raises. Compact: only RAISED flags are emitted (not a row per
    claim) so output scales regardless of answer size. Falsifiability spans are checked in code."""
    mode: Literal["W1", "W2", "W3", "W4", "W5", "W6", "W7", "W8", "W9"]
    claim_index: int | None = Field(default=None, description="1-based finding index for claim-level modes; null for answer-level")
    answer_span: str = Field(default="", description="verbatim phrase FROM THE ANSWER this flag is about (required for W1-W4/W7/W8)")
    source_span: str = Field(default="", description="verbatim phrase FROM THE CITED FINDING (required for W1-W4)")
    missing_option: str = Field(default="", description="for W5: the SPECIFIC omitted actionable option (must NOT be in the answer)")
    note: str = ""


class AnswerVerdict(BaseModel):
    flags: list[Flag] = Field(default_factory=list)
    n_recommendations: int = Field(default=0, description="how many recommendation-bearing statements the answer makes (denominator)")
    summary: str = ""


# Which modes require which spans to be falsifiable (structural gate, Rule-18-clean).
_NEEDS_ANSWER_SPAN = {"W1", "W2", "W3", "W4", "W7", "W8"}
_NEEDS_SOURCE_SPAN = {"W1", "W2", "W3", "W4"}

_JUDGE_SYS = (
    "You are a rigorous attending physician auditing an AI-generated clinical answer for WARRANT — "
    "not for whether it cites sources (it does), but for whether each recommendation is actually "
    "justified by evidence that applies and supports the specific inference. Judge ONLY what the "
    "provided findings support; you are checking warrant, not writing a better answer. These are "
    "semantic judgments — reason about meaning, do not pattern-match words.\n\n"
    "EMIT ONLY the flags you actually raise (do not enumerate every claim). Set n_recommendations to how "
    "many recommendation-bearing statements the answer makes.\n\n"
    "BE CONSERVATIVE AND FALSIFIABLE — raise a flag ONLY with concrete copied evidence:\n"
    "- W1-W4/W7/W8: `answer_span` = a VERBATIM phrase copied from the ANSWER; W1-W4 also need `source_span` "
    "= a VERBATIM phrase from the cited finding (set `claim_index`). If you can't copy the span(s), omit it.\n"
    "- W5 (coverage gap): `missing_option` = a SPECIFIC actionable option, only after confirming it is NOT "
    "anywhere in the answer.\n"
    "- W6/W9 are holistic; still copy an `answer_span` you're reacting to when you can.\n"
    "A flag you can't ground in copied spans is noise — omit it.\n\nFailure modes:\n"
    + "\n".join(f"{k}: {v}" for k, v in _W.items())
)


def _filter_verdict(v, answer, claims):
    """Drop flags whose concrete spans don't actually exist (Rule-18-clean falsifiability — kills the
    LLM-judge's habit of inventing gaps/challenges). Structural checks only; the LLM still owns meaning."""
    al = answer.lower()

    def _in(s, hay):
        return bool(s) and s.strip().lower() in hay
    kept = []
    for f in v.flags:
        if f.mode in _NEEDS_ANSWER_SPAN and not _in(f.answer_span, al):
            continue                                        # challenged phrase isn't in the answer → fabricated
        if f.mode in _NEEDS_SOURCE_SPAN:
            src = ""
            if f.claim_index and 1 <= f.claim_index <= len(claims):
                c = claims[f.claim_index - 1]
                src = (str(c.get("text", "")) + " " + str(c.get("quote", ""))).lower()
            if not _in(f.source_span, src):
                continue                                    # cited source span isn't in the finding → fabricated
        if f.mode == "W5" and (not f.missing_option or _in(f.missing_option, al)):
            continue                                        # the "missing" option is actually present → not a gap
        kept.append(f)
    v.flags = kept
    return v


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
    cases = [(cid, m) for cid, m in CASES.items() if not SUBSET or cid in SUBSET]
    tally = {k: 0 for k in _W}
    total_recs = 0
    print(f"warrant eval · mode={MODE} · {len(cases)} cases · log={LOG}\n")
    for cid, meta in cases:
        q = meta["q"] if isinstance(meta, dict) else meta
        try:
            answer, claims = get_answer(q)
            if not answer:
                print(f"  {cid:18s} NO ANSWER"); continue
            v = asyncio.run(_judge_async(llm, q, answer, claims))
            v = _filter_verdict(v, answer, claims)   # drop ungrounded/over-flagged verdicts
        except Exception as e:  # noqa: BLE001
            print(f"  {cid:26s} ERROR {e}"); continue
        total_recs += v.n_recommendations
        modes = {f.mode for f in v.flags}
        for m in modes:
            tally[m] += 1
        # persist (accumulating feedback log — the same store the auditor + user feedback will feed)
        with open(LOG, "a") as f:
            f.write(json.dumps({
                "ts": _dt.datetime.now(_dt.timezone.utc).isoformat(), "git_sha": sha,
                "judge_model": model, "mode": MODE, "case_id": cid, "question": q,
                "specialties": (meta.get("specialties") if isinstance(meta, dict) else []),
                "probes": (meta.get("probes") if isinstance(meta, dict) else []),
                "depth": (meta.get("depth") if isinstance(meta, dict) else ""),
                "n_claims": len(claims), "n_recs": v.n_recommendations, "answer": answer,
                # trimmed findings so downstream auditors (C1 probe) can check entailment offline
                "claims": [{"text": c.get("text", ""), "quote": c.get("quote", ""),
                            "source": c.get("source", "")} for c in claims],
                "verdict": v.model_dump(),
            }) + "\n")
        print(f"  {cid:26s} recs={v.n_recommendations:2d}  flags={','.join(sorted(modes)) or '—'}")
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
            f"judge against the TEXT):\n{findings}\n\nReturn ONLY the warrant flags you can ground in copied "
            "spans (W1-W4/W7 with claim_index + answer_span + source_span; W5 with missing_option; W6/W8/W9 "
            "with an answer_span where possible), plus n_recommendations. Do not enumerate every claim.")
    comp = await llm.complete(system=_JUDGE_SYS, messages=[{"role": "user", "content": user}],
                              response_format=AnswerVerdict, max_tokens=3000)
    return comp.parsed


if __name__ == "__main__":
    main()
