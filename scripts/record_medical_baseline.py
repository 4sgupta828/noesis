#!/usr/bin/env python
"""Record the medical clinical-benchmark BASELINE — the single budgeted-credit eval run.

Runs the held-out CLINICAL_GOLD (top-5 US conditions) through the REAL agent and prints the
risk-weighted scorecard. This is the North-Star-proxy number: run it ONCE with evidence-fitness OFF
to establish the baseline, then again with NOESIS_EVIDENCE_FITNESS=1 to measure the delta.

COSTS CREDITS (one LLM run per case). Not a CI test — invoke deliberately:
    NOESIS_PROVIDER_MODE=live NOESIS_ACTIVE_VERTICAL=medical \
    NOESIS_CORPUS_DSN=... ANTHROPIC_API_KEY=... OPENAI_API_KEY=... \
    .venv/bin/python scripts/record_medical_baseline.py

Guardrails: prints per-case pass/fail + the risk-weighted rate + critical failures + evidence_floor
coverage, so a regression or an evidence-fitness improvement is visible at a glance. Human/specialist
review of the gold (Rule 6) should precede trusting the absolute number.
"""
from __future__ import annotations

import asyncio
import json
import os
import sys

# app-package import (mirrors scripts/serve.sh PYTHONPATH)
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "apps"))


async def _main() -> int:
    from noesis_kernel.eval.runner import run_qa_eval, summarize
    from noesis_vertical_medical.eval_clinical_gold import CLINICAL_GOLD
    from api.app import build_default_service

    svc = build_default_service()
    tenant = os.environ.get("NOESIS_EVAL_TENANT", "public")
    scores = await run_qa_eval(svc.ask, CLINICAL_GOLD, tenant_id=tenant)
    summary = summarize(scores)

    print("\n=== per-case ===")
    for cid, s in scores.items():
        risk = s.clinical_risk.upper()
        mark = "PASS" if s.fully_correct else "FAIL"
        extra = "" if s.evidence_floor_ok else " [evidence_floor MISS]"
        print(f"  [{mark}] {risk:4s} {cid}{extra}")
    print("\n=== summary ===")
    print(json.dumps(summary, indent=2))
    fit = os.environ.get("NOESIS_EVIDENCE_FITNESS", "")
    print(f"\nevidence_fitness={'ON' if fit.lower() in ('1','true','yes') else 'OFF'}  "
          f"| risk_weighted_pass_rate={summary['risk_weighted_pass_rate']:.2f}  "
          f"| critical_failures={summary['critical_failures']}")
    # a critical failure (a high-risk case failing) is a hard stop
    return 0 if summary["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(_main()))
