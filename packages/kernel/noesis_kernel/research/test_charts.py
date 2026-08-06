"""Chart grounding gate: a bar survives ONLY if its value_str appears in its cited finding; any bad
bar drops the WHOLE chart (fail-safe). This is the safety boundary — a fabricated bar must never ship."""
from noesis_kernel.research.react import ChartPoint, ChartSpec, VerifiedClaim, _validate_charts

# Two verified findings with figures in their text/quote.
V = [
    VerifiedClaim(text="Drug A had a 53% response rate", atom_id="a1", quote="53% response rate"),
    VerifiedClaim(text="Drug B response was 41%", atom_id="a2", quote="41%"),
]


def _chart(points, title="Response"):
    return ChartSpec(title=title, unit="%", points=[ChartPoint(**p) for p in points])


def test_fully_grounded_chart_survives():
    ch = _chart([{"label": "Drug A", "value": 53, "value_str": "53%", "finding": 1},
                 {"label": "Drug B", "value": 41, "value_str": "41%", "finding": 2}])
    out = _validate_charts([ch], V)
    assert len(out) == 1 and len(out[0]["points"]) == 2


def test_one_ungrounded_bar_drops_the_whole_chart():
    # 88% appears in NO finding → the entire chart is dropped, not just the bar.
    ch = _chart([{"label": "Drug A", "value": 53, "value_str": "53%", "finding": 1},
                 {"label": "Drug C", "value": 88, "value_str": "88%", "finding": 2}])
    assert _validate_charts([ch], V) == []


def test_bad_finding_index_drops_chart():
    ch = _chart([{"label": "Drug A", "value": 53, "value_str": "53%", "finding": 1},
                 {"label": "Drug B", "value": 41, "value_str": "41%", "finding": 9}])  # no finding 9
    assert _validate_charts([ch], V) == []


def test_value_str_must_be_present_verbatim():
    # value 53 is right but value_str "0.53" is NOT in the finding text → dropped.
    ch = _chart([{"label": "Drug A", "value": 53, "value_str": "0.53", "finding": 1},
                 {"label": "Drug B", "value": 41, "value_str": "41%", "finding": 2}])
    assert _validate_charts([ch], V) == []


def test_single_bar_is_not_a_chart():
    ch = _chart([{"label": "Drug A", "value": 53, "value_str": "53%", "finding": 1}])
    assert _validate_charts([ch], V) == []


def test_empty_is_noop():
    assert _validate_charts([], V) == []


def test_case_insensitive_match():
    v = [VerifiedClaim(text="Incidence was 12 MG per day", atom_id="a", quote="12 MG"),
         VerifiedClaim(text="the other was 8 mg", atom_id="b", quote="8 mg")]
    ch = _chart([{"label": "X", "value": 12, "value_str": "12 mg", "finding": 1},
                 {"label": "Y", "value": 8, "value_str": "8 MG", "finding": 2}], title="Dose")
    assert len(_validate_charts([ch], v)) == 1
