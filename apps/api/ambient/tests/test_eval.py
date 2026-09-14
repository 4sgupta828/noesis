"""Regression gate over the 20-case eval set. Deterministic; no DB/LLM/network.

Fails if aggregate quality drops below the current bar, or if any negation false-positive appears
(condition precision must stay perfect — the safety-critical "don't invent problems" property).
"""
from __future__ import annotations

from api.ambient.eval.run import evaluate

BAR = 0.98  # current aggregate is 1.0; regressions below this fail CI


def test_eval_aggregate_above_bar():
    r = evaluate()
    assert r["aggregate"] >= BAR, (
        f"ambient eval regressed to {r['aggregate']:.3f} (<{BAR}). Failing: "
        + "; ".join(f"{c['id']}({c['fail']})" for c in r["cases"] if c["fail"])
    )


def test_no_negation_false_positives():
    # condition precision must be perfect — never surface a problem the transcript negated/denied
    r = evaluate()
    prec = r["by_dimension"].get("cond_precision")
    assert prec and prec["rate"] == 1.0, f"negation/absence false positive: {prec}"


def test_safety_recall_perfect():
    r = evaluate()
    saf = r["by_dimension"].get("safety")
    assert saf and saf["rate"] == 1.0, f"missed an expected drug-safety finding: {saf}"
