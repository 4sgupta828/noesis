"""Offline tests (no network, no LLM spend) for the Guided Intake eval harness:
1) the slice file validates (schema, gold shape, urgent/zero-clarification composition);
2) the simulated user is constrained to persona facts (prompt contract) and parses replies;
3) the intake loop terminates at ready, honors endpoint force-ready parity, and stops at the
   backstop cap;
4) structural-metric arithmetic (terms containment, over-ask, urgent flags);
5) judge-output parsing (padding/truncation against gold lists) and the judge's visible context;
6) the spend gate refuses without --confirm-spend (before any env pull / LLM work).

Run: .venv/bin/python -m pytest evals/realworld/test_eval_intake.py -q
"""
from __future__ import annotations

import asyncio
import importlib.util
import json
import pathlib
import sys

import pytest

HERE = pathlib.Path(__file__).parent
SLICE = HERE / "slices" / "slice-intake-12-2026-08-14.jsonl"


def _load_module():
    spec = importlib.util.spec_from_file_location("eval_intake", HERE / "eval_intake.py")
    m = importlib.util.module_from_spec(spec)
    sys.modules["eval_intake"] = m
    spec.loader.exec_module(m)
    return m


ei = _load_module()


# ---------------------------------------------------------------- scripted LLM

class _Comp:
    def __init__(self, parsed):
        self.parsed = parsed


class ScriptedLLM:
    """Mimics the kernel LLMClient.complete contract: returns .parsed pre-built objects in
    order, recording every call for assertions."""

    def __init__(self, replies):
        self.replies = list(replies)
        self.calls = []

    async def complete(self, *, system, messages, response_format, max_tokens=0):
        self.calls.append({"system": system, "messages": messages,
                           "response_format": response_format, "max_tokens": max_tokens})
        return _Comp(self.replies.pop(0))


# ---------------------------------------------------------------- 1) slice validates

def test_slice_schema_and_composition():
    recs = [json.loads(ln) for ln in SLICE.read_text().splitlines() if ln.strip()]
    assert len(recs) == 12
    assert len({r["id"] for r in recs}) == 12
    urgent = zero = 0
    for r in recs:
        assert r["set"] == "intake"
        assert r["question"].strip()
        persona = r["persona"]
        assert isinstance(persona, dict) and 5 <= len(persona) <= 8, r["id"]
        gold = r["gold"]
        cats = gold["clarification_categories"]
        assert isinstance(cats, list) and len(cats) <= 4
        if cats:
            assert 2 <= len(cats) <= 4, r["id"]
        else:
            zero += 1
        assert 2 <= len(gold["expected_terms"]) <= 6, r["id"]
        assert 2 <= len(gold["question_elements"]) <= 5, r["id"]
        assert isinstance(gold["urgent"], bool)
        urgent += 1 if gold["urgent"] else 0
    assert urgent == 2, "exactly 2 mid-conversation-urgent cases"
    assert zero == 2, "exactly 2 zero-clarification fast-converge cases"


def test_slice_urgent_detail_lives_in_persona_not_opening():
    # The urgent red flag must be revealed only when ASKED — never in the opening question.
    recs = [json.loads(ln) for ln in SLICE.read_text().splitlines() if ln.strip()]
    for r in recs:
        if r["gold"]["urgent"]:
            q = r["question"].lower()
            for red in ("chest", "arm", "thunderclap", "worst", "stiff neck"):
                assert red not in q, f"{r['id']}: urgent detail leaked into opening ask"


# ---------------------------------------------------------------- 2) simulated user

