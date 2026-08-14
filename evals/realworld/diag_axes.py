"""Exploratory-coverage DIAGNOSTIC (pre-build, ~$1 on top of the answer run).

For each gold must-cover axis of an exploratory question, classify the CURRENT system's
behavior into one of three buckets that each demand a different action:

  covered                 — the answer addresses the axis (no build needed)
  uncovered-retrievable   — the answer misses it AND our corpus holds usable evidence
                            (the exploratory-legs build would help)
  uncovered-absent        — the answer misses it AND the corpus has nothing usable
                            (the fix is ingestion, not machinery)

Usage:
  .venv/bin/python evals/realworld/diag_axes.py runs/<run-file>.jsonl --confirm-spend

Coverage judging: one structured LLM call per question (all axes at once).
Corpus probe (only for uncovered axes): embed "axis + question", top-5 pgvector search
over rs_block, one structured LLM call judging whether the snippets could evidence the
axis. Rule 18: both judgments are the model's; code only orchestrates and counts.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import pathlib
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
HERE = pathlib.Path(__file__).parent
for p in ("apps", "packages/kernel", "packages/vertical_medical"):
    sys.path.insert(0, str(ROOT / p))

from pydantic import BaseModel  # noqa: E402


class _AxisVerdicts(BaseModel):
    covered: list[bool] = []


class _ProbeVerdict(BaseModel):
    usable: bool = False
    note: str = ""


def _prod_env() -> None:
    import os
    api = json.loads(subprocess.run(["railway", "variables", "--service", "noesis-api",
                                     "--json"], capture_output=True, text=True,
                                    cwd=ROOT).stdout)
    pg = json.loads(subprocess.run(["railway", "variables", "--service", "Postgres",
                                    "--json"], capture_output=True, text=True,
                                   cwd=ROOT).stdout)
    for k, v in api.items():
        if not k.startswith("RAILWAY_") and k != "PORT":
            os.environ.setdefault(k, v)
    os.environ["NOESIS_CORPUS_DSN"] = pg["DATABASE_PUBLIC_URL"]


async def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("run_file")
    ap.add_argument("--confirm-spend", action="store_true")
    a = ap.parse_args()
    if not a.confirm_spend:
        raise SystemExit("refusing without --confirm-spend")
    _prod_env()
    from noesis_kernel.runtime.build import build_embedder, build_llm, resolve_mode
    llm = build_llm(mode=resolve_mode())
    embedder = build_embedder(mode=resolve_mode())

    rf = pathlib.Path(a.run_file) if a.run_file.startswith("/") else HERE / a.run_file
    rows = [json.loads(ln) for ln in rf.read_text().splitlines() if ln.strip()]
    print(f"diagnosing {len(rows)} answers")

    import asyncpg
    import os
    conn = await asyncpg.connect(os.environ["NOESIS_CORPUS_DSN"])

    buckets = {"covered": 0, "uncovered_retrievable": 0, "uncovered_absent": 0}
    detail = []
    for r in rows:
        axes = (r.get("gold") or {}).get("axes") or []
        answer = (r.get("answer") or "")[:9000]
        if not axes or not answer:
            continue
        axis_list = "\n".join(f"{i}. {ax}" for i, ax in enumerate(axes))
        comp = await llm.complete(
            system=("You judge whether an answer ADDRESSES each listed aspect. An aspect "
                    "counts as covered only if the answer contains substantive content "
                    "about it (a mention in passing with no information does not count). "
                    "Return covered as a list of booleans, one per numbered aspect, in "
                    "order."),
            messages=[{"role": "user",
                       "content": f"ASPECTS:\n{axis_list}\n\nANSWER:\n{answer}"}],
            response_format=_AxisVerdicts, max_tokens=500)
        verdicts = list(comp.parsed.covered) + [False] * (len(axes) - len(comp.parsed.covered))
        for ax, cov in zip(axes, verdicts):
            if cov:
                buckets["covered"] += 1
                detail.append({"id": r["id"], "axis": ax, "bucket": "covered"})
                continue
            # corpus probe: could our own corpus have evidenced this axis?
            vec = embedder.embed([f"{ax} — {r['question']}"])[0]
            hits = await conn.fetch(
                "SELECT document_title, left(text, 400) AS snippet "
                "FROM rs_block WHERE tenant_id='demo' AND embedding IS NOT NULL "
                "ORDER BY embedding <=> $1::vector LIMIT 5",
                "[" + ",".join(f"{x:.6f}" for x in vec) + "]")
            snips = "\n---\n".join(f"⟨{h['document_title'][:70]}⟩ {h['snippet']}"
                                   for h in hits)
            probe = await llm.complete(
                system=("You judge whether the retrieved snippets contain USABLE evidence "
                        "for the stated aspect of the question — content a grounded answer "
                        "could cite for it. Judge usability, not mere topical similarity."),
                messages=[{"role": "user", "content":
                           f"ASPECT: {ax}\nQUESTION: {r['question']}\n\nSNIPPETS:\n{snips}"}],
                response_format=_ProbeVerdict, max_tokens=500)
            b = "uncovered_retrievable" if probe.parsed.usable else "uncovered_absent"
            buckets[b] += 1
            detail.append({"id": r["id"], "axis": ax, "bucket": b,
                           "note": probe.parsed.note[:120],
                           "top_docs": [h["document_title"][:60] for h in hits[:3]]})
        print(f"  {r['id']}: done")
    await conn.close()

    total = sum(buckets.values())
    print("\n==== EXPLORATORY COVERAGE DIAGNOSTIC ====")
    for k, v in buckets.items():
        print(f"{k:24} {v:3}  ({v / max(total, 1):.0%})")
    print("\nuncovered axes:")
    for d in detail:
        if d["bucket"] != "covered":
            print(f"  [{d['bucket']}] {d['id']}: {d['axis'][:70]}")
    out = HERE / "runs" / f"diag-axes-{rf.stem}.json"
    out.write_text(json.dumps({"buckets": buckets, "detail": detail}, indent=1))
    print(f"\nsaved: {out.name}")


if __name__ == "__main__":
    asyncio.run(main())
