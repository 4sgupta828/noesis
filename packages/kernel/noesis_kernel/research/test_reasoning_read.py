"""Reasoning-Read grounding gate: an interpretation item survives ONLY if it (a) is a valid kind,
(b) rests on ≥1 real finding, and (c) introduces no number/dose/date/% absent from its basis findings.
The safety boundary — a fabricated inference (a number the evidence never stated) must never ship."""
from noesis_kernel.research.react import (
    InterpretationItem, VerifiedClaim, _validate_interpretation, extract_hard_tokens,
)

V = [
    VerifiedClaim(text="Drug A had a 53% response rate in the phase 3 trial", atom_id="a1",
                  quote="53% response rate"),
    VerifiedClaim(text="Drug B response was 41% but the study was observational", atom_id="a2",
                  quote="41%"),
    VerifiedClaim(text="Median follow-up was 12 months", atom_id="a3", quote="12 months"),
]


def _item(**kw):
    return InterpretationItem(**kw)


def test_grounded_interpretation_survives():
    items = [_item(text="The two response figures conflict and rest on different study designs",
                   kind="tension", basis_findings=[1, 2])]
    out = _validate_interpretation(items, V)
    assert len(out) == 1 and out[0]["kind"] == "tension" and out[0]["basis_findings"] == [1, 2]


def test_grounded_item_reusing_a_basis_number_survives():
    # 53% appears in finding 1 → allowed to cite it in the interpretation text
    items = [_item(text="A 53% response is only from one trial, limiting confidence",
                   kind="assumption", basis_findings=[1])]
    assert len(_validate_interpretation(items, V)) == 1


def test_fabricated_number_drops_item():
    # 70% appears in NO basis finding → no-new-facts drop
    items = [_item(text="Response could reach 70% in practice", kind="implication", basis_findings=[1])]
    assert _validate_interpretation(items, V) == []


def test_dangling_basis_drops_item():
    items = [_item(text="This is unsupported", kind="gap", basis_findings=[9])]
    assert _validate_interpretation(items, V) == []


def test_no_basis_drops_item():
    items = [_item(text="Floating interpretation", kind="implication", basis_findings=[])]
    assert _validate_interpretation(items, V) == []


def test_invalid_kind_drops_item():
    items = [InterpretationItem.model_construct(text="x", kind="editorial", basis_findings=[1])]
    assert _validate_interpretation(items, V) == []


def test_empty_text_drops_item():
    items = [_item(text="   ", kind="gap", basis_findings=[1])]
    assert _validate_interpretation(items, V) == []


def test_bad_basis_indices_are_clamped_not_fatal():
    # 9 is invalid, 1 is valid → item survives on finding 1, basis normalized to [1]
    items = [_item(text="Rests partly on a real finding", kind="implication", basis_findings=[9, 1])]
    out = _validate_interpretation(items, V)
    assert len(out) == 1 and out[0]["basis_findings"] == [1]


def test_dose_token_grounding():
    v = [VerifiedClaim(text="The regimen used 5 mg daily", atom_id="d", quote="5 mg daily")]
    ok = [_item(text="The 5 mg dose is the only one studied", kind="gap", basis_findings=[1])]
    bad = [_item(text="A 10 mg dose might work better", kind="implication", basis_findings=[1])]
    assert len(_validate_interpretation(ok, v)) == 1
    assert _validate_interpretation(bad, v) == []


def test_empty_is_noop():
    assert _validate_interpretation([], V) == []


def test_extract_hard_tokens_normalizes():
    toks = extract_hard_tokens("53% response, 5 mg dose, on 2026-07-01, and $4.2M")
    assert "53" in toks and "5mg" in toks and "2026-07-01" in toks


def test_extract_hard_tokens_ignores_letter_adjacent_digits():
    # drug/identifier names must NOT yield spurious figure tokens (the prod PCSK9 false-positive)
    toks = extract_hard_tokens("PCSK9 inhibitors, vitamin B12, COVID19, and CoQ10")
    assert toks == set(), toks
    # a real figure next to a name is still caught
    assert "40" in extract_hard_tokens("PCSK9 inhibitors cut LDL by 40%")
