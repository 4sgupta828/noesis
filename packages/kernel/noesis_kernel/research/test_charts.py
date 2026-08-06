"""Chart grounding gate: every plotted number (value + CI bounds) must appear in its cited finding, or
the whole chart is dropped (fail-safe). The safety boundary — a fabricated bar must never ship."""
from noesis_kernel.research.react import ChartBar, ChartSpec, VerifiedClaim, _validate_charts

V = [
    VerifiedClaim(text="Drug A had a 53% response rate", atom_id="a1", quote="53% response rate"),
    VerifiedClaim(text="Drug B response was 41%", atom_id="a2", quote="41%"),
    VerifiedClaim(text="HR 0.78 (95% CI 0.65-0.94) for the primary outcome", atom_id="a3",
                  quote="HR 0.78 (95% CI 0.65-0.94)"),
    VerifiedClaim(text="the comparator HR was 0.91 (95% CI 0.80 to 1.05)", atom_id="a4",
                  quote="0.91 (95% CI 0.80 to 1.05)"),
]


def _bar(**kw):
    return ChartBar(**kw)


def test_grounded_bar_chart_survives():
    ch = ChartSpec(kind="bar", title="Response", unit="%", bars=[
        _bar(label="Drug A", value=53, value_str="53%", finding=1),
        _bar(label="Drug B", value=41, value_str="41%", finding=2)])
    out = _validate_charts([ch], V)
    assert len(out) == 1 and out[0]["kind"] == "bar" and len(out[0]["bars"]) == 2


def test_one_ungrounded_bar_drops_the_whole_chart():
    ch = ChartSpec(bars=[_bar(label="A", value=53, value_str="53%", finding=1),
                         _bar(label="C", value=88, value_str="88%", finding=2)])  # 88% in no finding
    assert _validate_charts([ch], V) == []


def test_bad_finding_index_drops_chart():
    ch = ChartSpec(bars=[_bar(label="A", value=53, value_str="53%", finding=1),
                         _bar(label="B", value=41, value_str="41%", finding=9)])
    assert _validate_charts([ch], V) == []


def test_interval_chart_requires_grounded_bounds():
    # both estimate AND CI bounds present verbatim → survives
    ch = ChartSpec(kind="interval", title="HR", bars=[
        _bar(label="Trial 1", value=0.78, value_str="0.78", low=0.65, low_str="0.65",
             high=0.94, high_str="0.94", finding=3),
        _bar(label="Trial 2", value=0.91, value_str="0.91", low=0.80, low_str="0.80",
             high=1.05, high_str="1.05", finding=4)])
    assert len(_validate_charts([ch], V)) == 1


def test_interval_with_fabricated_ci_bound_drops_chart():
    ch = ChartSpec(kind="interval", bars=[
        _bar(label="Trial 1", value=0.78, value_str="0.78", low=0.65, low_str="0.65",
             high=0.99, high_str="0.99", finding=3),   # 0.99 not in finding 3
        _bar(label="Trial 2", value=0.91, value_str="0.91", finding=4)])
    assert _validate_charts([ch], V) == []


def test_grouped_bar_all_values_grounded():
    v = [VerifiedClaim(text="Drug A: response 53%, serious AE 7%", atom_id="a", quote="response 53%, serious AE 7%"),
         VerifiedClaim(text="Drug B: response 41%, serious AE 3%", atom_id="b", quote="response 41%, serious AE 3%")]
    ch = ChartSpec(kind="grouped_bar", title="Benefit vs risk", unit="%", bars=[
        _bar(label="Drug A", series="Response", value=53, value_str="53%", finding=1),
        _bar(label="Drug A", series="Serious AE", value=7, value_str="7%", finding=1),
        _bar(label="Drug B", series="Response", value=41, value_str="41%", finding=2),
        _bar(label="Drug B", series="Serious AE", value=3, value_str="3%", finding=2)])
    assert len(_validate_charts([ch], v)) == 1


def test_single_group_is_not_a_chart():
    ch = ChartSpec(bars=[_bar(label="A", value=53, value_str="53%", finding=1)])
    assert _validate_charts([ch], V) == []


def test_empty_is_noop():
    assert _validate_charts([], V) == []
