"""Kernel-direct slice runner — NO session rows, NO gap side-effects (amendment B7).

Prod-parity env is pulled from Railway at run time (secrets stay in process env, never on
disk). Each answer records Rule-11 provenance. Cost gate (amendment B2): prints the projected
LLM-call budget and refuses to run without --confirm-spend.

Usage:
  .venv/bin/python evals/realworld/run.py --slice slices/slice-kqa-dev-50-<date>.jsonl \
      [--limit 10] [--expand on|off|env] [--concurrency 3] --confirm-spend
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
RUNS = HERE / "runs"
for p in ("apps", "packages/kernel", "packages/vertical_medical"):
    sys.path.insert(0, str(ROOT / p))

CALLS_PER_ANSWER = (10, 20)      # honest range: ReAct steps + compose + extraction batches


def _prod_env() -> None:
    api = json.loads(subprocess.run(["railway", "variables", "--service", "noesis-api",
                                     "--json"], capture_output=True, text=True,
                                    cwd=ROOT).stdout)
    pg = json.loads(subprocess.run(["railway", "variables", "--service", "Postgres",
                                    "--json"], capture_output=True, text=True,
                                   cwd=ROOT).stdout)
    for k, v in api.items():
        if not k.startswith("RAILWAY_") and k != "PORT":
            os.environ[k] = v
    os.environ["NOESIS_CORPUS_DSN"] = pg["DATABASE_PUBLIC_URL"]
    os.environ["NOESIS_DIAG_TRACE"] = "1"          # graph-leg + trace telemetry in results


async def _run(slice_path: pathlib.Path, limit: int, expand: str, conc: int) -> pathlib.Path:
    if expand != "env":
        os.environ["NOESIS_GRAPH_EXPAND"] = "1" if expand == "on" else ""
    import api.app as appmod
    svc = appmod.build_default_service()
    sha = subprocess.run(["git", "rev-parse", "--short", "HEAD"], capture_output=True,
                         text=True, cwd=ROOT).stdout.strip()
    recs = [json.loads(ln) for ln in slice_path.read_text().splitlines() if ln.strip()][:limit]
    sem = asyncio.Semaphore(conc)

    async def one(r: dict) -> dict:
        async with sem:
            t0 = dt.datetime.now(dt.timezone.utc)
            try:
                res = await svc.ask(question=r["question"], tenant_id="demo")
            except Exception as e:               # noqa: BLE001
                return {"id": r["id"], "error": f"{type(e).__name__}: {e}"[:300]}
            gl = (getattr(res, "diagnostics", None) or {}).get("graph_legs")
            return {
                "id": r["id"], "set": r["set"], "stratum": r["stratum"],
                "question": r["question"], "gold": r.get("gold"),
                "answer": res.composed_answer, "grounded": res.grounded,
                "claims": [{"text": c.text, "quote": c.quote, "title": c.document_title,
                            "document_id": c.document_id, "source": c.source_key,
                            "evidence_kind": getattr(c, "evidence_kind", "")}
                           for c in res.verified_claims],
                "atoms": res.atoms_gathered, "stopped": res.stopped_reason,
                "coverage_gaps": res.coverage_gaps, "graph_legs": gl,
                "seconds": (dt.datetime.now(dt.timezone.utc) - t0).total_seconds(),
                "provenance": {"git_sha": sha, "expand": os.environ.get("NOESIS_GRAPH_EXPAND", ""),
                               "model": os.environ.get("NOESIS_LLM_MODEL", "(default)"),
                               "ran_at": t0.isoformat()},
            }

    results = await asyncio.gather(*(one(r) for r in recs))
    RUNS.mkdir(parents=True, exist_ok=True)
    stamp = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    dest = RUNS / f"run-{slice_path.stem}-{expand}-{stamp}.jsonl"
    dest.write_text("\n".join(json.dumps(x) for x in results))
    errs = sum(1 for x in results if "error" in x)
    print(f"{dest.name}: {len(results)} answers ({errs} errors)")
    return dest


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--slice", required=True)
    ap.add_argument("--limit", type=int, default=1000)
    ap.add_argument("--expand", choices=("on", "off", "env"), default="env")
    ap.add_argument("--concurrency", type=int, default=3)
    ap.add_argument("--confirm-spend", action="store_true")
    a = ap.parse_args()
    sp = pathlib.Path(a.slice) if a.slice.startswith("/") else HERE / a.slice
    n = min(a.limit, sum(1 for ln in sp.read_text().splitlines() if ln.strip()))
    lo, hi = CALLS_PER_ANSWER
    print(f"PROJECTED SPEND: {n} answers ≈ {n * lo}–{n * hi} LLM calls (answering dominates; "
          f"grading is separate).")
    if not a.confirm_spend:
        raise SystemExit("refusing to run without --confirm-spend (amendment B2)")
    _prod_env()
    asyncio.run(_run(sp, a.limit, a.expand, a.concurrency))


if __name__ == "__main__":
    main()
