"""Stage-4 paired A/B harness — NOESIS_ANSWER_MODE_ROUTING (enumerative compose) ON vs OFF.

Both arms run the SAME question set through run.py in a subprocess with per-arm env, so
run.py's `_prod_env` override-preserving behavior applies per arm (Railway values, except
the NOESIS_* knobs the arm's environment explicitly sets):

  A (baseline): NOESIS_EVIDENCE_IDENTITY=1 NOESIS_CLAIM_CONGRUENCE=1
                NOESIS_QUESTION_CONTRACT=steer NOESIS_ANSWER_MODE_ROUTING=""
  B (routing):  same + NOESIS_ANSWER_MODE_ROUTING=1

Per row, STRUCTURAL metrics are code-only (no LLM): routing decision vs the slice gold
(`question_contract.answer_mode.routed`), gold-entity coverage in the answer, subject-faithful
citations (a claim naming a gold entity should cite a title concerning that entity — a
conservative structural proxy: violations are flags, not certain errors), declared gaps.

The comparative signal is a PAIRWISE LLM judge (the sensitivity fix over absolute scoring):
each question's two answers are presented in seeded-random order, then again FLIPPED
(2 judge calls/question, mapping recorded). A "win" counts only when BOTH orderings agree
(order-consistent); anything else is a tie. Overall significance: exact two-sided binomial
sign test on order-consistent wins, ties ignored (implemented directly — no scipy).

Usage:
  .venv/bin/python evals/realworld/ab_stage4.py \
      --slice slices/slice-stage4-ab-30-2026-08-14.jsonl [--limit N] \
      [--patch-a FILE --patch-b FILE] [--judge-only RUNA RUNB] --confirm-spend
"""
from __future__ import annotations

import argparse
import asyncio
import datetime as dt
import hashlib
import json
import math
import os
import pathlib
import random
import re
import subprocess
import sys
from typing import Literal

ROOT = pathlib.Path(__file__).resolve().parents[2]
HERE = pathlib.Path(__file__).parent
RUNS = HERE / "runs"
for p in ("apps", "packages/kernel", "packages/vertical_medical"):
    sys.path.insert(0, str(ROOT / p))

from pydantic import BaseModel, Field  # noqa: E402

CALLS_PER_ANSWER = (10, 20)            # mirrors run.py's honest range

ARM_A_ENV = {"NOESIS_EVIDENCE_IDENTITY": "1", "NOESIS_CLAIM_CONGRUENCE": "1",
             "NOESIS_QUESTION_CONTRACT": "steer", "NOESIS_ANSWER_MODE_ROUTING": ""}
ARM_B_ENV = {**ARM_A_ENV, "NOESIS_ANSWER_MODE_ROUTING": "1"}

_DIMS = ("format_fit", "coverage", "coherence", "honesty")
_STRATA = ("low", "medium", "high")


# --------------------------------------------------------------------------- arm running
def run_arm(slice_path: pathlib.Path, limit: int, patch: str, arm_env: dict[str, str],
            label: str) -> pathlib.Path:
    """One arm = one run.py subprocess (its _prod_env preserves our NOESIS_* env as the
    explicit overrides). Returns the run file it produced (parsed from run.py's stdout)."""
    env = {**os.environ, **arm_env}
    cmd = [sys.executable, str(HERE / "run.py"), "--slice", str(slice_path),
           "--limit", str(limit), "--confirm-spend"]
    if patch:
        cmd += ["--patch", patch]
    print(f"[arm {label}] flags: " + " ".join(f"{k}={v!r}" for k, v in arm_env.items()))
    proc = subprocess.run(cmd, env=env, capture_output=True, text=True, cwd=str(HERE))
    sys.stdout.write(proc.stdout)
    sys.stderr.write(proc.stderr)
    if proc.returncode != 0:
        raise SystemExit(f"arm {label} run failed (exit {proc.returncode})")
    names = re.findall(r"(run-\S+\.jsonl)", proc.stdout)
    if not names:
        raise SystemExit(f"arm {label}: could not find run file name in run.py output")
    return RUNS / names[-1]


def load_run_rows(path: pathlib.Path) -> dict[str, dict]:
    """Healthy rows only (no error, non-empty answer), keyed by question id."""
    rows: dict[str, dict] = {}
    for ln in path.read_text().splitlines():
        if not ln.strip():
            continue
        r = json.loads(ln)
        if "error" not in r and (r.get("answer") or "").strip():
            rows[r["id"]] = r
    return rows


