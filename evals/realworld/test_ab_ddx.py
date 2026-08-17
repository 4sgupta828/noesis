"""Offline tests (no network, no LLM) for the DDx / clinical-decision A/B instrument:
1) the DDx slice file validates (15 records, unique/patterned ids, gold schema, held-out hygiene);
2) ab_ddx's structural metrics, order-consistency logic, sign test, and summary aggregation
   behave correctly on fixture rows and a scripted judge.

Run: .venv/bin/python -m pytest evals/realworld/test_ab_ddx.py -q
"""
from __future__ import annotations

import asyncio
import importlib.util
import json
import pathlib
import re
import subprocess
import sys

import pytest

HERE = pathlib.Path(__file__).parent
SLICE = HERE / "slices" / "slice-ddx-clinical-15-2026-08-17.jsonl"


def _load_module():
    spec = importlib.util.spec_from_file_location("ab_ddx", HERE / "ab_ddx.py")
    m = importlib.util.module_from_spec(spec)
    sys.modules["ab_ddx"] = m
    spec.loader.exec_module(m)
    return m


ab = _load_module()


def _rows() -> list[dict]:
    return [json.loads(ln) for ln in SLICE.read_text().splitlines() if ln.strip()]


# ------------------------------------------------------------------------ slice validates
def test_slice_loads_15_records() -> None:
    assert len(_rows()) == 15


def test_slice_ids_unique_and_patterned() -> None:
    rows = _rows()
    ids = [r["id"] for r in rows]
    assert len(set(ids)) == len(ids)
    for r in rows:
        assert re.fullmatch(r"ddx-\d{3}-[a-z0-9-]+", r["id"]), r["id"]


def test_slice_schema_and_gold_keys() -> None:
    for r in _rows():
        assert r["set"] == "ddx_clinical"
        assert r["history"] == []
        assert (r["question"] or "").strip()
        assert (r["stratum"] or "").strip()
        g = r["gold"]
        for key in ("top_dx", "cant_miss", "discriminator", "threshold"):
            assert key in g, (r["id"], key)
        assert isinstance(g["top_dx"], list) and g["top_dx"]
        assert isinstance(g["cant_miss"], list) and g["cant_miss"]
        assert isinstance(g["discriminator"], str) and g["discriminator"].strip()
        assert isinstance(g["threshold"], str) and g["threshold"].strip()


def test_ddx_questions_held_out_from_other_slices() -> None:
    """No DDx vignette question is verbatim-present in any OTHER slices/*.jsonl file — the eval
    must measure generalization, not memorization (Rule 5)."""
    def norm(q: str) -> str:
        return " ".join((q or "").lower().split())

    ddx = {norm(r["question"]) for r in _rows()}
    other: set[str] = set()
    for path in (HERE / "slices").glob("*.jsonl"):
        if path.name == SLICE.name:
            continue
        for ln in path.read_text().splitlines():
            if not ln.strip():
                continue
            try:
                rec = json.loads(ln)
            except json.JSONDecodeError:
                continue
            q = rec.get("question")
            if isinstance(q, str):
                other.add(norm(q))
    leaked = ddx & other
    assert not leaked, f"DDx questions leaked into other slices: {leaked}"


# --------------------------------------------------------------------- structural metrics
def _row(top_dx=("acute coronary syndrome (STEMI/NSTEMI/unstable angina)",),
         cant_miss=("acute coronary syndrome", "aortic dissection", "pulmonary embolism"),
         discriminator="12-lead ECG immediately plus serial high-sensitivity troponin",
         answer="", stratum="cardiac") -> dict:
    return {"id": "x", "stratum": stratum, "question": "q", "answer": answer,
            "gold": {"top_dx": list(top_dx), "cant_miss": list(cant_miss),
                     "discriminator": discriminator, "threshold": "ST-elevation -> reperfusion"}}


