"""Load the bundled sample trials (offline fixture for tests + a default corpus)."""
from __future__ import annotations

import json
from pathlib import Path

_DATA = Path(__file__).resolve().parent / "data" / "trials_sample.json"


def sample_studies() -> list[dict]:
    return json.loads(_DATA.read_text())
