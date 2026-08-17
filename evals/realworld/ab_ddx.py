"""DDx / clinical-decision paired A/B harness — NOESIS_DIFFERENTIAL_FORMAT (differential-first
clinical-decision compose) ON vs OFF, both arms through the REASONED engine.

Modeled EXACTLY on ab_stage4.py (same flipped-pairwise LLM judge, consistent_winner, sign_test,
subprocess-per-arm run.py invocation). Only what a clinical-decision A/B needs is changed: the arm
flags, the code-only structural gold metrics (repointed to the DDx gold), and the judge rubric.

Both arms run the SAME 15-vignette DDx slice through run.py in a subprocess with per-arm env, so
run.py's `_prod_env` override-preserving behavior applies per arm (Railway values, except the
NOESIS_* knobs the arm explicitly sets). BOTH arms set NOESIS_EVAL_REASONED=1 so run.py drives
`svc.ask_reasoned(...)` — the prod path for clinical-decision questions — and BOTH set
NOESIS_DIFFERENTIAL_FORMAT explicitly (A="" so neither inherits a prod value):

  A (baseline): NOESIS_EVIDENCE_IDENTITY=1 NOESIS_CLAIM_CONGRUENCE=1
                NOESIS_QUESTION_CONTRACT=steer NOESIS_EVAL_REASONED=1 NOESIS_DIFFERENTIAL_FORMAT=""
  B (differential): same + NOESIS_DIFFERENTIAL_FORMAT=1

Per row, STRUCTURAL metrics are code-only (no LLM), scored against the DDx gold:
  - top_dx_coverage: fraction of gold.top_dx whose key label appears in the answer;
  - cant_miss_coverage: fraction of gold.cant_miss surfaced — THE key safety metric;
  - discriminator_hit: whether the gold.discriminator's key test tokens appear in the answer.

The comparative signal is a PAIRWISE LLM judge (the sensitivity fix over absolute scoring): each
question's two answers are presented in seeded-random order, then again FLIPPED (2 judge calls/
question, mapping recorded). A "win" counts only when BOTH orderings agree (order-consistent);
anything else is a tie. Overall significance: exact two-sided binomial sign test on order-consistent
wins, ties ignored (implemented directly — no scipy).

Usage:
  .venv/bin/python evals/realworld/ab_ddx.py \
      --slice slices/slice-ddx-clinical-15-2026-08-17.jsonl [--limit N] \
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

# Both arms go through the REASONED engine (prod path for clinical-decision Qs); both set
# NOESIS_DIFFERENTIAL_FORMAT explicitly so neither inherits a prod value. A="" (off), B="1" (on).
ARM_A_ENV = {"NOESIS_EVIDENCE_IDENTITY": "1", "NOESIS_CLAIM_CONGRUENCE": "1",
             "NOESIS_QUESTION_CONTRACT": "steer", "NOESIS_EVAL_REASONED": "1",
             "NOESIS_DIFFERENTIAL_FORMAT": ""}
ARM_B_ENV = {**ARM_A_ENV, "NOESIS_DIFFERENTIAL_FORMAT": "1"}

_DIMS = ("differential_quality", "decision_framework", "evidence", "honesty")


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


def _key_term(dx: str) -> str:
    """The primary label of a gold diagnosis: the text before any parenthetical qualifier or
    '/' alternative — e.g. 'heart failure (HFrEF or HFpEF)' -> 'heart failure',
    'acute coronary syndrome / ischemic cardiomyopathy' -> 'acute coronary syndrome'. This is a
    STRUCTURAL strip (splitting a string on a delimiter, Rule 18: code owns structure), NOT a
    semantic rewrite — it just avoids demanding the parenthetical trivia appear verbatim."""
    return re.split(r"[(/]", dx, maxsplit=1)[0].strip()


def top_dx_coverage(row: dict) -> float | None:
    """Fraction of gold.top_dx whose key label appears (normalized containment) in the answer.
    None when the row carries no gold top_dx."""
    dxs = (row.get("gold") or {}).get("top_dx") or []
    if not dxs:
        return None
    ans = row.get("answer") or ""
    return sum(1 for d in dxs if _contains(_key_term(d), ans)) / len(dxs)


def cant_miss_coverage(row: dict) -> float | None:
    """Fraction of gold.cant_miss diagnoses surfaced (normalized containment) in the answer — THE
    key safety metric (a missed can't-miss dx is the dangerous failure). None when no can't-miss."""
    cm = (row.get("gold") or {}).get("cant_miss") or []
    if not cm:
        return None
    ans = row.get("answer") or ""
    return sum(1 for d in cm if _contains(_key_term(d), ans)) / len(cm)


# filler / connective words in a discriminator sentence that are NOT test names — dropped so the
# hit test keys on the actual test tokens (ECG, troponin, ultrasound, ...), not sentence glue.
_DISCRIM_STOP = {
    "the", "a", "an", "and", "or", "plus", "then", "with", "for", "if", "of", "to", "in", "on",
    "immediately", "first", "serial", "initial", "next", "test", "tests", "assessment", "study",
    "studies", "evaluation", "consider", "persists", "suspicion", "probability", "high", "low",
    "risk", "stratify", "score", "clinical", "status", "preferred", "over", "before", "after",
    "most", "single", "discriminating", "urgent", "bedside", "screen",
}


def _sig_tokens(s: str) -> list[str]:
    """Significant (non-filler, len>1) tokens of a discriminator sentence — structural tokenization,
    no semantics."""
    return [t for t in _norm(s).split() if t not in _DISCRIM_STOP and len(t) > 1]


def _has_word(tok: str, normed_hay: str) -> bool:
    return f" {tok} " in f" {normed_hay} "


def discriminator_hit(row: dict) -> bool | None:
    """Whether the gold.discriminator's key test tokens appear in the answer. Conservative
    structural proxy: >= half of the discriminator's significant (non-filler) tokens present as
    whole words in the answer (so 'ECG plus serial troponin' hits when the answer names ECG and
    troponin, regardless of the sentence glue). None when the discriminator has no significant
    tokens."""
    toks = set(_sig_tokens((row.get("gold") or {}).get("discriminator") or ""))
    if not toks:
        return None
    ans = _norm(row.get("answer") or "")
    present = sum(1 for t in toks if _has_word(t, ans))
    return (present / len(toks)) >= 0.5


def structural_row(row: dict) -> dict:
    return {"top_dx_coverage": top_dx_coverage(row),
            "cant_miss_coverage": cant_miss_coverage(row),
            "discriminator_hit": discriminator_hit(row)}


# ------------------------------------------------------------------------ pairwise judge
_PAIR_JUDGE_SYSTEM = """You compare TWO candidate answers (labeled "first" and "second") to the SAME \
clinical vignette — a differential-diagnosis / clinical-decision question posed by a clinician. Judge \
DECISION usefulness for a careful physician reader — never style, never length for its own sake. This \
is decision support, so an answer that is diagnostically complete, safely prioritized, and honestly \
grounded beats one that is merely fluent. Score EACH answer 1-5 on:

- differential_quality: are the plausible diagnoses actually ENUMERATED and qualitatively RANKED (most \
likely vs less likely), and are the CAN'T-MISS / dangerous diagnoses explicitly surfaced? Penalize a \
vague prose gesture at "many causes" and penalize omitting a life-threatening diagnosis the vignette \
demands.
- decision_framework: is there a clear WORKUP (what test next, in what order) and are the \
WHAT-CHANGES-MANAGEMENT thresholds explicit (result X -> action Y)? Reward a reader who could act; \
penalize an undifferentiated list with no decision logic.
- evidence: grounded and cited, at guideline / high-tier evidence where such guidance exists, with \
honest gaps where evidence is thin. Never reward confident overreach beyond the cited evidence.
- honesty: no fabricated numbers, no invented test performance or thresholds, no overconfident \
single-diagnosis anchoring where the vignette is genuinely ambiguous. An answer that overclaims scores \
LOW here even if fluent.

Then pick `better`: "first", "second", or "tie" — the answer the clinician would genuinely prefer to \
act on. Give a rationale of at most 50 words."""


class PairVerdict(BaseModel):
    better: Literal["first", "second", "tie"] = "tie"
    differential_quality_first: int = Field(3, ge=1, le=5)
    differential_quality_second: int = Field(3, ge=1, le=5)
    decision_framework_first: int = Field(3, ge=1, le=5)
    decision_framework_second: int = Field(3, ge=1, le=5)
    evidence_first: int = Field(3, ge=1, le=5)
    evidence_second: int = Field(3, ge=1, le=5)
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


def _delta(a: float | None, b: float | None) -> float | None:
    return round(b - a, 3) if a is not None and b is not None else None


def _hit_rate(structs: list[dict]) -> float | None:
    """Fraction of rows whose discriminator_hit is True, over rows where it is defined."""
    vals = [s["discriminator_hit"] for s in structs if s["discriminator_hit"] is not None]
    return round(sum(1 for v in vals if v) / len(vals), 3) if vals else None


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
        top_a, top_b = _mean([s["top_dx_coverage"] for s in sa]), _mean([s["top_dx_coverage"] for s in sb])
        cm_a, cm_b = _mean([s["cant_miss_coverage"] for s in sa]), _mean([s["cant_miss_coverage"] for s in sb])
        dh_a, dh_b = _hit_rate(sa), _hit_rate(sb)
        return {
            "n": len(ids), "judged": len(js),
            "wins_b": wins["B"], "wins_a": wins["A"], "ties": wins["tie"],
            "dim_delta_b_minus_a": dim_delta,
            "top_dx_coverage": {"a": top_a, "b": top_b, "delta": _delta(top_a, top_b)},
            "cant_miss_coverage": {"a": cm_a, "b": cm_b, "delta": _delta(cm_a, cm_b)},
            "discriminator_hit": {"a": dh_a, "b": dh_b, "delta": _delta(dh_a, dh_b)},
        }

    strata = sorted({(rows_a[i].get("stratum") or "") for i in paired})
    by_stratum = {}
    for st in strata:
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
    hdr = (f"{'stratum':<16} {'n':>3} {'B-win':>5} {'A-win':>5} {'tie':>4} "
           f"{'Δdiff':>6} {'Δdec':>6} {'Δev':>6} {'Δhon':>6} "
           f"{'topDxΔ':>7} {'cantMissΔ':>10} {'discrimΔ':>9}")
    print(hdr)
    print("-" * len(hdr))

    def fmt(v, w=6):
        return f"{'—':>{w}}" if v is None else f"{v:>{w}.2f}"

    rows = [*summary["per_stratum"].items(), ("ALL", summary["overall"])]
    for name, b in rows:
        dd = b["dim_delta_b_minus_a"]
        print(f"{name:<16} {b['n']:>3} {b['wins_b']:>5} {b['wins_a']:>5} {b['ties']:>4} "
              f"{fmt(dd['differential_quality'])} {fmt(dd['decision_framework'])} "
              f"{fmt(dd['evidence'])} {fmt(dd['honesty'])} "
              f"{fmt(b['top_dx_coverage']['delta'], 7)} "
              f"{fmt(b['cant_miss_coverage']['delta'], 10)} "
              f"{fmt(b['discriminator_hit']['delta'], 9)}")
    o = summary["overall"]
    print(f"\nsign test (order-consistent wins, ties ignored): B={o['wins_b']} A={o['wins_a']} "
          f"→ exact two-sided p = {o['sign_test_p']:.4f}")
    cm = o["cant_miss_coverage"]
    print(f"can't-miss coverage (SAFETY): A={fmt(cm['a'])} B={fmt(cm['b'])} Δ={fmt(cm['delta'])}")
    if cm["delta"] is not None and cm["delta"] < 0:
        print("WARNING: arm B surfaced FEWER can't-miss diagnoses than arm A — a safety regression; "
              "B is NOT better regardless of judge wins.")


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
    ap.add_argument("--seed", type=int, default=20260817)
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
    dest = RUNS / f"ab-ddx-{stamp}.json"
    dest.write_text(json.dumps({"provenance": provenance, "summary": summary,
                                "structural": structural, "judgments": judgments}, indent=2))
    print_table(summary)
    print("saved:", dest.name)


if __name__ == "__main__":
    main()
