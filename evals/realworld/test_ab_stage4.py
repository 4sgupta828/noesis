"""Offline tests (no network, no LLM) for the stage-4 A/B instrument:
1) the slice file validates (strata counts, unique ids, schema, held-out hygiene);
2) ab_stage4's structural metrics, order-consistency logic, sign test, and summary
   aggregation behave correctly on fixture rows and a scripted judge.

Run: .venv/bin/python -m pytest evals/realworld/test_ab_stage4.py -q
"""
from __future__ import annotations

import asyncio
import importlib.util
import json
import pathlib
import subprocess
import sys

import pytest

HERE = pathlib.Path(__file__).parent
SLICE = HERE / "slices" / "slice-stage4-ab-30-2026-08-14.jsonl"
ACT_SLICE = HERE / "slices" / "slice-act-heldout-5-2026-08-13.jsonl"


def _load_module():
    spec = importlib.util.spec_from_file_location("ab_stage4", HERE / "ab_stage4.py")
    m = importlib.util.module_from_spec(spec)
    sys.modules["ab_stage4"] = m
    spec.loader.exec_module(m)
    return m


ab = _load_module()


def _rows() -> list[dict]:
    return [json.loads(ln) for ln in SLICE.read_text().splitlines() if ln.strip()]


# ------------------------------------------------------------------------ slice validates
def test_slice_strata_counts_and_total() -> None:
    rows = _rows()
    assert len(rows) == 30
    by = {}
    for r in rows:
        by.setdefault(r["stratum"], []).append(r)
    assert len(by["low"]) == 8
    assert len(by["medium"]) == 10
    assert len(by["high"]) == 12


def test_slice_ids_unique_and_patterned() -> None:
    rows = _rows()
    ids = [r["id"] for r in rows]
    assert len(set(ids)) == len(ids)
    tag = {"low": "low", "medium": "med", "high": "high"}
    for r in rows:
        import re
        assert re.fullmatch(rf"s4-{tag[r['stratum']]}-\d{{3}}", r["id"]), r["id"]


def test_slice_schema() -> None:
    for r in _rows():
        assert r["set"] == "stage4_ab"
        assert r["history"] == []
        assert (r["question"] or "").strip()
        g = r["gold"]
        assert g["expected_mode"] in ("exploratory", "enumerative")
        assert isinstance(g["expected_entities"], list)
        assert isinstance(g["expected_axes"], list)
        assert (g["notes"] or "").strip()
        if r["stratum"] == "low":
            assert g["expected_mode"] == "exploratory"
            assert g["expected_entities"] == []
            assert g["expected_axes"] == []
        else:
            assert g["expected_mode"] == "enumerative"
            assert 3 <= len(g["expected_entities"]) <= 6
            assert 2 <= len(g["expected_axes"]) <= 4


def test_slice_excludes_act_heldout_verbatim() -> None:
    def norm(q: str) -> str:
        return " ".join((q or "").lower().split())
    act = {norm(json.loads(ln)["question"]) for ln in ACT_SLICE.read_text().splitlines()
           if ln.strip()}
    for r in _rows():
        assert norm(r["question"]) not in act, r["id"]


# --------------------------------------------------------------------- structural metrics
def _row(gold_mode="enumerative", entities=("beta blocker", "SGLT2", "sacubitril"),
         answer="Beta-blockers and SGLT2 inhibitors reduce mortality.",
         qc=None, claims=(), gaps=()) -> dict:
    return {"id": "x", "stratum": "medium", "question": "q", "answer": answer,
            "gold": {"expected_mode": gold_mode, "expected_entities": list(entities),
                     "expected_axes": ["a", "b"]},
            "question_contract": qc, "claims": list(claims), "coverage_gaps": list(gaps)}


def test_routed_and_covered_entities_from_answer_mode() -> None:
    r = _row(qc={"mode": "steer", "slot_grid": {"x": 1, "y": 0},
                 "answer_mode": {"routed": True, "covered_entities": 2}})
    assert ab.routed(r) is True
    assert ab.covered_entities(r) == 2


def test_covered_entities_falls_back_to_slot_grid() -> None:
    # arm A rows carry no answer_mode (routing flag off) — the slot grid is the source
    r = _row(qc={"mode": "steer", "slot_grid": {"x": 2, "y": 0, "z": 1}})
    assert ab.routed(r) is False
    assert ab.covered_entities(r) == 2
    assert ab.covered_entities(_row(qc=None)) == 0