def test_simulated_user_prompt_binds_to_persona_only():
    llm = ScriptedLLM([ei._UserReply(reply="She takes the little white pill, Aricept.")])
    persona = {"age": "she is 81", "memory_pill": "Aricept every morning"}
    transcript = [{"role": "user", "text": "my mom's memory pills stopped working"},
                  {"role": "assistant", "text": "What medication does she take?"}]
    out = asyncio.run(ei.simulate_user(llm, persona, transcript))
    assert out == "She takes the little white pill, Aricept."
    call = llm.calls[0]
    sys_p = call["system"]
    # the masquerade contract: persona-only, don't-know, never volunteer, lay register
    assert "ONLY the facts in the PERSONA" in sys_p
    assert "don't know" in sys_p
    assert "NEVER volunteer" in sys_p
    content = call["messages"][0]["content"]
    assert "Aricept every morning" in content            # persona facts visible
    assert "What medication does she take?" in content   # the question being answered
    assert call["response_format"] is ei._UserReply


def test_simulated_user_empty_reply_falls_back():
    llm = ScriptedLLM([ei._UserReply(reply="  ")])
    out = asyncio.run(ei.simulate_user(llm, {"age": "70"},
                                       [{"role": "user", "text": "hi"},
                                        {"role": "assistant", "text": "how old?"}]))
    assert out == "I'm not sure."


# ---------------------------------------------------------------- 3) loop mechanics

def _scripted_triage(turns):
    """triage_fn returning pre-built turn dicts in order; records force_ready flags."""
    seq = list(turns)
    forces = []

    async def fn(transcript, force_ready):
        forces.append(force_ready)
        return seq.pop(0)

    fn.forces = forces
    return fn


async def _echo_user(transcript):
    return "an answer"


def test_loop_terminates_at_ready():
    fn = _scripted_triage([
        {"status": "ask", "message": "Which medication?", "safety": "ok"},
        {"status": "ready", "message": "Running it.", "refined_question": "Q?",
         "understood_problem": "P", "safety": "ok"},
    ])
    res = asyncio.run(ei.run_case(question="my mom is dizzy", triage_fn=fn,
                                  user_fn=_echo_user, max_ask=2))
    assert res["n_asks"] == 1
    assert res["backstop_hit"] is False
    assert res["final"]["status"] == "ready"
    # transcript: opening user + assistant ask + simulated-user answer (ready adds nothing)
    assert [t["role"] for t in res["transcript"]] == ["user", "assistant", "user"]
    assert res["transcript"][2]["text"] == "an answer"
    assert len(res["turns"]) == 2


def test_loop_force_ready_parity_at_max_ask():
    # endpoint parity: force_ready is passed once n_asks reaches TRIAGE_MAX_ASK; a compliant
    # kernel coerces ready on that turn (run_triage_turn sets turn.status = "ready").
    seq = [{"status": "ask", "message": "q1", "safety": "ok"},
           {"status": "ask", "message": "q2", "safety": "ok"}]

    forces = []

    async def fn(transcript, force_ready):
        forces.append(force_ready)
        if force_ready:
            return {"status": "ready", "refined_question": "Q?", "safety": "ok"}
        return seq.pop(0)

    res = asyncio.run(ei.run_case(question="opening", triage_fn=fn,
                                  user_fn=_echo_user, max_ask=2))
    assert forces == [False, False, True]
    assert res["n_asks"] == 2
    assert res["backstop_hit"] is False
    assert res["final"]["status"] == "ready"


def test_loop_backstop_cap():
    # a triage that ignores force_ready and asks forever must stop at the backstop
    async def fn(transcript, force_ready):
        return {"status": "ask", "message": "again?", "safety": "ok"}

    res = asyncio.run(ei.run_case(question="opening", triage_fn=fn,
                                  user_fn=_echo_user, max_ask=2, backstop=8))
    assert res["backstop_hit"] is True
    assert len(res["turns"]) == 8
    assert res["n_asks"] == 8


# ---------------------------------------------------------------- 4) structural metrics

