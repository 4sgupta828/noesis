"""Masquerade eval — the KG v3 hard-case gate (spec C-7). Kernel-direct, prod env parity.

Each held-out case runs with graph expand OFF then LATE. PASS = the ON answer's cited
evidence carries the expected hidden-topic signals AND the OFF arm shows the baseline
missed them (if OFF also passes, the case is marked NON-DISCRIMINATING, not a win).
Scoring is structural (signal containment over claims + cited titles) — free.

Usage: .venv/bin/python evals/graph/run_masquerade.py [--limit N] --confirm-spend
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


def _signals_hit(res, signals: list[str]) -> list[str]:
    hay = " ".join(c.text + " " + c.quote + " " + c.document_title
                   for c in res.verified_claims).lower()
    hay += " " + (res.composed_answer or "").lower()
    return [s for s in signals if s.lower() in hay]


async def _arm(cases: list[dict], expand: str):
    os.environ["NOESIS_GRAPH_EXPAND"] = expand
    import importlib

    import api.app as appmod
    importlib.reload(appmod)
    svc = appmod.build_default_service()
    sem = asyncio.Semaphore(3)

    async def one(c):
        async with sem:
            try:
                r = await svc.ask(question=c["question"], tenant_id="demo")
            except Exception as e:               # noqa: BLE001
                return {"id": c["id"], "error": str(e)[:200]}
            gl = (getattr(r, "diagnostics", None) or {}).get("graph_legs")
            return {"id": c["id"], "grounded": r.grounded,
                    "claims": len(r.verified_claims),
                    "hits": _signals_hit(r, c["expected_evidence_signals"]),
                    "legs": [(x["query"][:60], x["merged"]) for x in (gl or {}).get("legs", [])]}
    return await asyncio.gather(*(one(c) for c in cases))


async def main(limit: int, off_from: str = ""):
    cases = [json.loads(ln) for ln in (HERE / "masquerade_cases.jsonl").read_text().splitlines()
             if ln.strip()][:limit]
    if off_from:
        # CREDIT-WISE reuse: the OFF arm from a prior run (banked results) — only the ON arm
        # (plus any banked-OFF gaps) spends. Arms then differ in run time; acceptable when the
        # corpus hasn't materially moved between them (say so in the report).
        prior = json.loads((HERE / off_from).read_text())
        banked = {r["id"]: r for r in prior["off"] if "error" not in r}
        missing = [c for c in cases if c["id"] not in banked]
        if missing:
            print(f"re-running {len(missing)} OFF case(s) missing from the bank: "
                  f"{[c['id'] for c in missing]}")
            fresh = {r["id"]: r for r in await _arm(missing, "")}
            banked.update(fresh)
        off = [banked[c["id"]] for c in cases]
    else:
        off = await _arm(cases, "")
    on = await _arm(cases, "late")
    sha = subprocess.run(["git", "rev-parse", "--short", "HEAD"], capture_output=True,
                         text=True, cwd=ROOT).stdout.strip()
    wins = nondisc = fails = 0
    print(f"\n========= MASQUERADE EVAL (git {sha}) =========")
    for c, o, n in zip(cases, off, on):
        if "error" in o or "error" in n:
            print(f"[{c['id']}] ERROR {o.get('error') or n.get('error')}")
            fails += 1
            continue
        on_pass = len(n["hits"]) > 0
        off_pass = len(o["hits"]) > 0
        verdict = ("WIN" if on_pass and not off_pass else
                   "non-discriminating (baseline also finds it)" if on_pass and off_pass else
                   "FAIL")
        wins += verdict == "WIN"
        nondisc += verdict.startswith("non")
        fails += verdict == "FAIL"
        print(f"[{c['id']}] {verdict} | expected: {c['expected_hidden_topic'][:40]}")
        print(f"    OFF: grounded={o['grounded']} claims={o['claims']} signals={o['hits']}")
        print(f"    ON : grounded={n['grounded']} claims={n['claims']} signals={n['hits']} "
              f"legs={n['legs']}")
    print(f"\nSCORE: {wins} wins · {nondisc} non-discriminating · {fails} fails "
          f"of {len(cases)} | no-harm: OFF grounded "
          f"{sum(1 for o in off if o.get('grounded'))}/{len(cases)} vs ON "
          f"{sum(1 for n in on if n.get('grounded'))}/{len(cases)}")
    out = HERE / f"masq-results-{dt.datetime.now(dt.timezone.utc).strftime('%Y%m%dT%H%M%SZ')}.json"
    out.write_text(json.dumps({"git": sha, "cases": len(cases),
                               "off": off, "on": on}, indent=2, default=str))
    print("saved:", out.name)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=10)
    ap.add_argument("--off-from", default="", help="reuse a prior run's OFF arm (results json)")
    ap.add_argument("--confirm-spend", action="store_true")
    a = ap.parse_args()
    arms = 1 if a.off_from else 2
    print(f"PROJECTED SPEND: {a.limit * arms} answers ≈ "
          f"{a.limit * arms * 10}–{a.limit * arms * 20} LLM calls")
    if not a.confirm_spend:
        raise SystemExit("refusing without --confirm-spend")
    _prod_env()
    asyncio.run(main(a.limit, a.off_from))
