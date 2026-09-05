"""Lexical candidate planner (pure; document-frequency driven). No DB."""
from __future__ import annotations

from noesis_kernel.retrieval.postgres import _parse_pg_text_array, plan_lexical

# document frequencies as pg_stats would report them (fraction of blocks); absent = rare
DF = {"patient": 0.19, "risk": 0.074, "dose": 0.052, "30": 0.030, "pain": 0.028, "guidelin": 0.022,
      "adjust": 0.016, "45": 0.009, "chest": 0.02}


def test_rare_terms_select_common_terms_only_rank() -> None:
    plans, rank = plan_lexical(["metformin", "dose", "adjust", "egfr", "30", "45"], DF)
    assert plans == ["metformin & egfr", "metformin | egfr"]       # rare terms drive selection
    assert rank == "metformin | dose | adjust | egfr | 30 | 45"    # every term shapes the ranking


def test_all_common_query_intersects_never_a_single_common_term() -> None:
    plans, _ = plan_lexical(["chest", "pain", "guidelin", "risk"], DF)
    assert plans[0] == "chest & pain & guidelin & risk"
    assert plans[1] == "chest & guidelin"                           # two least-common terms
    assert all("|" not in p for p in plans)


def test_single_rare_term_has_one_plan() -> None:
    assert plan_lexical(["troponin"], DF) == (["troponin"], "troponin")


def test_dedup_and_empty() -> None:
    assert plan_lexical(["egfr", "egfr"], DF) == (["egfr"], "egfr")
    assert plan_lexical([], DF) == ([], "")


def test_parse_pg_text_array() -> None:
    assert _parse_pg_text_array('{a,b,"c d","q\\"x"}') == ["a", "b", "c d", 'q"x']
    assert _parse_pg_text_array("{}") == [] and _parse_pg_text_array(None) == []