def test_structural_metrics_arithmetic():
    case = {"gold": {"clarification_categories": ["current-medications"],
                     "expected_terms": ["Donepezil", "Alzheimer", "amlodipine"],
                     "question_elements": ["e1"], "urgent": True}}
    result = {"n_asks": 2, "backstop_hit": False,
              "turns": [{"status": "ask", "safety": "ok"},
                        {"status": "ask", "safety": "urgent"},
                        {"status": "ready", "safety": "ok"}],
              "final": {"refined_question":
                        "In an 81-year-old on donepezil for Alzheimer disease, what causes dizziness?"}}
    s = ei.structural_metrics(case, result)
    assert s["n_asks"] == 2
    assert s["refined_nonempty"] is True
    assert s["terms_present"] == pytest.approx(2 / 3, abs=1e-3)   # case-insensitive containment
    assert s["urgent_gold"] is True
    assert s["urgent_fired"] is True                              # ANY turn counts
    assert s["urgent_correct"] is True
    assert s["zero_clarification_case"] is False
    assert s["over_ask"] is False


def test_structural_metrics_over_ask_and_empty_refined():
    case = {"gold": {"clarification_categories": [], "expected_terms": ["metformin"],
                     "question_elements": ["e1"], "urgent": False}}
    result = {"n_asks": 1, "backstop_hit": False,
              "turns": [{"status": "ask", "safety": "ok"}, {"status": "ready", "safety": "ok"}],
              "final": {"refined_question": "   "}}
    s = ei.structural_metrics(case, result)
    assert s["zero_clarification_case"] is True
    assert s["over_ask"] is True             # asked on a fast-converge case = the failure
    assert s["refined_nonempty"] is False
    assert s["terms_present"] == 0.0
    assert s["urgent_fired"] is False and s["urgent_correct"] is True


def test_structural_metrics_no_terms_is_none_not_zero():
    case = {"gold": {"clarification_categories": ["c"], "expected_terms": [],
                     "question_elements": [], "urgent": False}}
    result = {"n_asks": 0, "backstop_hit": False, "turns": [{"status": "ready", "safety": "ok"}],
              "final": {"refined_question": "Q?"}}
    assert ei.structural_metrics(case, result)["terms_present"] is None


# ---------------------------------------------------------------- 5) judge parsing

def test_judged_metrics_pads_and_truncates():
    gold = {"clarification_categories": ["a", "b", "c"], "question_elements": ["x", "y", "z"]}
    j = ei.IntakeJudgment(categories_hit=[True],                    # short → pad False
                          elements_captured=[True, True, True, True],  # long → truncate
                          confabulation=True, confabulation_note="invented a dose",
                          boundary_violation=False)
    m = ei.judged_metrics(j, gold)
    assert m["category_hit"] == pytest.approx(1 / 3, abs=1e-3)
    assert m["elements_captured"] == 1.0
    assert m["confabulation"] is True and m["confabulation_note"] == "invented a dose"
    assert m["boundary_violation"] is False


def test_judged_metrics_empty_gold_lists_are_none():
    m = ei.judged_metrics(ei.IntakeJudgment(), {"clarification_categories": [],
                                                "question_elements": []})
    assert m["category_hit"] is None and m["elements_captured"] is None


def test_judge_case_builds_context_and_parses():
    verdict = ei.IntakeJudgment(categories_hit=[True, False], elements_captured=[True],
                                boundary_violation=True, boundary_note="gave advice")
    llm = ScriptedLLM([verdict])
    case = {"question": "my mom is dizzy", "persona": {"age": "81"},
            "gold": {"clarification_categories": ["current-medications", "symptom-onset-duration"],
                     "question_elements": ["81-year-old"], "expected_terms": [], "urgent": False}}
    result = {"transcript": [{"role": "user", "text": "my mom is dizzy"},
                             {"role": "assistant", "text": "Which meds does she take?"},
                             {"role": "user", "text": "Aricept"}],
              "turns": [{"status": "ask", "message": "Which meds does she take?"},
                        {"status": "ready", "message": "ok", "refined_question": "RQ?",
                         "understood_problem": "UP"}],
              "final": {"refined_question": "RQ?", "understood_problem": "UP"}}
    out = asyncio.run(ei.judge_case(llm, case, result))
    assert out is verdict
    content = llm.calls[0]["messages"][0]["content"]
    for needle in ('"age": "81"', "my mom is dizzy", "Which meds does she take?", "RQ?", "UP",
                   "[0] current-medications", "[1] symptom-onset-duration", "[0] 81-year-old"):
        assert needle in content
    assert llm.calls[0]["response_format"] is ei.IntakeJudgment


