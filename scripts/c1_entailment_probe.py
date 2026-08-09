"""C1 auditor prototype — an adversarial ENTAILMENT audit over already-logged answers.

Two jobs at once:
  1) Prototype C1 (the claim→evidence auditor): for each recommendation-bearing statement in an answer,
     a skeptical judge decides whether the cited finding actually ENTAILS it — defaulting to "warranted"
     and flagging only over-reach (W1) / descriptive-as-normative (W2) / inapplicable (W3), each grounded
     in verbatim spans (Rule-18 falsifiability filter, reused from the eval).
  2) Proxy-VALIDATE the eval's W1/W2/W3 signal without a physician: this is an INDEPENDENT, stricter,
     differently-prompted judge. Where it AGREES with the broad eval judge on a mode, that mode is much
     more likely real (two independent judges); where it clears the eval's flags, the eval over-flagged.

Runs OFFLINE over the accumulating log (no new prod calls → cheap). Usage:
    N=21 DEPTH=focused .venv/bin/python scripts/c1_entailment_probe.py
"""
import json
import os
import sys
from typing import Literal

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "packages", "kernel"))
from pydantic import BaseModel, Field  # noqa: E402
from noesis_kernel.runtime.build import build_llm  # noqa: E402

LOG = os.environ.get("NOESIS_EVAL_LOG", os.path.join(os.path.dirname(__file__), "..", "data", "eval", "warrant_runs.jsonl"))
N = int(os.environ.get("N", "21"))
DEPTH = os.environ.get("DEPTH", "focused")
_KIND2W = {"over_reach": "W1", "descriptive_as_normative": "W2", "inapplicable": "W3"}


class AuditFlag(BaseModel):
    finding_index: int | None = Field(default=None, description="1-based cited finding this statement rests on")
    answer_span: str = Field(default="", description="the recommendation-bearing statement, VERBATIM from the answer")
    kind: Literal["over_reach", "descriptive_as_normative", "inapplicable"]
    source_span: str = Field(default="", description="VERBATIM phrase from the finding showing it does NOT establish the statement")
    why: str = ""


class Audit(BaseModel):
    n_recommendations: int = 0
    unwarranted: list[AuditFlag] = Field(default_factory=list)
    summary: str = ""


_SYS = (
    "You are a SKEPTICAL clinical-evidence auditor. For each recommendation-bearing statement in the "
    "ANSWER, the DEFAULT is that it is WARRANTED by its cited finding — you are looking only for the "
    "minority that are not. Flag a statement ONLY when the cited finding does not actually establish it:\n"
    "- over_reach: the finding merely mentions/touches the topic but does not support the specific "
    "recommendation or its strength;\n"
    "- descriptive_as_normative: the finding describes what was done / observed (a case, a trial protocol) "
    "and the answer turns that into a general 'should do X';\n"
    "- inapplicable: the finding is about a different population/setting/purpose than the question.\n"
    "FALSIFIABILITY: copy `answer_span` VERBATIM from the answer and `source_span` VERBATIM from the "
    "finding. If you cannot copy both, the statement is warranted — do NOT flag it. Be strict but honest: "
    "a real flag means a clinician relying on that sentence would be misled. Also return n_recommendations "
    "(how many recommendation-bearing statements the answer makes)."
)


def _load():
    recs = [json.loads(l) for l in open(LOG) if l.strip()]
    recs = [r for r in recs if (not DEPTH or r.get("depth") == DEPTH) and r.get("mode") == "research"]
    # de-dupe to the most recent record per case_id, take N
    by_case = {}
    for r in recs:
        by_case[r["case_id"]] = r
    return list(by_case.values())[:N]


def _in(s, hay):
    return bool(s) and s.strip().lower() in hay


def _filter(a: Audit, answer, claims):
    al = answer.lower()
    kept = []
    for f in a.unwarranted:
        if not _in(f.answer_span, al):
            continue
        src = ""
        if f.finding_index and 1 <= f.finding_index <= len(claims):
            c = claims[f.finding_index - 1]
            src = (str(c.get("text", "")) + " " + str(c.get("quote", ""))).lower()
        if f.source_span and not _in(f.source_span, src):
            continue
        kept.append(f)
    a.unwarranted = kept
    return a


async def _audit(llm, q, answer, claims):
    findings = "\n".join(
        f"[{i+1}] {c.get('text','')}\n     quote: \"{c.get('quote','')}\"  — {c.get('source','')}"
        for i, c in enumerate(claims))
    user = (f"QUESTION:\n{q}\n\nANSWER:\n{answer}\n\nFINDINGS (the source text each [n] rests on):\n{findings}\n\n"
            "Return only the recommendation-bearing statements the cited finding does NOT establish, with "
            "copied answer_span + source_span. Plus n_recommendations.")
    comp = await llm.complete(system=_SYS, messages=[{"role": "user", "content": user}],
                              response_format=Audit, max_tokens=3000)
    return comp.parsed


def _eval_modes(rec):
    v = rec.get("verdict", {}) or {}
    return {f.get("mode") for f in v.get("flags", []) if f.get("mode")}


def main():
    import asyncio
    llm = build_llm(mode="live")
    recs = _load()
    if not recs:
        print("no logged research answers found — run the eval first"); return
    print(f"C1 entailment probe · {len(recs)} logged answers\n")
    tot_recs = tot_flags = 0
    agree = {"W1": [0, 0, 0], "W2": [0, 0, 0], "W3": [0, 0, 0]}   # [both, auditor-only, eval-only]
    n_eval = 0
    for r in recs:
        claims = r.get("claims") or []
        a = None
        for attempt in range(3):   # the model occasionally malforms the structured list — a fresh sample fixes it
            try:
                a = asyncio.run(_audit(llm, r["question"], r["answer"], claims)); break
            except Exception as e:  # noqa: BLE001
                if attempt == 2:
                    print(f"  {r['case_id']:34s} JUDGE ERROR (skipped): {str(e)[:60]}")
        if a is None:
            continue
        n_eval += 1
        a = _filter(a, r["answer"], claims)
        tot_recs += a.n_recommendations
        tot_flags += len(a.unwarranted)
        amodes = {_KIND2W[f.kind] for f in a.unwarranted}
        emodes = _eval_modes(r)
        for m in ("W1", "W2", "W3"):
            if m in amodes and m in emodes: agree[m][0] += 1
            elif m in amodes: agree[m][1] += 1
            elif m in emodes: agree[m][2] += 1
        print(f"  {r['case_id']:34s} recs={a.n_recommendations:2d} unwarranted={len(a.unwarranted):2d}  "
              f"[{','.join(sorted(amodes)) or '—'}]  eval:[{','.join(sorted(emodes & {'W1','W2','W3'})) or '—'}]")
    print(f"\naudited {n_eval}/{len(recs)} answers · total recommendation-bearing statements: {tot_recs}")
    print(f"flagged unwarranted by the strict auditor : {tot_flags}"
          f"  ({tot_flags/max(tot_recs,1):.0%} of statements)")
    print("\n=== agreement with the broad eval judge (cases) ===")
    print(f"  {'mode':4s} {'both':>5s} {'auditor-only':>13s} {'eval-only':>10s}   read")
    for m in ("W1", "W2", "W3"):
        both, ao, eo = agree[m]
        read = ("CONFIRMED (both judges)" if both >= max(ao, eo) and both > 0 else
                "eval likely over-flagged" if eo > both + ao else
                "auditor finds MORE" if ao > both + eo else "mixed")
        print(f"  {m:4s} {both:5d} {ao:13d} {eo:10d}   {read}")


if __name__ == "__main__":
    main()
