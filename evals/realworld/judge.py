"""T2 judge for K-QA runs (plan v2, amendment B5): per answer, ONE batched LLM call grades
every gold must-have statement (covered / missing / contradicted by the answer), plus a
failure-taxonomy bucket for weak answers (trace-aware: the classifier sees the searched
queries and graph legs, not just final text — amendment B6).

Provenance pinned per Rule 11 (judge model + prompt hash recorded per judgment).
Calibration (B5): --double-grade N re-judges N answers with the OpenAI model; agreement is
reported so deltas aren't trusted on an uncalibrated judge.

Usage:
  .venv/bin/python evals/realworld/judge.py runs/run-<...>.jsonl [--double-grade 5] --confirm-spend
"""
from __future__ import annotations

import argparse
import asyncio
import datetime as dt
import hashlib
import json
import os
import pathlib
import subprocess
import sys
from typing import Literal

ROOT = pathlib.Path(__file__).resolve().parents[2]
HERE = pathlib.Path(__file__).parent
for p in ("apps", "packages/kernel", "packages/vertical_medical"):
    sys.path.insert(0, str(ROOT / p))

from pydantic import BaseModel, Field  # noqa: E402

# KERNEL-NEUTRAL grading directive (works for any vertical's gold-fact datasets; a vertical
# may append domain guidance via --domain-directive or a manifest field when one exists).
_JUDGE_SYSTEM = """You grade an answer against GOLD must-have facts written by domain experts.

For EACH gold statement, judge how the answer treats it:
- covered: the answer conveys this fact (any wording; partial numeric precision still counts
  if practically equivalent in the domain).
- missing: the answer does not convey it.
- contradicted: the answer asserts the OPPOSITE or an incompatible claim.
Judge ONLY from the answer text given. Be strict about 'contradicted' (real conflict, not
mere absence)."""

_TAXONOMY = ("missing_evidence", "wrong_evidence_selected", "ranking_failure",
             "reasoning_or_composition", "abstained_despite_evidence",
             "question_misunderstood", "not_a_failure")

_CLASSIFY_SYSTEM = """An answer under-covered its gold facts. Given the answer, the gold
facts it missed, and the engine trace (queries searched, evidence titles retrieved, graph legs),
pick the SINGLE dominant failure mode:
- missing_evidence: the corpus/web evidence needed for the missed facts was never retrieved.
- wrong_evidence_selected: relevant evidence WAS retrieved (see titles) but the answer used other, less relevant material.
- ranking_failure: relevant evidence appears late/low and was crowded out.
- reasoning_or_composition: evidence present and used, but the answer failed to state the facts.
- abstained_despite_evidence: the answer withheld/hedged despite adequate evidence.
- question_misunderstood: the answer addressed a different question.
- not_a_failure: the misses are minor/nice-to-have; the answer is fine for domain practice."""


class _StatementGrade(BaseModel):
    index: int
    verdict: Literal["covered", "missing", "contradicted"]


class _Grades(BaseModel):
    grades: list[_StatementGrade] = Field(default_factory=list)


class _Bucket(BaseModel):
    bucket: Literal["missing_evidence", "wrong_evidence_selected", "ranking_failure",
                    "reasoning_or_composition", "abstained_despite_evidence",
                    "question_misunderstood", "not_a_failure"] = "not_a_failure"
    why: str = ""


def _parse_gold(g) -> list[str]:
    if isinstance(g, list):
        return [str(x) for x in g]
    try:                                   # K-QA stores python-repr lists as strings
        import ast
        v = ast.literal_eval(g or "[]")
        return [str(x) for x in v] if isinstance(v, list) else []
    except Exception:   # noqa: BLE001
        return []


async def _judge_one(llm, row: dict) -> dict | None:
    must = _parse_gold((row.get("gold") or {}).get("must_have"))
    if not must or not (row.get("answer") or "").strip():
        return None
    numbered = "\n".join(f"[{i}] {s}" for i, s in enumerate(must))
    comp = await llm.complete(
        system=_JUDGE_SYSTEM,
        messages=[{"role": "user", "content":
                   f"ANSWER:\n{row['answer'][:8000]}\n\nGOLD MUST-HAVE FACTS:\n{numbered}"}],
        response_format=_Grades, max_tokens=600)
    by_i = {g.index: g.verdict for g in comp.parsed.grades if 0 <= g.index < len(must)}
    verdicts = [by_i.get(i, "missing") for i in range(len(must))]
    return {"must_have": must, "verdicts": verdicts,
            "covered": verdicts.count("covered"), "missing": verdicts.count("missing"),
            "contradicted": verdicts.count("contradicted"), "n": len(must)}


async def _classify_failure(llm, row: dict, judged: dict) -> dict:
    missed = [s for s, v in zip(judged["must_have"], judged["verdicts"]) if v != "covered"]
    legs = (row.get("graph_legs") or {}).get("legs") or []
    titles = sorted({c.get("title", "")[:70] for c in row.get("claims", [])})[:15]
    trace = (f"EVIDENCE TITLES RETRIEVED+CITED:\n" + "\n".join(f"- {t}" for t in titles)
             + f"\n\nGRAPH LEGS: {[(x.get('query'), x.get('merged')) for x in legs]}"
             + f"\nATOMS: {row.get('atoms')} | STOPPED: {row.get('stopped')}")
    comp = await llm.complete(
        system=_CLASSIFY_SYSTEM,
        messages=[{"role": "user", "content":
                   f"QUESTION: {row['question']}\n\nANSWER:\n{row['answer'][:6000]}\n\n"
                   f"MISSED GOLD FACTS:\n" + "\n".join(f"- {m}" for m in missed)
                   + f"\n\nTRACE:\n{trace}"}],
        response_format=_Bucket, max_tokens=200)
    return {"bucket": comp.parsed.bucket, "why": comp.parsed.why[:200]}