# ---------------------------------------------------------------- aggregate sanity

def test_aggregate_rates():
    def mk(i, *, cat, terms, elems, confab, bound, zero, over, urg_gold, urg_fired, asks):
        return {"id": f"in-{i}",
                "structural": {"n_asks": asks, "backstop_hit": False, "refined_nonempty": True,
                               "terms_present": terms, "urgent_gold": urg_gold,
                               "urgent_fired": urg_fired,
                               "urgent_correct": urg_gold == urg_fired,
                               "zero_clarification_case": zero, "over_ask": over},
                "judged": {"category_hit": cat, "elements_captured": elems,
                           "confabulation": confab, "confabulation_note": "",
                           "boundary_violation": bound, "boundary_note": ""}}
    cases = [
        mk(1, cat=1.0, terms=0.5, elems=1.0, confab=False, bound=False, zero=False,
           over=False, urg_gold=True, urg_fired=True, asks=2),
        mk(2, cat=0.0, terms=1.0, elems=0.5, confab=True, bound=True, zero=False,
           over=False, urg_gold=True, urg_fired=False, asks=1),
        mk(3, cat=None, terms=1.0, elems=1.0, confab=False, bound=False, zero=True,
           over=True, urg_gold=False, urg_fired=False, asks=1),
        {"id": "in-4", "error": "boom"},
    ]
    s = ei.aggregate(cases)
    assert s["cases"] == 4 and s["errors"] == 1
    assert s["mean_category_hit"] == 0.5          # None excluded from the mean
    assert s["mean_terms_present"] == pytest.approx(2.5 / 3, abs=1e-3)
    assert s["confabulation_rate"] == pytest.approx(1 / 3, abs=1e-3)
    assert s["boundary_violation_rate"] == pytest.approx(1 / 3, abs=1e-3)
    assert s["over_ask_rate_zero_clarification"] == 1.0   # only the zero-clarification case
    assert s["urgent_detection"] == 0.5                   # 1 of 2 gold-urgent fired
    assert s["false_urgent_rate"] == 0.0
    assert s["mean_n_asks"] == pytest.approx(4 / 3, abs=1e-3)


# ---------------------------------------------------------------- 6) spend gate

def test_spend_gate_refuses_without_confirm(tmp_path, monkeypatch):
    p = tmp_path / "s.jsonl"
    p.write_text(json.dumps({"id": "in-x", "set": "intake", "question": "q",
                             "persona": {}, "gold": {}}) + "\n")
    # the gate must fire BEFORE any Railway env pull or service build
    monkeypatch.setattr(ei, "_prod_env",
                        lambda: (_ for _ in ()).throw(AssertionError("env pulled before gate")))
    with pytest.raises(SystemExit, match="confirm-spend"):
        ei.main(["--slice", str(p)])


def test_arm_flag_accepts_v1_and_v2_only(tmp_path):
    p = tmp_path / "s.jsonl"
    p.write_text(json.dumps({"id": "in-x", "set": "intake", "question": "q",
                             "persona": {}, "gold": {}}) + "\n")
    with pytest.raises(SystemExit):        # argparse rejects unknown arm
        ei.main(["--slice", str(p), "--arm", "v3", "--confirm-spend"])


def test_select_prompt_v2_falls_back_to_v1(capsys):
    v1, sha1, used1 = ei._select_prompt("v1")
    assert used1 == "v1" and v1 and len(sha1) == 12
    v2, sha2, used2 = ei._select_prompt("v2")
    out = capsys.readouterr().out
    if used2 == "v1":                      # v2 prompt hasn't landed → wired fallback + warning
        assert "falling back" in out and v2 == v1 and sha2 == sha1
    else:                                  # once v2 lands this arm becomes real
        assert used2 == "v2" and sha2 != sha1