def test_key_term_strips_qualifiers() -> None:
    assert ab._key_term("heart failure (HFrEF or HFpEF)") == "heart failure"
    assert ab._key_term("acute coronary syndrome / ischemic cardiomyopathy") == "acute coronary syndrome"
    assert ab._key_term("pancreatic head adenocarcinoma") == "pancreatic head adenocarcinoma"


def test_top_dx_coverage_containment() -> None:
    r = _row(top_dx=("acute coronary syndrome (STEMI/NSTEMI/unstable angina)",
                     "aortic dissection", "pericarditis"),
             answer="Most likely acute coronary syndrome; also consider aortic dissection.")
    # ACS and aortic dissection present, pericarditis absent → 2/3
    assert r  # sanity
    assert ab.top_dx_coverage(r) == pytest.approx(2 / 3)
    assert ab.top_dx_coverage(_row(top_dx=(), answer="x")) is None


def test_cant_miss_coverage_is_the_safety_metric() -> None:
    r = _row(cant_miss=("acute coronary syndrome", "aortic dissection", "pulmonary embolism"),
             answer="Rule out acute coronary syndrome and pulmonary embolism urgently.")
    # ACS and PE surfaced, aortic dissection missed → 2/3
    assert ab.cant_miss_coverage(r) == pytest.approx(2 / 3)
    assert ab.cant_miss_coverage(_row(cant_miss=(), answer="x")) is None


def test_discriminator_hit_token_overlap() -> None:
    # discriminator sig tokens ~ {12, lead, ecg, sensitivity, troponin}; answer names ECG + troponin
    hit = _row(answer="Obtain a 12-lead ECG and serial high-sensitivity troponin now.")
    assert ab.discriminator_hit(hit) is True
    miss = _row(answer="Check a chest X-ray and complete blood count.")
    assert ab.discriminator_hit(miss) is False
    assert ab.discriminator_hit(_row(discriminator="", answer="x")) is None


def test_has_word_is_whole_word() -> None:
    assert ab._has_word("ct", "obtain a ct head") is True
    assert ab._has_word("ct", "octreotide infusion") is False


def test_structural_row_shape() -> None:
    s = ab.structural_row(_row(answer="acute coronary syndrome; 12-lead ECG and troponin"))
    assert set(s) == {"top_dx_coverage", "cant_miss_coverage", "discriminator_hit"}


# ------------------------------------------------------- order-consistent pairwise winner
def test_consistent_winner() -> None:
    assert ab.consistent_winner(("A", "B"), "first", "second") == "A"
    assert ab.consistent_winner(("A", "B"), "second", "first") == "B"
    assert ab.consistent_winner(("B", "A"), "first", "second") == "B"
    # position bias (same POSITION both times → different arms) → tie
    assert ab.consistent_winner(("A", "B"), "first", "first") == "tie"
    assert ab.consistent_winner(("A", "B"), "tie", "second") == "tie"
    assert ab.consistent_winner(("A", "B"), "first", "tie") == "tie"
    assert ab.consistent_winner(("A", "B"), "tie", "tie") == "tie"


class _ScriptedLLM:
    """Returns queued PairVerdicts in call order; records the prompts it saw."""

    def __init__(self, verdicts):
        self.verdicts = list(verdicts)
        self.calls: list[str] = []

    async def complete(self, system, messages, response_format, max_tokens=0):
        self.calls.append(messages[0]["content"])
        v = self.verdicts.pop(0)

        class _C:
            parsed = v
        return _C()