def test_routing_class_branches() -> None:
    routed_qc = {"answer_mode": {"routed": True, "covered_entities": 3}}
    assert ab.routing_class(_row(gold_mode="enumerative", qc=routed_qc)) == "true_route"
    assert ab.routing_class(_row(gold_mode="exploratory", qc=routed_qc)) == "false_route"
    covered_qc = {"slot_grid": {"x": 1, "y": 1}}
    assert ab.routing_class(_row(gold_mode="enumerative", qc=covered_qc)) == "missed_route"
    # enumerative-gold, not routed, <2 covered → not a miss (nothing to enumerate)
    thin_qc = {"slot_grid": {"x": 1, "y": 0}}
    assert ab.routing_class(_row(gold_mode="enumerative", qc=thin_qc)) == "ok"
    assert ab.routing_class(_row(gold_mode="exploratory", qc=None)) == "ok"


def test_entity_coverage_containment_with_hyphen_normalization() -> None:
    r = _row(answer="Beta-blockers and SGLT2 inhibitors reduce mortality.")
    # 'beta blocker' matches 'Beta-blockers'; 'SGLT2' matches; 'sacubitril' absent → 2/3
    assert ab.entity_coverage(r) == pytest.approx(2 / 3)
    assert ab.entity_coverage(_row(entities=())) is None      # low stratum → excluded


def test_citation_violations() -> None:
    claims = [
        {"text": "Sacubitril/valsartan reduced mortality", "title": "ENTRESTO- sacubitril tablet"},
        {"text": "SGLT2 inhibitors reduce mortality", "title": "Metformin hydrochloride label"},
        {"text": "Unrelated claim naming nothing", "title": "Anything"},
    ]
    v = ab.citation_violations(_row(claims=claims))
    assert len(v) == 1
    assert v[0]["entity"] == "SGLT2"
    assert "Metformin" in v[0]["title"]


def test_declared_gaps() -> None:
    assert ab.declared_gaps(_row(gaps=("No evidence retrieved for x",))) == 1
    assert ab.declared_gaps(_row()) == 0


# ------------------------------------------------------- order-consistent pairwise winner
def test_consistent_winner() -> None:
    # both calls name the same arm → win for it
    assert ab.consistent_winner(("A", "B"), "first", "second") == "A"
    assert ab.consistent_winner(("A", "B"), "second", "first") == "B"
    assert ab.consistent_winner(("B", "A"), "first", "second") == "B"
    # position bias (same POSITION both times → different arms) → tie
    assert ab.consistent_winner(("A", "B"), "first", "first") == "tie"
    # any tie verdict → tie
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
    rows_a = {"q1": {"id": "q1", "stratum": "medium", "question": "Q?", "answer": "ANSWER-A"}}
    rows_b = {"q1": {"id": "q1", "stratum": "medium", "question": "Q?", "answer": "ANSWER-B"}}
    # call 1: 'first' wins with distinct scores; call 2 (flipped): 'second' wins → the arm
    # shown first in call 1 is the order-consistent winner.
    v1 = ab.PairVerdict(better="first", format_fit_first=5, format_fit_second=1,
                        coverage_first=4, coverage_second=2, coherence_first=5,
                        coherence_second=3, honesty_first=4, honesty_second=4)
    v2 = ab.PairVerdict(better="second", format_fit_first=1, format_fit_second=5,
                        coverage_first=2, coverage_second=4, coherence_first=3,
                        coherence_second=5, honesty_first=4, honesty_second=4)
    llm = _ScriptedLLM([v1, v2])
    (j,) = asyncio.run(ab.judge_pairs(llm, rows_a, rows_b, seed=7))
    assert len(llm.calls) == 2
    first_arm = j["order_call1"][0]
    assert j["winner"] == first_arm
    # the answer shown first in call 1 is shown second in call 2 (flip verified via prompts)
    shown = {"A": "ANSWER-A", "B": "ANSWER-B"}
    assert llm.calls[0].index(shown[first_arm]) < llm.calls[0].index(shown[j["order_call1"][1]])
    assert llm.calls[1].index(shown[j["order_call1"][1]]) < llm.calls[1].index(shown[first_arm])
    # dims: winner got 5,4,5,4 in both calls; loser 1,2,3,4 → exact means, mapped per arm
    win, lose = first_arm, j["order_call1"][1]
    assert j["dims"][win] == {"format_fit": 5, "coverage": 4, "coherence": 5, "honesty": 4}
    assert j["dims"][lose] == {"format_fit": 1, "coverage": 2, "coherence": 3, "honesty": 4}


def test_judge_pairs_position_bias_becomes_tie() -> None:
    rows_a = {"q1": {"id": "q1", "stratum": "low", "question": "Q?", "answer": "a"}}
    rows_b = {"q1": {"id": "q1", "stratum": "low", "question": "Q?", "answer": "b"}}
    llm = _ScriptedLLM([ab.PairVerdict(better="first"), ab.PairVerdict(better="first")])
    (j,) = asyncio.run(ab.judge_pairs(llm, rows_a, rows_b, seed=1))
    assert j["winner"] == "tie"


