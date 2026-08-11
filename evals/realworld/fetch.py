"""License-verified dataset fetch → evals/realworld/data/ + manifest (URL, sha256, license).

Usage: .venv/bin/python evals/realworld/fetch.py [--sets healthbench,healthbench_hard,kqa]
Datasets land git-ignored; the manifest is the auditable record (Rule 11).
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import pathlib
import urllib.request

HERE = pathlib.Path(__file__).parent
DATA = HERE / "data"

SETS = {
    # name: (url, license, license_source)
    "healthbench": (
        "https://openaipublic.blob.core.windows.net/simple-evals/healthbench/2025-05-07-06-14-12_oss_eval.jsonl",
        "MIT", "github.com/openai/simple-evals (LICENSE)"),
    "healthbench_hard": (
        "https://openaipublic.blob.core.windows.net/simple-evals/healthbench/hard_2025-05-08-21-00-10.jsonl",
        "MIT", "github.com/openai/simple-evals (LICENSE)"),
    "healthbench_consensus": (
        "https://openaipublic.blob.core.windows.net/simple-evals/healthbench/consensus_2025-05-09-20-00-46.jsonl",
        "MIT", "github.com/openai/simple-evals (LICENSE)"),
    "kqa": (
        "https://raw.githubusercontent.com/Itaymanes/K-QA/main/dataset/questions_w_answers.jsonl",
        "MIT", "github.com/Itaymanes/K-QA (LICENSE)"),
    "kqa_questions": (
        "https://raw.githubusercontent.com/Itaymanes/K-QA/main/dataset/questions.jsonl",
        "MIT", "github.com/Itaymanes/K-QA (LICENSE)"),
}


def fetch(name: str) -> dict:
    url, license_, src = SETS[name]
    DATA.mkdir(parents=True, exist_ok=True)
    dest = DATA / f"{name}.jsonl"
    raw = urllib.request.urlopen(url, timeout=120).read()
    dest.write_bytes(raw)
    lines = sum(1 for ln in raw.splitlines() if ln.strip())
    return {"name": name, "url": url, "license": license_, "license_source": src,
            "sha256": hashlib.sha256(raw).hexdigest(), "bytes": len(raw), "records": lines,
            "fetched_at": dt.datetime.now(dt.timezone.utc).isoformat()}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--sets", default="healthbench,healthbench_hard,kqa")
    args = ap.parse_args()
    manifest_path = DATA / "manifest.json"
    manifest = json.loads(manifest_path.read_text()) if manifest_path.exists() else {}
    for name in [s.strip() for s in args.sets.split(",") if s.strip()]:
        if name not in SETS:
            raise SystemExit(f"unknown set {name!r} (known: {sorted(SETS)})")
        info = fetch(name)
        manifest[name] = info
        print(f"fetched {name}: {info['records']} records, {info['bytes']:,} bytes, "
              f"license {info['license']}")
    manifest_path.write_text(json.dumps(manifest, indent=2))
    print(f"manifest → {manifest_path}")


if __name__ == "__main__":
    main()