def test_judge_pairs_maps_orders_and_averages_dims() -> None:
    rows_a = {"q1": {"id": "q1", "stratum": "cardiac", "question": "Q?", "answer": "ANSWER-A"}}
    rows_b = {"q1": {"id": "q1", "stratum": "cardiac", "question": "Q?", "answer": "ANSWER-B"}}
    v1 = ab.PairVerdict(better="first", differential_quality_first=5, differential_quality_second=1,
                        decision_framework_first=4, decision_framework_second=2,
                        evidence_first=5, evidence_second=3, honesty_first=4, honesty_second=4)
    v2 = ab.PairVerdict(better="second", differential_quality_first=1, differential_quality_second=5,
                        decision_framework_first=2, decision_framework_second=4,
                        evidence_first=3, evidence_second=5, honesty_first=4, honesty_second=4)
    llm = _ScriptedLLM([v1, v2])
    (j,) = asyncio.run(ab.judge_pairs(llm, rows_a, rows_b, seed=7))
    assert len(llm.calls) == 2
    first_arm = j["order_call1"][0]
    assert j["winner"] == first_arm
    shown = {"A": "ANSWER-A", "B": "ANSWER-B"}
    assert llm.calls[0].index(shown[first_arm]) < llm.calls[0].index(shown[j["order_call1"][1]])
    assert llm.calls[1].index(shown[j["order_call1"][1]]) < llm.calls[1].index(shown[first_arm])
    win, lose = first_arm, j["order_call1"][1]
    assert j["dims"][win] == {"differential_quality": 5, "decision_framework": 4,
                              "evidence": 5, "honesty": 4}
    assert j["dims"][lose] == {"differential_quality": 1, "decision_framework": 2,
                               "evidence": 3, "honesty": 4}


def test_judge_pairs_position_bias_becomes_tie() -> None:
    rows_a = {"q1": {"id": "q1", "stratum": "cardiac", "question": "Q?", "answer": "a"}}
    rows_b = {"q1": {"id": "q1", "stratum": "cardiac", "question": "Q?", "answer": "b"}}
    llm = _ScriptedLLM([ab.PairVerdict(better="first"), ab.PairVerdict(better="first")])
    (j,) = asyncio.run(ab.judge_pairs(llm, rows_a, rows_b, seed=1))
    assert j["winner"] == "tie"


def test_judge_pairs_seed_reproducible() -> None:
    rows_a = {"q1": {"id": "q1", "stratum": "cardiac", "question": "Q?", "answer": "a"}}
    rows_b = {"q1": {"id": "q1", "stratum": "cardiac", "question": "Q?", "answer": "b"}}
    orders = []
    for _ in range(2):
        llm = _ScriptedLLM([ab.PairVerdict(), ab.PairVerdict()])
        (j,) = asyncio.run(ab.judge_pairs(llm, rows_a, rows_b, seed=42))
        orders.append(tuple(j["order_call1"]))
    assert orders[0] == orders[1]


# ------------------------------------------------------------------------------ sign test
def test_sign_test_exact_values() -> None:
    assert ab.sign_test_p(0, 0) == 1.0
    assert ab.sign_test_p(5, 5) == 1.0
    assert ab.sign_test_p(2, 8) == pytest.approx(112 / 1024)
    assert ab.sign_test_p(8, 2) == pytest.approx(112 / 1024)
    assert ab.sign_test_p(0, 10) == pytest.approx(2 / 1024)
    assert ab.sign_test_p(0, 1) == 1.0


