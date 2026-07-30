"""Held-out eval gold for the regulatory vertical.

Two cases keep the gate honest: (1) a covered question with a grounded answer,
(2) an ADVERSARIAL case for a jurisdiction the corpus lacks — the honest answer
is a coverage gap with zero fabricated claims. Quotes are real substrings of the
fixture (Rule 5/6). Gold is data only — never placed in a prompt/few-shot.
"""
from __future__ import annotations

GOLD = {
    "grounded_value": {
        "question": "What return on equity did the Commission approve?",
        "expect": "value",
        "expected_values": ["9.6"],
        "supporting_quote": "the commission approves a return on equity of 9.6 percent",
    },
    "coverage_gap_out_of_state": {
        "question": "What return on equity was approved in CA?",
        "expect": "refuse",           # CA not in the corpus → honest gap, no claim
    },
}
