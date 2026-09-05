"""Structural FORMAT check for a run of the format slice — free (no LLM).

For each answer: which `## ` headings appear, which are forbidden for the expected question shape,
which required ones are present, and (for `update`) whether every bullet carries a year. Reports
PASS/FAIL per question and flags the two failure directions separately:
  - over-correction: the decision-control question (#4) lost its plan;
  - old bias: a general question still got Do now / Do if / Watch for.

  .venv/bin/python evals/realworld/format_check.py runs/run-slice-format-8-...jsonl
"""
from __future__ import annotations

import json
import pathlib
import re
import sys

HEAD = re.compile(r"^##\s+(.+?)\s*$", re.M)
YEAR = re.compile(r"\b(19|20)\d{2}\b")


def check(row: dict) -> tuple[bool, list[str]]:
    gold, ans = row.get("gold") or {}, row.get("answer") or ""
    heads = [h.strip() for h in HEAD.findall(ans)]
    low = [h.lower() for h in heads]
    problems: list[str] = []
    for h in gold.get("forbid_headings", []):
        if any(x.startswith(h.lower()) for x in low):
            problems.append(f"forbidden heading present: {h}")
    for h in gold.get("require_headings", []):
        if not any(x.startswith(h.lower()) for x in low):
            problems.append(f"required heading missing: {h}")
    if gold.get("require_any") and not any(any(x.startswith(h.lower()) for x in low) for h in gold["require_any"]):
        problems.append(f"none of {gold['require_any']} present")
    for t in gold.get("require_text", []):
        if t.lower() not in ans.lower():
            problems.append(f"required text missing: {t}")
    if gold.get("require_dated_items"):
        bullets = [ln for ln in ans.splitlines() if ln.strip().startswith(("-", "*", "1", "2", "3"))]
        undated = [ln for ln in bullets if not YEAR.search(ln)]
        if bullets and undated:
            problems.append(f"{len(undated)}/{len(bullets)} items undated")
    return (not problems), problems


def main(path: str) -> None:
    rows = [json.loads(ln) for ln in pathlib.Path(path).read_text().splitlines() if ln.strip()]
    ok = 0
    for r in rows:
        if "error" in r:
            print(f"ERR  {r['id']}: {r['error'][:100]}"); continue
        passed, problems = check(r)
        ok += passed
        tag = "PASS" if passed else "FAIL"
        direction = "" if passed else (" [over-correction]" if r.get("stratum") == "decision-control" else " [old bias]")
        print(f"{tag} {r['id']}{direction}" + ("" if passed else " — " + "; ".join(problems)))
    print(f"{ok}/{len(rows)} passed")


if __name__ == "__main__":
    main(sys.argv[1])