# --------------------------------------------------------------------- structural metrics
def _norm(s: str) -> str:
    """Case-fold and treat hyphens/dashes as spaces so 'beta blocker' matches
    'beta-blockers' — still pure containment, no semantics."""
    return re.sub(r"\s+", " ", (s or "").lower().replace("-", " ").replace("–", " ")).strip()


def _contains(needle: str, hay: str) -> bool:
    return bool(needle) and _norm(needle) in _norm(hay)


def routed(row: dict) -> bool:
    am = ((row.get("question_contract") or {}).get("answer_mode")) or {}
    return bool(am.get("routed"))


def covered_entities(row: dict) -> int:
    """Contract entities holding ≥1 slot-matched claim: answer_mode.covered_entities when the
    routing flag stamped it (arm B); else derived from the slot_grid (arm A / shadow)."""
    qc = row.get("question_contract") or {}
    am = qc.get("answer_mode") or {}
    if "covered_entities" in am:
        return int(am["covered_entities"])
    grid = qc.get("slot_grid") or {}
    return sum(1 for v in grid.values() if v > 0)


def routing_class(row: dict) -> str:
    """Row-level routing verdict vs gold: 'true_route' | 'false_route' (routed on an
    exploratory-gold question — a low-stratum error) | 'missed_route' (not routed on an
    enumerative-gold question although ≥2 entities were covered) | 'ok'."""
    mode = ((row.get("gold") or {}).get("expected_mode") or "").strip().lower()
    if routed(row):
        return "false_route" if mode == "exploratory" else \
               "true_route" if mode == "enumerative" else "ok"
    if mode == "enumerative" and covered_entities(row) >= 2:
        return "missed_route"
    return "ok"


def entity_coverage(row: dict) -> float | None:
    """Fraction of gold expected_entities appearing (normalized containment) in the answer.
    None when the row has no gold entities (low stratum)."""
    ents = (row.get("gold") or {}).get("expected_entities") or []
    if not ents:
        return None
    ans = row.get("answer") or ""
    return sum(1 for e in ents if _contains(e, ans)) / len(ents)


def citation_violations(row: dict) -> list[dict]:
    """Claims whose TEXT names a gold entity but whose cited TITLE does not concern it
    (containment). Conservative structural proxy — e.g. a comparison claim naming two
    entities flags the one its single citation doesn't cover; symmetric across arms."""
    ents = (row.get("gold") or {}).get("expected_entities") or []
    out: list[dict] = []
    for c in row.get("claims") or []:
        text, title = c.get("text") or "", c.get("title") or ""
        for e in ents:
            if _contains(e, text) and not _contains(e, title):
                out.append({"entity": e, "title": title[:80], "claim": text[:120]})
    return out


def declared_gaps(row: dict) -> int:
    return len(row.get("coverage_gaps") or [])


def structural_row(row: dict) -> dict:
    return {"routed": routed(row), "covered_entities": covered_entities(row),
            "routing": routing_class(row), "entity_coverage": entity_coverage(row),
            "citation_violations": len(citation_violations(row)),
            "declared_gaps": declared_gaps(row)}


# ------------------------------------------------------------------------ pairwise judge
_PAIR_JUDGE_SYSTEM = """You compare TWO candidate answers (labeled "first" and "second") to \
the SAME question. Judge fitness-for-purpose for a careful professional reader — never style, \
never length for its own sake. Score EACH answer 1-5 on:

- format_fit: does the answer's FORM match what the question demands? A question weighing \
multiple candidate options demands a per-option comparison the reader can act on; a \
single-fact or yes/no question demands a direct answer. Penalize BOTH an undifferentiated \
prose wall where comparison was demanded AND needless comparison scaffolding bolted onto a \
simple lookup.
- coverage: completeness against the question's OWN demands — are the options, constraints, \
and dimensions the question raises actually addressed?
- coherence: internally consistent and well-organized; safety caveats and risks appear \
ADJACENT to the favorable claims they qualify, not buried at the end or omitted.
- honesty: grounded and cited; gaps and uncertainty admitted where evidence is thin. Never \
reward confident overreach — an answer that overclaims beyond its cited evidence scores LOW \
here even if fluent.

Then pick `better`: "first", "second", or "tie" — the answer the reader would genuinely \
prefer to receive. Give a rationale of at most 50 words."""


