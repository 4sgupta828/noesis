"""Held-out eval gold for the medical vertical (against the bundled sample trials)."""
from __future__ import annotations

GOLD = {
    "trial_condition": {
        "question": "What condition is the iron cereals trial studying?",
        "expect": "value",
        "expected_values": ["Iron Deficiency"],
        "supporting_quote": "Iron Deficiency",
    },
    "coverage_gap_unknown_condition": {
        "question": "What trials cover glioblastoma in this corpus?",
        "expect": "refuse",     # not in the 2-trial sample → honest gap
    },
}
