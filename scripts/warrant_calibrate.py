"""Measure judge-vs-physician agreement per warrant mode — step (b), part 2.

Given a physician's blind labels (from warrant_label_sheet.py) and the LLM judge's stored verdicts (in
the eval log), compute, per failure mode W1–W9, how often the judge and the physician agree — and,
crucially, whether the judge OVER-flags (false positives — flags a problem the physician doesn't) or
UNDER-flags (misses one). This is the gate: we only trust a mode's rates once the judge tracks the
physician on it. Comparison is at the CASE level per mode (did each flag mode Wk anywhere in this
answer?) — robust to per-claim index quibbles and it's what "is the judge trustworthy on Wk" needs.

Usage:
    LABELS=data/eval/warrant_labels.json .venv/bin/python scripts/warrant_calibrate.py
"""
import json
import os
import sys

LOG = os.environ.get("NOESIS_EVAL_LOG", os.path.join(os.path.dirname(__file__), "..", "data", "eval", "warrant_runs.jsonl"))
LABELS = os.environ.get("LABELS", os.path.join(os.path.dirname(LOG), "warrant_labels.json"))
_MODES = [f"W{i}" for i in range(1, 10)]
_ANSWER_MODES = {"W5", "W6", "W8", "W9"}


def _judge_modes(rec):
    """The set of W-modes the JUDGE flagged for one log record (flags-only schema; falls back to the
    legacy claim_verdicts shape for older records)."""
    v = rec.get("verdict", {}) or {}
    if "flags" in v:
        return {f.get("mode") for f in v.get("flags", []) if f.get("mode")}
    modes = {m for cv in v.get("claim_verdicts", []) for m in (cv.get("failure_modes") or [])}
    for lvl, code in (("coverage_gap", "W5"), ("salience_distortion", "W6"),
                      ("contradiction", "W8"), ("miscalibration", "W9")):
        if v.get(lvl):
            modes.add(code)
    return modes


def _human_modes(lab):
    """The set of W-modes the PHYSICIAN flagged for one labeled record."""
    modes = {m for m, on in (lab.get("answer_flags") or {}).items() if on}
    for _idx, ms in (lab.get("claim_flags") or {}).items():
        modes.update(ms or [])
    return modes


def main():
    if not os.path.exists(LABELS):
        print(f"no labels at {LABELS} — fill the sheet from warrant_label_sheet.py first"); sys.exit(1)
    labels = json.load(open(LABELS))
    by_ts = {json.loads(l)["ts"]: json.loads(l) for l in open(LOG) if l.strip()}
    pairs = []   # (judge_modes, human_modes) per labeled record that we could match to a log verdict
    for rid, lab in labels.items():
        rec = by_ts.get(rid)
        if not rec:
            print(f"  (skip {rid}: no matching log record)"); continue
        pairs.append((_judge_modes(rec), _human_modes(lab)))
    if not pairs:
        print("no matched labeled records"); sys.exit(1)

    print(f"calibration over {len(pairs)} labeled answers\n")
    print(f"  {'mode':4s} {'both':>5s} {'judge-only':>11s} {'human-only':>11s} {'agree%':>7s}  verdict")
    trustworthy, suspect = [], []
    for m in _MODES:
        tp = sum(1 for j, h in pairs if m in j and m in h)          # both flagged
        fp = sum(1 for j, h in pairs if m in j and m not in h)      # judge over-flags
        fn = sum(1 for j, h in pairs if m not in j and m in h)      # judge misses
        tn = sum(1 for j, h in pairs if m not in j and m not in h)
        agree = (tp + tn) / len(pairs)
        # a mode is trustworthy when the judge neither systematically over- nor under-flags it
        base = tp + fp + fn
        note = "n/a (never flagged)" if base == 0 else (
               "OVER-flags" if fp > tp + fn else
               "UNDER-flags" if fn > tp + fp else
               "ok" if tp >= max(fp, fn) else "noisy")
        (trustworthy if note == "ok" else suspect).append(m)
        print(f"  {m:4s} {tp:5d} {fp:11d} {fn:11d} {agree:6.0%}   {note}")
    print(f"\ntrustworthy modes: {', '.join(trustworthy) or 'none yet'}")
    print(f"needs rubric work : {', '.join(m for m in suspect) or 'none'}")
    print("\nOnly report failure rates for the trustworthy modes; fix the rubric/prompt for the rest, "
          "re-run the eval, and re-label until the judge tracks the physician.")


if __name__ == "__main__":
    main()
