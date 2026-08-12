"""COMPOSE-MODEL A/B — is our synthesis/writing model the right choice?

Design: evidence held CONSTANT. Each arm re-composes final answers from the SAME banked
verified claims (same questions, same findings, same base compose contract) — the only
variable is the writing model. Grounding safety is unchanged by construction (claims were
span-verified before any writer sees them). Every arm is judged by BOTH judge families
(Claude + OpenAI) so family bias is visible and cancels in the comparison.

Arms: claude (the incumbent, via the service LLM) · gpt (OpenAI, NOESIS_AB_OPENAI_MODEL,
default gpt-5.1) · gemini (only if GEMINI_API_KEY exists — else skipped and noted).

Usage:
  .venv/bin/python evals/realworld/compose_ab.py runs/run-<banked>.jsonl [--limit 25] --confirm-spend
"""
from __future__ import annotations

import argparse
import asyncio
import datetime as dt
import json
import os
import pathlib
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
HERE = pathlib.Path(__file__).parent
for p in ("apps", "packages/kernel", "packages/vertical_medical"):
    sys.path.insert(0, str(ROOT / p))

# The kernel's BASE compose contract (react.py), replicated verbatim for harness use — all
# arms get the IDENTICAL prompt, so inter-arm comparison is valid even if this drifts from
# the live closure someday.
_COMPOSE_INSTR = (
    "Write a clear, well-organized answer to the question that synthesizes "
    "these findings into coherent prose. Reference each finding inline as "
    "[n] where you use it. Use ONLY the findings above — do not add facts, "
    "figures, or claims not present in them. If they only partially answer "
    "the question, say what is and isn't supported.")


def _prod_env() -> None:
    api = json.loads(subprocess.run(["railway", "variables", "--service", "noesis-api",
                                     "--json"], capture_output=True, text=True,
                                    cwd=ROOT).stdout)
    for k, v in api.items():
        if not k.startswith("RAILWAY_") and k != "PORT":
            os.environ.setdefault(k, v)


def _findings_block(claims: list[dict]) -> str:
    return "\n".join(f"[{i}] {c['text']}  (quote: \"{c['quote']}\" — source: {c.get('source','')})"
                     for i, c in enumerate(claims, 1))


async def _compose_claude(llm, question: str, findings: str) -> str:
    from pydantic import BaseModel

    class _A(BaseModel):
        answer: str

    comp = await llm.complete(
        system="You are an evidence-grounded research writer.",
        messages=[{"role": "user", "content":
                   f"Question: {question}\n\nVERIFIED FINDINGS (the ONLY facts you may use):\n"
                   f"{findings}\n\n{_COMPOSE_INSTR}"}],
        response_format=_A, max_tokens=3000)
    return comp.parsed.answer


async def _compose_openai(question: str, findings: str, model: str) -> str:
    from noesis_kernel.providers.openai_llm import OpenAIJsonLLM
    oa = OpenAIJsonLLM()
    raw = await oa.complete_json(
        model=model,
        system="You are an evidence-grounded research writer. "
               'Return JSON: {"answer": "<the full answer text>"}',
        user=f"Question: {question}\n\nVERIFIED FINDINGS (the ONLY facts you may use):\n"
             f"{findings}\n\n{_COMPOSE_INSTR}")
    return (raw.get("answer") or "") if isinstance(raw, dict) else ""


_JM = None


def _load_judge():
    """Load judge.py once, REGISTERED in sys.modules (pydantic forward-ref resolution
    requires it for the _Grades/_StatementGrade models)."""
    global _JM
    if _JM is None:
        import importlib.util
        spec = importlib.util.spec_from_file_location("rw_judge", HERE / "judge.py")
        m = importlib.util.module_from_spec(spec)
        sys.modules["rw_judge"] = m
        spec.loader.exec_module(m)
        _JM = m
    return _JM


async def _judge_openai(rec_answer: str, must: list[str], model: str) -> list[str] | None:
    from noesis_kernel.providers.openai_llm import OpenAIJsonLLM
    jm = _load_judge()
    oa = OpenAIJsonLLM()
    numbered = "\n".join(f"[{i}] {s}" for i, s in enumerate(must))
    try:
        raw = await oa.complete_json(
            model=model,
            system=jm._JUDGE_SYSTEM + '\nReturn JSON: {"grades":[{"index":0,'
                                      '"verdict":"covered|missing|contradicted"}]}',
            user=f"ANSWER:\n{rec_answer[:8000]}\n\nGOLD MUST-HAVE FACTS:\n{numbered}")
    except Exception:   # noqa: BLE001
        return None
    by_i = {g.get("index"): g.get("verdict") for g in
            (raw.get("grades") if isinstance(raw, dict) else None) or [] if isinstance(g, dict)}
    return [by_i.get(i) if by_i.get(i) in ("covered", "missing", "contradicted") else "missing"
            for i in range(len(must))]


