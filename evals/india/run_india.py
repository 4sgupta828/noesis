"""Noesis IN launch-gate eval (spec D-8): the India frozen slice, PAIRED IN-off vs IN-on.

Kernel-direct (no prod flag flip needed): the ON arm emulates the resolved IN profile
exactly as _do_research applies it — country_boost {"IN"}, the structural brand planner
context, and the conflict-protocol compose addendum. Judged with the standard rw judge;
scored as paired per-question deltas + a sign test (means are noise at n=24).

Usage: .venv/bin/python evals/india/run_india.py [--limit 24] --confirm-spend
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
    os.environ["NOESIS_DIAG_TRACE"] = "1"


def _load_judge():
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "rw_judge", ROOT / "evals" / "realworld" / "judge.py")
    m = importlib.util.module_from_spec(spec)
    sys.modules["rw_judge"] = m
    spec.loader.exec_module(m)
    return m


async def _arm(svc, cases, in_on: bool):
    from noesis_vertical_medical.india_brands import INDIA_CONFLICT_DIRECTIVE, brand_context
    sem = asyncio.Semaphore(3)

    async def one(c):
        async with sem:
            kw = {}
            if in_on:
                kw = {"country_boost": {"IN"},
                      "question_context": brand_context(c["question"]) or None,
                      "extra_directive": INDIA_CONFLICT_DIRECTIVE}
            try:
                r = await svc.ask(question=c["question"], tenant_id="demo", **kw)
            except Exception as e:               # noqa: BLE001
                return {"id": c["id"], "error": str(e)[:200]}
            gl = (getattr(r, "diagnostics", None) or {}).get("graph_legs")
            return {"id": c["id"], "question": c["question"], "gold": c["gold"],
                    "answer": r.composed_answer, "grounded": r.grounded,
                    "claims": [{"text": vc.text, "quote": vc.quote,
                                "title": vc.document_title, "source": vc.source_key,
                                "country": (vc.facets or {}).get("source_country", "")}
                               for vc in r.verified_claims],
                    "atoms": r.atoms_gathered,
                    "in_cited": sum(1 for vc in r.verified_claims
                                    if (vc.facets or {}).get("source_country") == "IN")}
    return await asyncio.gather(*(one(c) for c in cases))


async def main(limit: int) -> None:
    import api.app as appmod
    jm = _load_judge()
    svc = appmod.build_default_service()
    cases = [json.loads(ln) for ln in
             (HERE / "slice-india-dev-24-v1.jsonl").read_text().splitlines() if ln.strip()][:limit]

    def _ckpt(name):
        return HERE / f"india-arm-{name}.json"

    async def _arm_banked(name, in_on):
        # PER-ARM CHECKPOINT (credit discipline): a killed run never loses a completed arm;
        # healthy banked rows are reused, only errored/missing ids re-answer.
        banked = {}
        if _ckpt(name).exists():
            banked = {r["id"]: r for r in json.loads(_ckpt(name).read_text())
                      if "error" not in r}
            print(f"{name}: reusing {len(banked)} banked answers")
        todo = [c for c in cases if c["id"] not in banked]
        if todo:
            fresh = await _arm(svc, todo, in_on=in_on)
            banked.update({r["id"]: r for r in fresh})
        rows = [banked[c["id"]] for c in cases if c["id"] in banked]
        _ckpt(name).write_text(json.dumps(rows, indent=1, default=str))
        return rows

    off = await _arm_banked("off", False)
    on = await _arm_banked("on", True)

    async def judge(rows):
        out = {}
        for r in rows:
            if "error" in r:
                continue
            j = await jm._judge_one(svc.llm, r)
            if j:
                out[r["id"]] = {"recall": round(j["covered"] / j["n"], 3),
                                "contradicted": j["contradicted"]}
        return out
    joff, jon = await judge(off), await judge(on)

    wins = losses = ties = 0
    print("\n========= NOESIS IN LAUNCH-GATE EVAL (paired) =========")
    for c in cases:
        a, b = joff.get(c["id"]), jon.get(c["id"])
        if not a or not b:
            print(f"[{c['id']}] SKIP (error)")
            continue
        d = b["recall"] - a["recall"]
        wins += d > 0.02
        losses += d < -0.02
        ties += abs(d) <= 0.02
        onrow = next(r for r in on if r.get("id") == c["id"])
        print(f"[{c['id']}] OFF {a['recall']:.2f} → ON {b['recall']:.2f} ({d:+.2f}) "
              f"| IN-cited {onrow.get('in_cited', 0)} | {c['stratum'][:28]}")
    n_off = [v["recall"] for v in joff.values()]
    n_on = [v["recall"] for v in jon.values()]
    print(f"\nmean recall OFF {sum(n_off)/len(n_off):.3f} → ON {sum(n_on)/len(n_on):.3f} | "
          f"paired: {wins} up / {losses} down / {ties} tie | "
          f"contradictions OFF {sum(v['contradicted'] for v in joff.values())} "
          f"ON {sum(v['contradicted'] for v in jon.values())}")
    stamp = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    sha = subprocess.run(["git", "rev-parse", "--short", "HEAD"], capture_output=True,
                         text=True, cwd=ROOT).stdout.strip()
    (HERE / f"india-gate-{stamp}.json").write_text(json.dumps(
        {"git": sha, "off": off, "on": on, "judged_off": joff, "judged_on": jon},
        indent=1, default=str))
    print("saved: india-gate-" + stamp + ".json")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=24)
    ap.add_argument("--confirm-spend", action="store_true")
    a = ap.parse_args()
    print(f"PROJECTED SPEND: {a.limit * 2} answers ≈ {a.limit * 20}–{a.limit * 40} calls + judging")
    if not a.confirm_spend:
        raise SystemExit("refusing without --confirm-spend")
    _prod_env()
    asyncio.run(main(a.limit))