class PairVerdict(BaseModel):
    better: Literal["first", "second", "tie"] = "tie"
    format_fit_first: int = Field(3, ge=1, le=5)
    format_fit_second: int = Field(3, ge=1, le=5)
    coverage_first: int = Field(3, ge=1, le=5)
    coverage_second: int = Field(3, ge=1, le=5)
    coherence_first: int = Field(3, ge=1, le=5)
    coherence_second: int = Field(3, ge=1, le=5)
    honesty_first: int = Field(3, ge=1, le=5)
    honesty_second: int = Field(3, ge=1, le=5)
    rationale: str = ""


async def judge_pair(llm, question: str, first: str, second: str) -> PairVerdict:
    comp = await llm.complete(
        system=_PAIR_JUDGE_SYSTEM,
        messages=[{"role": "user", "content":
                   f"QUESTION:\n{question[:2000]}\n\nANSWER (first):\n{first[:8000]}\n\n"
                   f"ANSWER (second):\n{second[:8000]}"}],
        response_format=PairVerdict, max_tokens=500)
    return comp.parsed


def consistent_winner(order_call1: tuple[str, str], better1: str, better2: str) -> str:
    """order_call1 = (arm shown first, arm shown second) in call 1; call 2 is FLIPPED.
    Returns 'A' | 'B' | 'tie' — a win only when both orderings name the same arm."""
    def pick(order: tuple[str, str], better: str) -> str | None:
        return None if better == "tie" else order[0] if better == "first" else order[1]
    w1 = pick(order_call1, better1)
    w2 = pick((order_call1[1], order_call1[0]), better2)
    return w1 if (w1 is not None and w1 == w2) else "tie"


def _dims_for(order: tuple[str, str], v: PairVerdict) -> dict[str, dict[str, int]]:
    out: dict[str, dict[str, int]] = {order[0]: {}, order[1]: {}}
    for d in _DIMS:
        out[order[0]][d] = getattr(v, f"{d}_first")
        out[order[1]][d] = getattr(v, f"{d}_second")
    return out


async def judge_pairs(llm, rows_a: dict[str, dict], rows_b: dict[str, dict], seed: int,
                      concurrency: int = 4) -> list[dict]:
    """2 judge calls per paired question (seeded-random order, then flipped). Order mapping,
    both raw verdicts, and per-arm dimension means (across both calls) are recorded."""
    ids = sorted(set(rows_a) & set(rows_b))
    sem = asyncio.Semaphore(concurrency)
    out: list[dict] = []

    async def one(qid: str) -> None:
        async with sem:
            ra, rb = rows_a[qid], rows_b[qid]
            rng = random.Random(f"{seed}:{qid}")
            order = ("A", "B") if rng.random() < 0.5 else ("B", "A")
            texts = {"A": ra.get("answer") or "", "B": rb.get("answer") or ""}
            try:
                v1 = await judge_pair(llm, ra["question"], texts[order[0]], texts[order[1]])
                v2 = await judge_pair(llm, ra["question"], texts[order[1]], texts[order[0]])
            except Exception as e:   # noqa: BLE001 — a dead judgment never kills the run
                out.append({"id": qid, "stratum": ra.get("stratum"),
                            "error": f"{type(e).__name__}: {e}"[:200]})
                return
            d1 = _dims_for(order, v1)
            d2 = _dims_for((order[1], order[0]), v2)
            out.append({
                "id": qid, "stratum": ra.get("stratum"), "order_call1": list(order),
                "better_call1": v1.better, "better_call2": v2.better,
                "winner": consistent_winner(order, v1.better, v2.better),
                "dims": {arm: {d: (d1[arm][d] + d2[arm][d]) / 2 for d in _DIMS}
                         for arm in ("A", "B")},
                "rationales": [v1.rationale[:250], v2.rationale[:250]],
            })

    await asyncio.gather(*(one(q) for q in ids))
    return out


# ----------------------------------------------------------------------------- sign test
def sign_test_p(wins_a: int, wins_b: int) -> float:
    """Exact two-sided binomial sign test (p=0.5), ties already excluded. scipy-free:
    p = 2 * P[X >= max(wins)] for X ~ Bin(n, 0.5), clipped at 1."""
    n = wins_a + wins_b
    if n == 0:
        return 1.0
    k = max(wins_a, wins_b)
    tail = sum(math.comb(n, i) for i in range(k, n + 1)) / (2 ** n)
    return min(1.0, 2.0 * tail)


