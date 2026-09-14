"""Scorer for the ambient-CDS eval set. Deterministic, no LLM/DB/network — measures each engine
change against clinician-authored gold across diverse encounters.

Dimensions (each a set of boolean checks):
  cond_recall     — conditions that must be detected
  cond_precision  — conditions that must NOT be detected (negation / absence)
  gap_recall      — care-gap ids that must appear
  gap_precision   — care-gap ids that must NOT appear (covered / contraindicated-out)
  caution         — expected contraindication caution at the expected level (hold/confirm)
  safety          — expected drug-safety finding categories
  coding          — expected ICD-10 codes (US)
  coverage        — expected has-coverage-gaps flag (silence-≠-clearance)

Run:  PYTHONPATH=apps python -m api.ambient.eval.run
"""
from __future__ import annotations

from collections import defaultdict
from typing import Dict, List, Tuple

from api.rxcds.engine import PatientContext
from api.ambient.engine import analyze_encounter

from .cases import CASES


def _ctx(p: Dict) -> PatientContext:
    return PatientContext(
        age_years=p.get("age"), sex=p.get("sex"), egfr=p.get("egfr"),
        pregnant=p.get("pregnant"), allergies=[a.lower() for a in p.get("allergies", [])],
        conditions=[c.lower() for c in p.get("conditions", [])], current_meds=p.get("current_meds", []),
    )


def score_case(case: Dict) -> List[Tuple[str, bool, str]]:
    res = analyze_encounter(case["transcript"], _ctx(case.get("patient", {})),
                            mode=case.get("mode", "US"),
                            recent_hospitalization=case.get("recent_hosp", False))
    g = case["gold"]
    got_conds = {c["condition"] for c in res["pre_visit"]["conditions"]}
    got_gaps = {x["id"] for x in res["pre_visit"]["care_gaps"]}
    got_actions = {a["id"] for a in res["pre_visit"]["actions"]}
    got_caut = {x["id"]: x["caution"]["level"] for x in res["pre_visit"]["care_gaps"] if x.get("caution")}
    got_safety = {f["category"] for f in res["encounter"]["safety_findings"]}
    got_codes = {c["code"] for c in res["post_visit"].get("icd10", [])}
    has_cov = res["summary"]["has_coverage_gaps"]

    checks: List[Tuple[str, bool, str]] = []
    for c in g.get("conditions", []):
        checks.append(("cond_recall", c in got_conds, f"detect {c}"))
    for c in g.get("forbid_conditions", []):
        checks.append(("cond_precision", c not in got_conds, f"NOT {c}"))
    for gp in g.get("gaps", []):
        checks.append(("gap_recall", gp in got_gaps, f"gap {gp}"))
    for gp in g.get("forbid_gaps", []):
        checks.append(("gap_precision", gp not in got_gaps, f"no gap {gp}"))
    for a in g.get("actions", []):
        checks.append(("action_recall", a in got_actions, f"action {a}"))
    for gid, lvl in g.get("cautions", {}).items():
        checks.append(("caution", got_caut.get(gid) == lvl, f"{gid}={lvl} (got {got_caut.get(gid)})"))
    for sc in g.get("safety_categories", []):
        checks.append(("safety", sc in got_safety, f"safety {sc}"))
    for cd in g.get("codes", []):
        checks.append(("coding", cd in got_codes, f"code {cd}"))
    if "coverage" in g:
        checks.append(("coverage", has_cov == g["coverage"], f"coverage={g['coverage']} (got {has_cov})"))
    return checks


def evaluate() -> Dict:
    dim_tot: Dict[str, int] = defaultdict(int)
    dim_ok: Dict[str, int] = defaultdict(int)
    case_rows = []
    total = ok = 0
    for case in CASES:
        checks = score_case(case)
        fails = [c for c in checks if not c[1]]
        for dim, passed, _ in checks:
            dim_tot[dim] += 1
            dim_ok[dim] += 1 if passed else 0
            total += 1
            ok += 1 if passed else 0
        case_rows.append({"id": case["id"], "n": len(checks), "fail": len(fails),
                          "fails": [f"{d}:{msg}" for d, _, msg in fails]})
    return {
        "n_cases": len(CASES), "checks": total, "passed": ok,
        "aggregate": round(ok / total, 4) if total else 0.0,
        "by_dimension": {d: {"passed": dim_ok[d], "total": dim_tot[d],
                             "rate": round(dim_ok[d] / dim_tot[d], 3)} for d in sorted(dim_tot)},
        "cases": case_rows,
    }


def main() -> None:
    r = evaluate()
    print(f"\nAMBIENT-CDS EVAL — {r['n_cases']} cases, {r['checks']} checks")
    print(f"AGGREGATE: {r['passed']}/{r['checks']} = {r['aggregate']*100:.1f}%\n")
    print("By dimension:")
    for d, v in r["by_dimension"].items():
        bar = "█" * int(v["rate"] * 20)
        print(f"  {d:16} {v['passed']:>3}/{v['total']:<3} {v['rate']*100:5.1f}% {bar}")
    fails = [c for c in r["cases"] if c["fail"]]
    if fails:
        print("\nFailing cases:")
        for c in fails:
            print(f"  {c['id']}: {c['fail']}/{c['n']} failed")
            for f in c["fails"]:
                print(f"       ✗ {f}")
    else:
        print("\n✓ All checks pass.")


if __name__ == "__main__":
    main()