async def main(run_file: str, double_n: int) -> None:
    import api.app as appmod
    svc = appmod.build_default_service()
    rows = [json.loads(ln) for ln in
            (pathlib.Path(run_file) if run_file.startswith("/") else HERE / run_file)
            .read_text().splitlines() if ln.strip()]
    rows = [r for r in rows if "error" not in r]
    judge_model = os.environ.get("NOESIS_LLM_MODEL", "(default anthropic)")
    prompt_hash = hashlib.sha256((_JUDGE_SYSTEM + _CLASSIFY_SYSTEM).encode()).hexdigest()[:12]
    sem = asyncio.Semaphore(4)
    out: list[dict] = []

    async def one(r):
        async with sem:
            j = await _judge_one(svc.llm, r)
            if j is None:
                return
            rec = {"id": r["id"], "question": r["question"][:120], **j,
                   "recall": round(j["covered"] / j["n"], 3),
                   "judge": {"model": judge_model, "prompt_sha": prompt_hash}}
            if j["covered"] < j["n"]:
                rec["failure"] = await _classify_failure(svc.llm, r, j)
            out.append(rec)

    await asyncio.gather(*(one(r) for r in rows))
    out.sort(key=lambda x: x["recall"])

    # ---- calibration (B5): double-grade the N lowest-recall answers with an INDEPENDENT
    # judge family (OpenAI JSON client) and report verdict agreement ----
    agree = None
    if double_n and os.environ.get("OPENAI_API_KEY"):
        from noesis_kernel.providers.openai_llm import OpenAIJsonLLM
        oa = OpenAIJsonLLM()
        mdl = (os.environ.get("NOESIS_FALLBACK_MODEL") or "").strip() or "gpt-4o"
        pairs = same = 0
        by_id = {r["id"]: r for r in rows}
        for rec in out[:double_n]:
            row = by_id[rec["id"]]
            numbered = "\n".join(f"[{i}] {s}" for i, s in enumerate(rec["must_have"]))
            try:
                raw = await oa.complete_json(
                    model=mdl,
                    system=_JUDGE_SYSTEM + '\nReturn JSON: {"grades":[{"index":0,'
                                           '"verdict":"covered|missing|contradicted"}]}',
                    user=f"ANSWER:\n{row['answer'][:8000]}\n\nGOLD MUST-HAVE FACTS:\n{numbered}")
            except Exception:   # noqa: BLE001 — calibration is best-effort
                continue
            by_i = {g.get("index"): g.get("verdict") for g in
                    (raw.get("grades") if isinstance(raw, dict) else None) or []
                    if isinstance(g, dict)}
            for i, a in enumerate(rec["verdicts"]):
                b = by_i.get(i)
                if b in ("covered", "missing", "contradicted"):
                    pairs += 1
                    same += a == b
        agree = round(same / pairs, 3) if pairs else None

    n = len(out)
    stamp = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    dest = HERE / "runs" / f"judged-{pathlib.Path(run_file).stem}-{stamp}.json"
    sha = subprocess.run(["git", "rev-parse", "--short", "HEAD"], capture_output=True,
                         text=True, cwd=ROOT).stdout.strip()
    summary = {
        "git": sha, "answers_judged": n,
        "must_have_recall_mean": round(sum(r["recall"] for r in out) / n, 3) if n else None,
        "answers_fully_covered": sum(1 for r in out if r["recall"] == 1.0),
        "contradiction_answers": sum(1 for r in out if r["contradicted"]),
        "failure_buckets": {b: sum(1 for r in out if r.get("failure", {}).get("bucket") == b)
                            for b in _TAXONOMY},
        "judge_agreement_double_grade": agree,
    }
    dest.write_text(json.dumps({"summary": summary, "judgments": out}, indent=2))
    print(json.dumps(summary, indent=2))
    print("worst 5:")
    for r in out[:5]:
        print(f"  [{r['id']}] recall={r['recall']} contradicted={r['contradicted']} "
              f"bucket={r.get('failure', {}).get('bucket')} | {r['question'][:70]}")
    print("saved:", dest.name)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("run_file")
    ap.add_argument("--double-grade", type=int, default=0)
    ap.add_argument("--confirm-spend", action="store_true")
    a = ap.parse_args()
    print("PROJECTED SPEND: ~1-2 small judge calls per answer (+double-grades)")
    if not a.confirm_spend:
        raise SystemExit("refusing without --confirm-spend")
    # prod env parity for keys
    api = json.loads(subprocess.run(["railway", "variables", "--service", "noesis-api",
                                     "--json"], capture_output=True, text=True,
                                    cwd=ROOT).stdout)
    for k, v in api.items():
        if not k.startswith("RAILWAY_") and k != "PORT":
            os.environ.setdefault(k, v)
    asyncio.run(main(a.run_file, a.double_grade))