# ------------------------------------------------------------------------------- summary
def _mean(vals: list) -> float | None:
    vals = [v for v in vals if v is not None]
    return round(sum(vals) / len(vals), 3) if vals else None


def summarize(rows_a: dict[str, dict], rows_b: dict[str, dict],
              judgments: list[dict]) -> dict:
    j_ok = [j for j in judgments if "error" not in j]
    paired = sorted(set(rows_a) & set(rows_b))

    def block(ids: list[str], js: list[dict]) -> dict:
        wins = {"A": 0, "B": 0, "tie": 0}
        for j in js:
            wins[j["winner"]] += 1
        dim_delta = {d: _mean([j["dims"]["B"][d] - j["dims"]["A"][d] for j in js])
                     for d in _DIMS}
        sa = [structural_row(rows_a[i]) for i in ids]
        sb = [structural_row(rows_b[i]) for i in ids]
        tp = sum(1 for s in sb if s["routing"] == "true_route")
        fp = sum(1 for s in sb if s["routing"] == "false_route")
        fn = sum(1 for s in sb if s["routing"] == "missed_route")
        cov_a = _mean([s["entity_coverage"] for s in sa])
        cov_b = _mean([s["entity_coverage"] for s in sb])
        return {
            "n": len(ids), "judged": len(js),
            "wins_b": wins["B"], "wins_a": wins["A"], "ties": wins["tie"],
            "dim_delta_b_minus_a": dim_delta,
            "routing_b": {"true": tp, "false": fp, "missed": fn,
                          "precision": round(tp / (tp + fp), 3) if tp + fp else None,
                          "recall": round(tp / (tp + fn), 3) if tp + fn else None},
            "arm_a_routed_anomaly": sum(1 for s in sa if s["routed"]),
            "entity_coverage": {"a": cov_a, "b": cov_b,
                                "delta": (round(cov_b - cov_a, 3)
                                          if cov_a is not None and cov_b is not None else None)},
            "citation_violations": {"a": sum(s["citation_violations"] for s in sa),
                                    "b": sum(s["citation_violations"] for s in sb)},
            "declared_gaps": {"a": sum(s["declared_gaps"] for s in sa),
                              "b": sum(s["declared_gaps"] for s in sb)},
        }

    by_stratum = {}
    for st in _STRATA:
        ids = [i for i in paired if (rows_a[i].get("stratum") or "") == st]
        js = [j for j in j_ok if j.get("stratum") == st]
        if ids or js:
            by_stratum[st] = block(ids, js)
    overall = block(paired, j_ok)
    overall["sign_test_p"] = sign_test_p(overall["wins_a"], overall["wins_b"])
    return {"per_stratum": by_stratum, "overall": overall,
            "healthy_rows": {"a": len(rows_a), "b": len(rows_b), "paired": len(paired)},
            "judge_errors": [j for j in judgments if "error" in j]}


def print_table(summary: dict) -> None:
    hdr = (f"{'stratum':<8} {'n':>3} {'B-win':>5} {'A-win':>5} {'tie':>4} "
           f"{'Δfmt':>6} {'Δcov':>6} {'Δcoh':>6} {'Δhon':>6} "
           f"{'entcovΔ':>8} {'routeP':>7} {'routeR':>7} {'civ A/B':>8} {'gaps A/B':>9}")
    print(hdr)
    print("-" * len(hdr))

    def fmt(v, w=6):
        return f"{'—':>{w}}" if v is None else f"{v:>{w}.2f}"

    rows = [*summary["per_stratum"].items(), ("ALL", summary["overall"])]
    for name, b in rows:
        dd = b["dim_delta_b_minus_a"]
        rt = b["routing_b"]
        print(f"{name:<8} {b['n']:>3} {b['wins_b']:>5} {b['wins_a']:>5} {b['ties']:>4} "
              f"{fmt(dd['format_fit'])} {fmt(dd['coverage'])} {fmt(dd['coherence'])} "
              f"{fmt(dd['honesty'])} {fmt(b['entity_coverage']['delta'], 8)} "
              f"{fmt(rt['precision'], 7)} {fmt(rt['recall'], 7)} "
              f"{b['citation_violations']['a']:>3}/{b['citation_violations']['b']:<4} "
              f"{b['declared_gaps']['a']:>4}/{b['declared_gaps']['b']:<4}")
    o = summary["overall"]
    print(f"\nsign test (order-consistent wins, ties ignored): B={o['wins_b']} A={o['wins_a']} "
          f"→ exact two-sided p = {o['sign_test_p']:.4f}")
    if o["arm_a_routed_anomaly"]:
        print(f"WARNING: arm A routed on {o['arm_a_routed_anomaly']} row(s) — the routing flag "
              f"leaked into the baseline arm; the comparison is not clean.")


