"""Run the INDIA clinical-gold benchmark against a Noesis deployment and score it deterministically.

Mirrors the US top-50 baseline: hits /research (or set MODE=panel for /panel/ask/stream) for each
INDIA_CLINICAL_GOLD case, scores forbidden overclaims + evidence_floor + absence + risk weighting.

Against the CURRENT (global) corpus this is EXPECTED to expose India gaps (missing ICMR/Indian-journal
evidence, Indian brands) — that gap is the signal for what to ingest. After Indian-source ingestion +
`source_country=IN` scoping (NOESIS_COUNTRY_SCOPE=1, countries=["IN"]), re-run to measure the lift.

Usage:
    NOESIS_URL=https://noesis-api-production.up.railway.app .venv/bin/python scripts/run_india_baseline.py
    (optional) SUBSET="tb_new_pulmonary_first_line,dengue_analgesia_safety"  # smoke a few
"""
import json
import os
import sys
import time
import urllib.request

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "packages", "vertical_medical"))
from noesis_vertical_medical.eval_india_gold import INDIA_CLINICAL_GOLD  # noqa: E402

URL = os.environ.get("NOESIS_URL", "https://noesis-api-production.up.railway.app").rstrip("/") + "/research"
TENANT = os.environ.get("TENANT", "demo")
SUBSET = {s.strip() for s in os.environ.get("SUBSET", "").split(",") if s.strip()}
COUNTRIES = [c for c in os.environ.get("COUNTRIES", "").split(",") if c.strip()]   # e.g. IN (needs the flag on)
REQ_TIMEOUT = int(os.environ.get("REQ_TIMEOUT", "300"))   # per-request timeout (prod can be slow under load)
RISK_W = {"low": 1, "med": 3, "high": 8}


def ask(q):
    body = {"question": q, "tenant_id": TENANT}
    if COUNTRIES:
        body["countries"] = COUNTRIES
    last = None
    for attempt in range(3):
        try:
            req = urllib.request.Request(URL, json.dumps(body).encode(), {"Content-Type": "application/json"})
            with urllib.request.urlopen(req, timeout=REQ_TIMEOUT) as r:
                return json.load(r)
        except Exception as e:   # noqa: BLE001
            last = e
            time.sleep(8 * (attempt + 1))
    raise last


def score(spec, d):
    prose = (d.get("answer") or "").lower()
    grounded = bool(d.get("grounded"))
    tiers = (d.get("diagnostics") or {}).get("evidence_tiers") or {}
    if spec.get("expect") == "absence":
        gaps = d.get("coverage_gaps") or []
        confab = any(p.lower() in prose for p in spec.get("forbidden_phrases", []))
        ok = bool(gaps) and not confab
        return {"ok": ok, "why": "flagged gap" if ok else ("OVERCLAIMED" if confab else "did not flag gap"), "tiers": tiers}
    forb_ok = not any(p.lower() in prose for p in spec.get("forbidden_phrases", []))
    floor = set(spec.get("evidence_floor_kinds", ()))
    floor_ok = (not floor) or any(t in floor and n > 0 for t, n in tiers.items())
    ok = grounded and forb_ok and floor_ok
    why = []
    if not grounded: why.append("not grounded")
    if not forb_ok: why.append("FORBIDDEN overclaim")
    if not floor_ok: why.append("evidence_floor miss (no India-tier evidence?)")
    return {"ok": ok, "why": ", ".join(why) or "pass", "tiers": tiers}


def main():
    cases = [(c, s) for c, s in INDIA_CLINICAL_GOLD.items() if not SUBSET or c in SUBSET]
    res = {}
    for i, (cid, spec) in enumerate(cases, 1):
        t0 = time.time()
        try:
            s = score(spec, ask(spec["question"]))
        except Exception as e:   # noqa: BLE001
            s = {"ok": False, "why": f"ERROR {e}", "tiers": {}}
        s["risk"] = spec.get("clinical_risk", "low")
        res[cid] = s
        print(f"[{i:2d}/{len(cases)}] {'PASS' if s['ok'] else 'FAIL'} {s['risk']:4s} {cid:34s} "
              f"{s['why']:38s} tiers={s['tiers']} ({time.time()-t0:.0f}s)", flush=True)
    n = len(res); p = sum(1 for s in res.values() if s["ok"])
    ws = sum(RISK_W[s["risk"]] for s in res.values()); wp = sum(RISK_W[s["risk"]] for s in res.values() if s["ok"])
    crit = [c for c, s in res.items() if not s["ok"] and s["risk"] == "high"]
    print(f"\n=== INDIA BASELINE (tenant={TENANT}, countries={COUNTRIES or 'none'}) ===")
    print(f"pass_rate        : {p}/{n} = {p/n:.2f}")
    print(f"risk_weighted    : {wp}/{ws} = {wp/ws:.2f}")
    print(f"critical_failures: {crit}")


if __name__ == "__main__":
    main()
