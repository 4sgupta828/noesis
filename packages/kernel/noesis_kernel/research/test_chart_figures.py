from noesis_kernel.research.react import _fig_in, _norm_fig


def test_figure_matching_ignores_dash_style_and_spacing():
    # the same NUMBER typed differently still counts as grounded
    assert _fig_in("−14.9%", "weight change was -14.9% at 68 weeks")   # unicode minus
    assert _fig_in("-14.9%", "weight change was −14.9% at 68 weeks")
    assert _fig_in("1.7 kg", "gained 1.7kg over the period")               # spacing
    assert _fig_in("1.7kg", "gained 1.7 kg over the period")
    assert _fig_in("22 %", "reduced events by 22%")
    assert _fig_in("0.85", "HR 0.85 (95% CI 0.79-0.92)")
    assert _fig_in("0.72–0.90", "95% CI 0.72-0.90")                    # en dash range


def test_figure_matching_still_rejects_a_different_number():
    assert not _fig_in("0.86", "HR 0.85 (95% CI 0.79-0.92)")
    assert not _fig_in("31%", "reduced events by 22%")
    assert not _fig_in("", "anything")
    assert _norm_fig("  A  B−C ") == "a b-c"
