"""Summary tests. Each is named after a way a summary could mislead a clinician."""
from __future__ import annotations

import asyncio

from api.voices.summarize import extractive, summarize, verify

SOURCE = (
    "The trial randomised 4,094 adults with type 2 diabetes and established cardiovascular disease. "
    "Over a median of 3.8 years the primary composite endpoint occurred in 12% of the treatment arm "
    "against 15% of placebo, a hazard ratio of 0.79.\n\n"
    "What matters clinically is that the benefit was concentrated in patients with an eGFR above "
    "forty-five, and the subgroup below thirty was too small to say anything about.\n\n"
    "The authors argue this should change first-line choice for patients who already have vascular "
    "disease, though they are careful to note the trial was industry funded."
)


class _LLM:
    """A stand-in model. `reply` is whatever the model would return."""

    def __init__(self, reply, boom=False):
        self.reply, self.boom = reply, boom

    async def complete(self, **kw):
        if self.boom:
            raise RuntimeError("credit balance exhausted")
        return type("R", (), {"parsed": self.reply})()


def _obj(points, heading="A trial in type 2 diabetes", quotes=None):
    return type("S", (), {"heading": heading, "points": points, "quotes": quotes or []})()


def test_a_figure_the_piece_never_states_is_dropped():
    got = verify(["Reduced events by 30% overall.", "Hazard ratio was 0.79."], SOURCE)
    assert got == ["Hazard ratio was 0.79."]


def test_a_takeaway_with_no_figures_is_kept():
    got = verify(["The benefit was concentrated in less advanced kidney disease."], SOURCE)
    assert len(got) == 1


def test_figures_match_across_formatting():
    assert verify(["Enrolled 4094 adults."], SOURCE) == ["Enrolled 4094 adults."]
    assert verify(["Enrolled 4,094 adults."], SOURCE) == ["Enrolled 4,094 adults."]
    assert verify(["Enrolled 5,000 adults."], SOURCE) == []


def test_a_model_summary_says_it_came_from_a_model():
    out = asyncio.run(summarize(title="T", source=SOURCE,
                                llm=_LLM(_obj(["Hazard ratio was 0.79 over 3.8 years."]))))
    assert out["basis"] == "model" and out["points"]


def test_an_invented_quote_is_not_shown_as_one():
    out = asyncio.run(summarize(title="T", source=SOURCE, llm=_LLM(
        _obj(["Hazard ratio was 0.79."], quotes=["The drug is a miracle.",
                                                 "a hazard ratio of 0.79."]))))
    assert out["quotes"] == ["a hazard ratio of 0.79."]


def test_a_model_outage_degrades_to_the_sources_own_sentences():
    out = asyncio.run(summarize(title="T", source=SOURCE, llm=_LLM(None, boom=True)))
    assert out["basis"] == "extractive" and out["points"]
    flat = " ".join(SOURCE.split())
    for p in out["points"]:
        assert " ".join(p.split()) in flat        # every line is the author's own


def test_with_no_model_at_all_it_still_says_something():
    out = asyncio.run(summarize(title="T", source=SOURCE, llm=None))
    assert out["basis"] == "extractive" and len(out["points"]) >= 2


def test_a_model_that_invents_everything_falls_back_rather_than_shipping_it():
    out = asyncio.run(summarize(title="T", source=SOURCE,
                                llm=_LLM(_obj(["A 30% cut in mortality.", "Enrolled 90,000 people."]))))
    assert out["basis"] == "extractive"           # nothing survived verification


def test_an_empty_piece_returns_nothing_rather_than_inventing_a_summary():
    out = asyncio.run(summarize(title="T", source="   ", llm=None))
    assert out["points"] == [] and out["basis"] == "empty"


def test_extractive_keeps_the_sources_order():
    pts = extractive(SOURCE, n=3)
    assert pts == sorted(pts, key=lambda p: SOURCE.index(p))
