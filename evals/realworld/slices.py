"""Build FROZEN, versioned slices from fetched sets — stratified by DATASET-NATIVE metadata
(amendment B1: HealthBench `theme:*` tags, K-QA `ICD_10_diag`; no keyword condition-matching).

Split discipline (Rule 5): a deterministic hash of the question id assigns dev (70%) / test
(30%) ONCE — same assignment on every machine, no RNG. Slices draw from ONE split and are
frozen files; re-running with the same args reproduces byte-identical slices.

Usage:
  .venv/bin/python evals/realworld/slices.py --set kqa --n 50 --split dev
  .venv/bin/python evals/realworld/slices.py --set healthbench --n 50 --split dev --single-turn
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import pathlib

HERE = pathlib.Path(__file__).parent
DATA = HERE / "data"
SLICES = HERE / "slices"


def _split_of(key: str) -> str:
    return "dev" if int(hashlib.sha256(key.encode()).hexdigest(), 16) % 10 < 7 else "test"


def _norm_records(name: str, single_turn: bool) -> list[dict]:
    out = []
    for i, ln in enumerate((DATA / f"{name}.jsonl").read_text().splitlines()):
        if not ln.strip():
            continue
        r = json.loads(ln)
        if name.startswith("healthbench"):
            msgs = r.get("prompt") or []
            if single_turn and len(msgs) != 1:
                continue
            users = [m["content"] for m in msgs if m.get("role") == "user"]
            if not users:
                continue
            themes = [t.split(":", 1)[1] for t in (r.get("example_tags") or [])
                      if t.startswith("theme:")]
            out.append({"id": r.get("prompt_id") or f"{name}-{i}", "set": name,
                        "question": users[-1], "history": msgs[:-1],
                        "stratum": themes[0] if themes else "untagged",
                        "gold": {"rubrics": r.get("rubrics") or []}})
        elif name.startswith("kqa"):
            q = r.get("Question") or ""
            if not q:
                continue
            out.append({"id": f"kqa-{i}", "set": name, "question": q, "history": [],
                        "stratum": (r.get("ICD_10_diag") or "unknown")[:60],
                        "gold": {"must_have": r.get("Must_have"),
                                 "nice_to_have": r.get("Nice_to_have")}})
    return out


def build(name: str, n: int, split: str, single_turn: bool) -> pathlib.Path:
    recs = [r for r in _norm_records(name, single_turn) if _split_of(r["id"]) == split]
    # stratified round-robin: deterministic order inside each stratum (by id), cycle strata
    by_s: dict[str, list[dict]] = {}
    for r in sorted(recs, key=lambda x: x["id"]):
        by_s.setdefault(r["stratum"], []).append(r)
    chosen: list[dict] = []
    strata = sorted(by_s)
    while len(chosen) < min(n, len(recs)):
        for s in strata:
            if by_s[s] and len(chosen) < n:
                chosen.append(by_s[s].pop(0))
    SLICES.mkdir(parents=True, exist_ok=True)
    stamp = dt.date.today().isoformat()
    dest = SLICES / f"slice-{name}-{split}-{len(chosen)}-{stamp}.jsonl"
    if dest.exists():
        raise SystemExit(f"{dest} exists — slices are frozen; pick a new date/n")
    dest.write_text("\n".join(json.dumps(r) for r in chosen))
    print(f"{dest.name}: {len(chosen)} questions, {len(set(r['stratum'] for r in chosen))} strata "
          f"(pool: {len(recs)} {split} records)")
    return dest


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--set", required=True)
    ap.add_argument("--n", type=int, default=50)
    ap.add_argument("--split", choices=("dev", "test"), default="dev")
    ap.add_argument("--single-turn", action="store_true")
    a = ap.parse_args()
    build(a.set, a.n, a.split, a.single_turn)
