"""T0 STRUCTURAL scorecard over a run file — free (no LLM). T2 rubric judging is a separate,
budget-gated step (amendment B5: judge calibration first).

Usage: .venv/bin/python evals/realworld/score.py runs/run-<...>.jsonl [runs/other.jsonl]
Two run files → side-by-side diff (e.g. expand on vs off on the same slice).
"""
from __future__ import annotations

import json
import pathlib
import sys


def load(p: str) -> list[dict]:
    path = pathlib.Path(p) if p.startswith("/") else pathlib.Path(__file__).parent / p
    return [json.loads(ln) for ln in path.read_text().splitlines() if ln.strip()]


def card(rows: list[dict]) -> dict:
    ok = [r for r in rows if "error" not in r]
    if not ok:
        return {"answers": 0, "errors": len(rows)}
    legs_fired = [r for r in ok if any((leg.get("merged") or 0) > 0
                                       for leg in ((r.get("graph_legs") or {}).get("legs") or []))]
    kinds: dict[str, int] = {}
    for r in ok:
        for c in r["claims"]:
            k = c.get("evidence_kind") or "unclassified"
            kinds[k] = kinds.get(k, 0) + 1
    return {
        "answers": len(ok), "errors": len(rows) - len(ok),
        "grounded_rate": round(sum(r["grounded"] for r in ok) / len(ok), 3),
        "abstention_rate": round(sum(1 for r in ok if not r["claims"]) / len(ok), 3),
        "avg_claims": round(sum(len(r["claims"]) for r in ok) / len(ok), 1),
        "avg_atoms": round(sum(r["atoms"] for r in ok) / len(ok), 1),
        "avg_seconds": round(sum(r.get("seconds", 0) for r in ok) / len(ok), 1),
        "stopped": {s: sum(1 for r in ok if r["stopped"] == s)
                    for s in {r["stopped"] for r in ok}},
        "coverage_gap_rate": round(sum(1 for r in ok if r["coverage_gaps"]) / len(ok), 3),
        "graph_leg_fire_rate": round(len(legs_fired) / len(ok), 3),
        "evidence_kinds": dict(sorted(kinds.items(), key=lambda x: -x[1])[:8]),
    }


def main() -> None:
    if len(sys.argv) < 2:
        raise SystemExit(__doc__)
    cards = {p: card(load(p)) for p in sys.argv[1:]}
    if len(cards) == 1:
        print(json.dumps(next(iter(cards.values())), indent=2))
        return
    keys = ["answers", "errors", "grounded_rate", "abstention_rate", "avg_claims",
            "avg_atoms", "avg_seconds", "coverage_gap_rate", "graph_leg_fire_rate"]
    names = list(cards)
    print(f"{'metric':22} " + " ".join(f"{pathlib.Path(n).name[:34]:>36}" for n in names))
    for k in keys:
        print(f"{k:22} " + " ".join(f"{str(cards[n].get(k)):>36}" for n in names))


if __name__ == "__main__":
    main()
