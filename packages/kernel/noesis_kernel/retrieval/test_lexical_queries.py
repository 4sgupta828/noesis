"""Lexical-leg query shaping (pure function; the prod long-pole fix). No DB."""
from __future__ import annotations

from noesis_kernel.retrieval.postgres import _lexical_queries
from noesis_kernel.retrieval.scoring import tokens


def test_strict_is_and_of_content_terms_numbers_dropped() -> None:
    strict, relaxed = _lexical_queries(tokens("metformin dose adjustment eGFR 30-45"))
    assert strict == "metformin & dose & adjustment & egfr"
    assert "30" not in strict and "45" not in strict
    # relaxed = every pair of content terms, OR'ed — still index-driven, never a single common term
    assert relaxed == ("(metformin & dose) | (metformin & adjustment) | (metformin & egfr) | "
                       "(dose & adjustment) | (dose & egfr) | (adjustment & egfr)")


def test_function_words_and_duplicates_filtered() -> None:
    strict, relaxed = _lexical_queries(tokens("What is the recommended metformin dose for metformin"))
    assert strict == "recommended & metformin & dose"
    assert "what" not in relaxed and "the" not in relaxed


def test_single_term_has_no_relaxed_leg() -> None:
    assert _lexical_queries(["metformin"]) == ("metformin", "")


def test_numbers_only_fall_back_to_raw_terms() -> None:
    strict, relaxed = _lexical_queries(["30", "45"])
    assert strict == "30 & 45" and relaxed == "(30 & 45)"


def test_empty() -> None:
    assert _lexical_queries([]) == ("", "")
