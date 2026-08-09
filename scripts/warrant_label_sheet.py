"""Emit a BLIND physician-labeling worksheet from the warrant eval log — step (b), part 1.

Before we trust the LLM judge's W1–W9 rates, a physician labels a sample of the SAME answers WITHOUT
seeing the judge's verdict; `warrant_calibrate.py` then measures agreement per mode. This script pulls
recent records from the accumulating log and writes:
  - a readable Markdown sheet (the answer + numbered claims + a blank W-checklist), and
  - a JSON template the physician fills (judge verdict deliberately omitted → blind).

Usage:
    .venv/bin/python scripts/warrant_label_sheet.py                 # newest 8 records
    N=12 MODE=panel .venv/bin/python scripts/warrant_label_sheet.py # newest 12 panel records
Output goes next to the log (data/eval/). The physician edits the .json; then run warrant_calibrate.py.
"""
import json
import os
import sys

LOG = os.environ.get("NOESIS_EVAL_LOG", os.path.join(os.path.dirname(__file__), "..", "data", "eval", "warrant_runs.jsonl"))
N = int(os.environ.get("N", "8"))
MODE = os.environ.get("MODE", "")   # "" = any · "research" · "panel"
OUT = os.environ.get("OUT", os.path.join(os.path.dirname(LOG), "warrant_labels"))

_W = {
 "W1": "Unwarranted (source doesn't establish the claim)",
 "W2": "Descriptive→normative ('X was done' used as 'do X')",
 "W3": "Inapplicable (wrong population/setting/purpose)",
 "W4": "Tier-mismatch (weak source drives a routine recommendation)",
 "W5": "Coverage gap (a material, actionable option omitted)",
 "W6": "Salience distortion (loudest topic over-weighted)",
 "W7": "Conditionality collapse ('do if X' shown as routine)",
 "W8": "Contradiction (recommendation vs a stated safety caveat)",
 "W9": "Miscalibration (stated confidence ≠ evidence strength)",
}
_CLAIM_MODES = ["W1", "W2", "W3", "W4", "W7"]     # judged per claim
_ANSWER_MODES = ["W5", "W6", "W8", "W9"]          # judged for the whole answer


def main():
    if not os.path.exists(LOG):
        print(f"no log at {LOG} — run scripts/eval_warrant.py first"); sys.exit(1)
    recs = [json.loads(l) for l in open(LOG) if l.strip()]
    if MODE:
        recs = [r for r in recs if r.get("mode") == MODE]
    recs = recs[-N:]
    if not recs:
        print("no matching records"); sys.exit(1)

    md, template = [], {}
    md.append("# Warrant labeling worksheet (blind — judge verdict hidden)\n")
    md.append("For each answer: read it, then mark which failure modes you (the physician) see. "
              "Per-claim modes attach to a claim number; answer-level modes to the whole answer. "
              "Fill the matching `.json` file (rec_id → your labels) and run `warrant_calibrate.py`.\n")
    md.append("Legend — claim-level: " + " · ".join(f"**{k}** {_W[k]}" for k in _CLAIM_MODES))
    md.append("\nLegend — answer-level: " + " · ".join(f"**{k}** {_W[k]}" for k in _ANSWER_MODES) + "\n")
    for i, r in enumerate(recs):
        rid = r.get("ts", f"rec{i}")
        claims = []   # reconstruct claim list length from verdict if present, else from n_claims
        n_claims = r.get("n_claims", 0)
        md.append("\n---\n")
        md.append(f"## [{i+1}] {r.get('case_id','?')}  · mode={r.get('mode','')}  · rec_id=`{rid}`\n")
        md.append(f"**Question:** {r.get('question','')}\n")
        md.append(f"**Answer:**\n\n{r.get('answer','')}\n")
        md.append(f"\n*({n_claims} findings underlie this answer — see the product's Evidence section "
                  f"for the numbered claims + quotes.)*\n")
        md.append("\n**Your labels:**")
        md.append("- Answer-level modes present (list any of W5/W6/W8/W9): __________")
        md.append("- Per-claim modes present (e.g. `3:W2, 5:W3`): __________")
        md.append("- Notes: __________")
        template[rid] = {
            "case_id": r.get("case_id", ""), "mode": r.get("mode", ""),
            "answer_flags": {m: False for m in _ANSWER_MODES},   # set true where present
            "claim_flags": {},                                    # e.g. {"3": ["W2"], "5": ["W3"]}
            "notes": "",
        }
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT + ".md", "w") as f:
        f.write("\n".join(md))
    with open(OUT + ".json", "w") as f:
        json.dump(template, f, indent=2)
    print(f"wrote {len(recs)} records to:\n  {OUT}.md   (read this)\n  {OUT}.json  (physician fills this)")
    print("Then: LABELS=%s.json .venv/bin/python scripts/warrant_calibrate.py" % OUT)


if __name__ == "__main__":
    main()