# ---------------------------------------------------------------------------------- main
def _build_judge_llm():
    """Prod-parity keys for the judge (setdefault — never clobbers explicit local env),
    then the service LLM, mirroring judge.py."""
    api = json.loads(subprocess.run(["railway", "variables", "--service", "noesis-api",
                                     "--json"], capture_output=True, text=True,
                                    cwd=ROOT).stdout)
    for k, v in api.items():
        if not k.startswith("RAILWAY_") and k != "PORT":
            os.environ.setdefault(k, v)
    import api.app as appmod
    return appmod.build_default_service().llm


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--slice", default="")
    ap.add_argument("--limit", type=int, default=1000)
    ap.add_argument("--patch-a", default="", help="prior arm-A run file: keep healthy rows")
    ap.add_argument("--patch-b", default="", help="prior arm-B run file: keep healthy rows")
    ap.add_argument("--judge-only", nargs=2, metavar=("RUNA", "RUNB"),
                    help="skip arm running; judge these two existing run files")
    ap.add_argument("--seed", type=int, default=20260814)
    ap.add_argument("--confirm-spend", action="store_true")
    a = ap.parse_args()

    def _resolve(p: str) -> pathlib.Path:
        return pathlib.Path(p) if p.startswith("/") else HERE / p

    if a.judge_only:
        run_a, run_b = _resolve(a.judge_only[0]), _resolve(a.judge_only[1])
        n = len(set(load_run_rows(run_a)) & set(load_run_rows(run_b)))
        print(f"PROJECTED SPEND (judge-only): pairwise judge = 2×{n} = {2 * n} calls.")
    else:
        if not a.slice:
            raise SystemExit("--slice is required unless --judge-only is given")
        sp = _resolve(a.slice)
        n = min(a.limit, sum(1 for ln in sp.read_text().splitlines() if ln.strip()))
        lo, hi = CALLS_PER_ANSWER
        print(f"PROJECTED SPEND: answers ≈ 2×{n}×({lo}–{hi}) ≈ {2 * n * lo}–{2 * n * hi} "
              f"LLM calls; pairwise judge = 2×{n} = {2 * n} calls.")
    if not a.confirm_spend:
        raise SystemExit("refusing to run without --confirm-spend (amendment B2)")

    if a.judge_only:
        pass                                    # run_a/run_b already set above
    else:
        run_a = run_arm(sp, a.limit, a.patch_a, ARM_A_ENV, "A")
        run_b = run_arm(sp, a.limit, a.patch_b, ARM_B_ENV, "B")

    rows_a, rows_b = load_run_rows(run_a), load_run_rows(run_b)
    llm = _build_judge_llm()
    judgments = asyncio.run(judge_pairs(llm, rows_a, rows_b, a.seed))
    summary = summarize(rows_a, rows_b, judgments)

    sha = subprocess.run(["git", "rev-parse", "--short", "HEAD"], capture_output=True,
                         text=True, cwd=ROOT).stdout.strip()
    provenance = {"git_sha": sha, "run_a": run_a.name, "run_b": run_b.name,
                  "arm_a_env": ARM_A_ENV, "arm_b_env": ARM_B_ENV, "seed": a.seed,
                  "judge_model": os.environ.get("NOESIS_LLM_MODEL", "(default anthropic)"),
                  "judge_prompt_sha": hashlib.sha256(
                      _PAIR_JUDGE_SYSTEM.encode()).hexdigest()[:12],
                  "ran_at": dt.datetime.now(dt.timezone.utc).isoformat()}
    structural = {arm: {i: structural_row(r) for i, r in rows.items()}
                  for arm, rows in (("A", rows_a), ("B", rows_b))}
    RUNS.mkdir(parents=True, exist_ok=True)
    stamp = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    dest = RUNS / f"ab-stage4-{stamp}.json"
    dest.write_text(json.dumps({"provenance": provenance, "summary": summary,
                                "structural": structural, "judgments": judgments}, indent=2))
    print_table(summary)
    print("saved:", dest.name)


if __name__ == "__main__":
    main()