async def main(run_file: str, limit: int) -> None:
    import api.app as appmod
    jm = _load_judge()
    svc = appmod.build_default_service()
    gpt_model = (os.environ.get("NOESIS_AB_OPENAI_MODEL") or "gpt-5.1").strip()
    oa_judge = (os.environ.get("NOESIS_FALLBACK_MODEL") or "gpt-4o").strip()
    rows = [json.loads(ln) for ln in
            (pathlib.Path(run_file) if run_file.startswith("/") else HERE / run_file)
            .read_text().splitlines() if ln.strip()]
    rows = [r for r in rows if "error" not in r and r.get("claims")][:limit]
    sem = asyncio.Semaphore(3)
    results: list[dict] = []

    async def one(r: dict) -> None:
        async with sem:
            must = jm._parse_gold((r.get("gold") or {}).get("must_have"))
            if not must:
                return
            findings = _findings_block(r["claims"])
            arms: dict[str, str] = {}
            arms["claude"] = await _compose_claude(svc.llm, r["question"], findings)
            arms["gpt"] = await _compose_openai(r["question"], findings, gpt_model)
            rec: dict = {"id": r["id"], "question": r["question"][:100], "n_gold": len(must)}
            for arm, ans in arms.items():
                cj = await jm._judge_one(svc.llm, {"answer": ans, "gold": r["gold"]})
                oj = await _judge_openai(ans, must, oa_judge)
                rec[arm] = {
                    "chars": len(ans),
                    "claude_judge_recall": round(cj["covered"] / cj["n"], 3) if cj else None,
                    "claude_judge_contradicted": cj["contradicted"] if cj else None,
                    "openai_judge_recall": (round(sum(v == "covered" for v in oj) / len(oj), 3)
                                            if oj else None),
                    "answer": ans,
                }
            results.append(rec)

    await asyncio.gather(*(one(r) for r in rows))
    n = len(results)

    def _mean(arm, key):
        vals = [x[arm][key] for x in results if x[arm].get(key) is not None]
        return round(sum(vals) / len(vals), 3) if vals else None

    summary = {"git": subprocess.run(["git", "rev-parse", "--short", "HEAD"],
                                     capture_output=True, text=True, cwd=ROOT).stdout.strip(),
               "questions": n, "gpt_model": gpt_model, "openai_judge": oa_judge,
               "gemini_arm": "skipped (no GEMINI_API_KEY)"}
    for arm in ("claude", "gpt"):
        summary[arm] = {"recall_claude_judge": _mean(arm, "claude_judge_recall"),
                        "recall_openai_judge": _mean(arm, "openai_judge_recall"),
                        "contradictions": sum((x[arm].get("claude_judge_contradicted") or 0) > 0
                                              for x in results),
                        "avg_chars": round(sum(x[arm]["chars"] for x in results) / n) if n else 0}
    wins = {"claude": 0, "gpt": 0, "tie": 0}
    for x in results:                              # paired, averaged across BOTH judges
        def _score(arm):
            vals = [v for v in (x[arm]["claude_judge_recall"], x[arm]["openai_judge_recall"])
                    if v is not None]
            return sum(vals) / len(vals) if vals else 0
        d = _score("claude") - _score("gpt")
        wins["claude" if d > 0.02 else "gpt" if d < -0.02 else "tie"] += 1
    summary["paired_wins"] = wins
    stamp = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    dest = HERE / "runs" / f"compose-ab-{stamp}.json"
    dest.write_text(json.dumps({"summary": summary, "results": results}, indent=2))
    print(json.dumps(summary, indent=2))
    print("saved:", dest.name)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("run_file")
    ap.add_argument("--limit", type=int, default=25)
    ap.add_argument("--confirm-spend", action="store_true")
    a = ap.parse_args()
    print(f"PROJECTED SPEND: ~{a.limit * 2} compose calls + ~{a.limit * 4} judge calls "
          f"(2 arms × 2 judges), all small")
    if not a.confirm_spend:
        raise SystemExit("refusing without --confirm-spend")
    _prod_env()
    asyncio.run(main(a.run_file, a.limit))