# -------------------------------------------------------------------------------- summary
def test_summarize_aggregates() -> None:
    def mk(qid, stratum, answer):
        r = _row(top_dx=("acute coronary syndrome (STEMI)", "aortic dissection", "pericarditis"),
                 cant_miss=("acute coronary syndrome", "aortic dissection", "pulmonary embolism"),
                 answer=answer, stratum=stratum)
        r["id"] = qid
        return r

    # arm A surfaces 1 top_dx + 1 can't-miss; arm B surfaces 2 top_dx + 2 can't-miss (B better)
    rows_a = {
        "c1": mk("c1", "cardiac", "consider acute coronary syndrome"),
        "n1": mk("n1", "neurologic", "consider acute coronary syndrome"),
    }
    rows_b = {
        "c1": mk("c1", "cardiac", "acute coronary syndrome and aortic dissection; 12-lead ECG, troponin"),
        "n1": mk("n1", "neurologic", "acute coronary syndrome and pulmonary embolism"),
    }
    judgments = [
        {"id": "c1", "stratum": "cardiac", "winner": "B", "order_call1": ["A", "B"],
         "dims": {"A": {d: 3 for d in ab._DIMS}, "B": {d: 4 for d in ab._DIMS}}},
        {"id": "n1", "stratum": "neurologic", "winner": "tie", "order_call1": ["B", "A"],
         "dims": {"A": {d: 3 for d in ab._DIMS}, "B": {d: 3 for d in ab._DIMS}}},
    ]
    s = ab.summarize(rows_a, rows_b, judgments)
    o = s["overall"]
    assert o["n"] == 2 and o["wins_b"] == 1 and o["wins_a"] == 0 and o["ties"] == 1
    assert o["sign_test_p"] == 1.0                         # 1 win vs 0 → n=1 → p=1
    # top_dx coverage: A=1/3 both rows; B = mean(2/3 for c1, 1/3 for n1) = 0.5 → delta +0.167
    assert o["top_dx_coverage"]["a"] == pytest.approx(1 / 3, abs=1e-3)
    assert o["top_dx_coverage"]["b"] == pytest.approx(0.5, abs=1e-3)
    assert o["top_dx_coverage"]["delta"] == pytest.approx(0.167, abs=1e-3)
    # can't-miss coverage (safety): A=1/3 both rows; B = mean(2/3 for c1, 2/3 for n1) = 2/3
    assert o["cant_miss_coverage"]["a"] == pytest.approx(1 / 3, abs=1e-3)
    assert o["cant_miss_coverage"]["b"] == pytest.approx(2 / 3, abs=1e-3)
    # discriminator hit-rate: only c1-B names ECG+troponin → A=0/2, B=1/2
    assert o["discriminator_hit"]["a"] == pytest.approx(0.0)
    assert o["discriminator_hit"]["b"] == pytest.approx(0.5)
    assert o["dim_delta_b_minus_a"]["differential_quality"] == pytest.approx(0.5)
    assert set(s["per_stratum"]) == {"cardiac", "neurologic"}
    assert s["per_stratum"]["cardiac"]["wins_b"] == 1


def test_load_run_rows_filters_unhealthy(tmp_path) -> None:
    p = tmp_path / "run.jsonl"
    p.write_text("\n".join(json.dumps(r) for r in [
        {"id": "a", "answer": "ok answer"},
        {"id": "b", "error": "Boom: x"},
        {"id": "c", "answer": "   "},
    ]))
    assert set(ab.load_run_rows(p)) == {"a"}


# ------------------------------------------------------------------------------ arm setup
def test_arm_envs() -> None:
    assert ab.ARM_A_ENV == {"NOESIS_EVIDENCE_IDENTITY": "1", "NOESIS_CLAIM_CONGRUENCE": "1",
                            "NOESIS_QUESTION_CONTRACT": "steer", "NOESIS_EVAL_REASONED": "1",
                            "NOESIS_DIFFERENTIAL_FORMAT": ""}
    assert ab.ARM_B_ENV == {**ab.ARM_A_ENV, "NOESIS_DIFFERENTIAL_FORMAT": "1"}
    # both arms reasoned; A differential OFF, B differential ON; both set the flag explicitly
    assert ab.ARM_A_ENV["NOESIS_EVAL_REASONED"] == ab.ARM_B_ENV["NOESIS_EVAL_REASONED"] == "1"
    assert ab.ARM_A_ENV["NOESIS_DIFFERENTIAL_FORMAT"] == ""
    assert ab.ARM_B_ENV["NOESIS_DIFFERENTIAL_FORMAT"] == "1"


def test_spend_gate_refuses_without_confirm() -> None:
    proc = subprocess.run([sys.executable, str(HERE / "ab_ddx.py"),
                           "--slice", str(SLICE)], capture_output=True, text=True)
    assert proc.returncode != 0
    assert "confirm-spend" in (proc.stdout + proc.stderr)
    assert "PROJECTED SPEND" in proc.stdout                 # spend printed before refusal