def test_judge_pairs_seed_reproducible() -> None:
    rows_a = {"q1": {"id": "q1", "stratum": "low", "question": "Q?", "answer": "a"}}
    rows_b = {"q1": {"id": "q1", "stratum": "low", "question": "Q?", "answer": "b"}}
    orders = []
    for _ in range(2):
        llm = _ScriptedLLM([ab.PairVerdict(), ab.PairVerdict()])
        (j,) = asyncio.run(ab.judge_pairs(llm, rows_a, rows_b, seed=42))
        orders.append(tuple(j["order_call1"]))
    assert orders[0] == orders[1]


# ------------------------------------------------------------------------------ sign test
def test_sign_test_exact_values() -> None:
    assert ab.sign_test_p(0, 0) == 1.0
    assert ab.sign_test_p(5, 5) == 1.0                       # perfectly split → p clipped to 1
    assert ab.sign_test_p(2, 8) == pytest.approx(112 / 1024)  # 2*(45+10+1)/1024
    assert ab.sign_test_p(8, 2) == pytest.approx(112 / 1024)  # symmetric
    assert ab.sign_test_p(0, 10) == pytest.approx(2 / 1024)
    assert ab.sign_test_p(0, 1) == 1.0


# -------------------------------------------------------------------------------- summary
def test_summarize_aggregates() -> None:
    def mk(qid, stratum, gold_mode, entities, answer, qc):
        r = _row(gold_mode=gold_mode, entities=entities, answer=answer, qc=qc)
        r.update({"id": qid, "stratum": stratum})
        return r

    rows_a = {
        "l1": mk("l1", "low", "exploratory", (), "direct answer", {"slot_grid": {}}),
        "m1": mk("m1", "medium", "enumerative", ("SGLT2", "sacubitril", "lithium"),
                 "SGLT2 only here", {"slot_grid": {"SGLT2": 1, "sacubitril": 1}}),
    }
    rows_b = {
        "l1": mk("l1", "low", "exploratory", (), "direct answer",
                 {"answer_mode": {"routed": True, "covered_entities": 2}}),   # false route
        "m1": mk("m1", "medium", "enumerative", ("SGLT2", "sacubitril", "lithium"),
                 "SGLT2 and sacubitril here",
                 {"answer_mode": {"routed": True, "covered_entities": 2}}),   # true route
    }
    judgments = [
        {"id": "l1", "stratum": "low", "winner": "tie", "order_call1": ["A", "B"],
         "dims": {"A": {d: 3 for d in ab._DIMS}, "B": {d: 3 for d in ab._DIMS}}},
        {"id": "m1", "stratum": "medium", "winner": "B", "order_call1": ["B", "A"],
         "dims": {"A": {d: 3 for d in ab._DIMS}, "B": {d: 4 for d in ab._DIMS}}},
    ]
    s = ab.summarize(rows_a, rows_b, judgments)
    o = s["overall"]
    assert o["n"] == 2 and o["wins_b"] == 1 and o["wins_a"] == 0 and o["ties"] == 1
    assert o["sign_test_p"] == 1.0                            # 1 win vs 0 → n=1 → p=1
    assert o["routing_b"] == {"true": 1, "false": 1, "missed": 0,
                              "precision": 0.5, "recall": 1.0}
    assert o["arm_a_routed_anomaly"] == 0
    # coverage over gold-entity rows only (m1): A=1/3, B=2/3 → delta +0.333
    assert o["entity_coverage"]["a"] == pytest.approx(1 / 3, abs=1e-3)
    assert o["entity_coverage"]["b"] == pytest.approx(2 / 3, abs=1e-3)
    assert o["entity_coverage"]["delta"] == pytest.approx(1 / 3, abs=1e-3)
    assert s["per_stratum"]["medium"]["wins_b"] == 1
    assert s["per_stratum"]["low"]["routing_b"]["false"] == 1
    assert o["dim_delta_b_minus_a"]["coverage"] == pytest.approx(0.5)


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
                            "NOESIS_QUESTION_CONTRACT": "steer",
                            "NOESIS_ANSWER_MODE_ROUTING": ""}
    assert ab.ARM_B_ENV == {**ab.ARM_A_ENV, "NOESIS_ANSWER_MODE_ROUTING": "1"}


def test_spend_gate_refuses_without_confirm() -> None:
    proc = subprocess.run([sys.executable, str(HERE / "ab_stage4.py"),
                           "--slice", str(SLICE)], capture_output=True, text=True)
    assert proc.returncode != 0
    assert "confirm-spend" in (proc.stdout + proc.stderr)
    assert "PROJECTED SPEND" in proc.stdout                   # spend printed before refusal
