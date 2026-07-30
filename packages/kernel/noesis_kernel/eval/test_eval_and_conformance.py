"""Offline tests for the lookup scorer + conformance runner."""
from __future__ import annotations

from noesis_kernel.contract.manifest import VerticalManifest
from noesis_kernel.conformance.runner import run_conformance
from noesis_kernel.eval.lookup_scoring import score_lookup
from noesis_kernel.eval.schema import EmittedRow, ExpectedRow, LookupCase, LookupTrace


def _case() -> LookupCase:
    return LookupCase(
        id="roe_two_utils",
        category="C1",
        expected_rows=(
            ExpectedRow(row_key={"entity": "A"}, cells={"roe": "9.8%", "rate_base": "$1,200"}),
            ExpectedRow(row_key={"entity": "B"}, cells={"roe": "10.10%"}),
        ),
    )


def test_loose_numeric_match_and_full_credit() -> None:
    trace = LookupTrace(case_id="roe_two_utils", rows=[
        EmittedRow(row_key={"entity": "A"}, cells={"roe": "9.80", "rate_base": "1200"}),
        EmittedRow(row_key={"entity": "B"}, cells={"roe": "10.1"}),
    ])
    s = score_lookup(_case(), trace)
    assert s.matched_rows == 2
    assert s.cell_accuracy == 1.0
    assert s.fully_correct


def test_wrong_adjacent_row_value_loses_credit() -> None:
    # Adversarial trap: B's value placed on A's row.
    trace = LookupTrace(case_id="roe_two_utils", rows=[
        EmittedRow(row_key={"entity": "A"}, cells={"roe": "10.10%", "rate_base": "$1,200"}),
        EmittedRow(row_key={"entity": "B"}, cells={"roe": "10.10%"}),
    ])
    s = score_lookup(_case(), trace)
    assert not s.fully_correct
    assert s.cell_accuracy < 1.0  # A.roe wrong


def test_strict_column_rejects_rounding() -> None:
    case = LookupCase(
        id="strict", expected_rows=(
            ExpectedRow(row_key={"entity": "A"}, cells={"amt": "189.80"}),
        ),
        strict_columns=frozenset({"amt"}),
    )
    # 189.8 != 189.80 under strict literal match.
    trace = LookupTrace(case_id="strict", rows=[EmittedRow(row_key={"entity": "A"}, cells={"amt": "189.8"})])
    assert not score_lookup(case, trace).fully_correct


def test_missing_row_no_credit() -> None:
    trace = LookupTrace(case_id="roe_two_utils", rows=[
        EmittedRow(row_key={"entity": "A"}, cells={"roe": "9.8%", "rate_base": "$1,200"}),
    ])
    s = score_lookup(_case(), trace)
    assert s.matched_rows == 1 and not s.fully_correct


def test_conformance_partial_manifest_ok_at_p0_fails_at_p3() -> None:
    m = VerticalManifest(name="regulatory")
    assert run_conformance(m, phase="P0").ok           # only name required at P0
    rep3 = run_conformance(m, phase="P3")
    assert not rep3.ok                                  # entity/scope/persona/gold missing
    names_failed = {r.name for r in rep3.results if not r.passed and not r.skipped}
    assert "entity-taxonomy-declared" in names_failed


def test_conformance_full_manifest_passes_p3() -> None:
    m = VerticalManifest(
        name="regulatory",
        entity_types=("case", "filing"),
        scope_dimensions=("jurisdiction",),
        gating_policy=object(),
        persona=object(),
        authority_policy=object(),
        eval_gold={"lookup": ["case1"]},
    )
    assert run_conformance(m, phase="P3").ok
