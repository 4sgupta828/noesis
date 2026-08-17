"""Offline tests (no network, no LLM) for the Specialist-Panel DDx differential-synthesis A/B
instrument. Asserts the PANEL arm envs are exactly as specified (both panel + contract + dedup on;
A differential OFF, B ON) and that the reused DDx structural metric functions still behave.

Run: .venv/bin/python -m pytest evals/realworld/test_ab_panel_ddx.py -q
"""
from __future__ import annotations

import importlib.util
import pathlib
import sys

import pytest

HERE = pathlib.Path(__file__).parent


def _load_module():
    spec = importlib.util.spec_from_file_location("ab_panel_ddx", HERE / "ab_panel_ddx.py")
    m = importlib.util.module_from_spec(spec)
    sys.modules["ab_panel_ddx"] = m
    spec.loader.exec_module(m)
    return m


ab = _load_module()


def _row(top_dx=("acute coronary syndrome (STEMI/NSTEMI/unstable angina)",),
         cant_miss=("acute coronary syndrome", "aortic dissection", "pulmonary embolism"),
         discriminator="12-lead ECG immediately plus serial high-sensitivity troponin",
         answer="", stratum="cardiac") -> dict:
    return {"id": "x", "stratum": stratum, "question": "q", "answer": answer,
            "gold": {"top_dx": list(top_dx), "cant_miss": list(cant_miss),
                     "discriminator": discriminator, "threshold": "ST-elevation -> reperfusion"}}


# ------------------------------------------------------------------------------ arm setup
def test_arm_envs_exact() -> None:
    assert ab.ARM_A_ENV == {"NOESIS_EVIDENCE_IDENTITY": "1", "NOESIS_CLAIM_CONGRUENCE": "1",
                            "NOESIS_EVAL_PANEL": "1", "NOESIS_PANEL_CONTRACT": "1",
                            "NOESIS_PANEL_DEDUP": "1", "NOESIS_PANEL_DIFFERENTIAL": ""}
    assert ab.ARM_B_ENV == {**ab.ARM_A_ENV, "NOESIS_PANEL_DIFFERENTIAL": "1"}


def test_both_arms_panel_contract_dedup_on() -> None:
    for env in (ab.ARM_A_ENV, ab.ARM_B_ENV):
        assert env["NOESIS_EVAL_PANEL"] == "1"
        assert env["NOESIS_PANEL_CONTRACT"] == "1"
        assert env["NOESIS_PANEL_DEDUP"] == "1"
    # A differential OFF, B differential ON
    assert ab.ARM_A_ENV["NOESIS_PANEL_DIFFERENTIAL"] == ""
    assert ab.ARM_B_ENV["NOESIS_PANEL_DIFFERENTIAL"] == "1"
    # arms differ ONLY in the differential knob
    assert {k: v for k, v in ab.ARM_A_ENV.items() if k != "NOESIS_PANEL_DIFFERENTIAL"} == \
           {k: v for k, v in ab.ARM_B_ENV.items() if k != "NOESIS_PANEL_DIFFERENTIAL"}


# --------------------------------------------------------------------- structural metrics
def test_top_dx_coverage_containment() -> None:
    r = _row(top_dx=("acute coronary syndrome (STEMI/NSTEMI/unstable angina)",
                     "aortic dissection", "pericarditis"),
             answer="Most likely acute coronary syndrome; also consider aortic dissection.")
    assert ab.top_dx_coverage(r) == pytest.approx(2 / 3)
    assert ab.top_dx_coverage(_row(top_dx=(), answer="x")) is None


def test_cant_miss_coverage_is_the_safety_metric() -> None:
    r = _row(cant_miss=("acute coronary syndrome", "aortic dissection", "pulmonary embolism"),
             answer="Rule out acute coronary syndrome and pulmonary embolism urgently.")
    assert ab.cant_miss_coverage(r) == pytest.approx(2 / 3)
    assert ab.cant_miss_coverage(_row(cant_miss=(), answer="x")) is None


def test_discriminator_hit_token_overlap() -> None:
    hit = _row(answer="Obtain a 12-lead ECG and serial high-sensitivity troponin now.")
    assert ab.discriminator_hit(hit) is True
    miss = _row(answer="Check a chest X-ray and complete blood count.")
    assert ab.discriminator_hit(miss) is False
    assert ab.discriminator_hit(_row(discriminator="", answer="x")) is None


def test_structural_row_shape() -> None:
    s = ab.structural_row(_row(answer="acute coronary syndrome; 12-lead ECG and troponin"))
    assert set(s) == {"top_dx_coverage", "cant_miss_coverage", "discriminator_hit"}


# ------------------------------------------------------------------ order-consistent winner
def test_consistent_winner_and_sign_test() -> None:
    assert ab.consistent_winner(("A", "B"), "first", "second") == "A"
    assert ab.consistent_winner(("A", "B"), "second", "first") == "B"
    assert ab.consistent_winner(("A", "B"), "first", "first") == "tie"
    assert ab.sign_test_p(0, 0) == 1.0
    assert ab.sign_test_p(0, 10) == pytest.approx(2 / 1024)
