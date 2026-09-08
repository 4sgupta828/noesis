"""Transcript-leg tests. Each is named after a way the leg could lie about what was said."""
from __future__ import annotations

import asyncio

from noesis_vertical_medical.voices_transcript import (
    PodcastTranscriptConnector, episode_markdown, hhmmss, parse_cues, plain_passages, to_passages,
)

VTT = """WEBVTT
Kind: captions
Language: en

1
00:00:02.000 --> 00:00:06.500
[SPEAKER_00]: Welcome back to the show. Today we are talking about metformin in chronic kidney disease, which comes up on rounds constantly and which almost everyone gets slightly wrong.

2
00:00:06.500 --> 00:00:11.000
[SPEAKER_00]: The label changed in 2016 and a lot of us have not caught up with it, so we are still quoting a creatinine cutoff that has not been the guidance for years now.

3
00:01:04.250 --> 00:01:09.000
[SPEAKER_01]: Right, and the threshold people remember is creatinine, which is the wrong number to be anchoring on when you are deciding whether this patient can stay on the drug at all.

4
00:01:09.000 --> 00:01:14.000
[SPEAKER_01]: It is eGFR thirty that matters, not a creatinine cutoff, and between thirty and forty-five you reduce the dose rather than stopping outright.
"""

SRT = """1
00:00:01,000 --> 00:00:04,000
This is an AI generated transcript and may contain errors.

2
00:00:04,000 --> 00:00:09,000
The trial reported a hazard ratio of zero point eight for the primary endpoint.
"""


def test_cues_parse_from_vtt_and_srt_alike():
    v = parse_cues(VTT)
    assert len(v) == 4 and v[0][0] == 2 and v[2][0] == 64
    assert "metformin" in v[0][1]
    s = parse_cues(SRT)
    assert len(s) == 2 and s[1][0] == 4
    # structure is not speech
    assert not any(t.strip().isdigit() or t.startswith("WEBVTT") for _, t in v)


def test_a_passage_breaks_on_a_speaker_change_and_keeps_its_offset():
    ps = to_passages(parse_cues(VTT))
    assert len(ps) == 2, [p.text for p in ps]
    assert ps[0].speaker == "SPEAKER_00" and ps[0].start == 2
    assert ps[1].speaker == "SPEAKER_01" and ps[1].start == 64
    # the speaker tag is metadata, not part of the quote
    assert "[SPEAKER_00]" not in ps[0].text
    assert "label changed in 2016" in ps[0].text


def test_a_fast_exchange_is_not_shredded_into_meaningless_turns():
    """A dialogue that changes speaker every sentence produced 19-word cards like "Yeah, that's a
    tough job" — true, but gibberish on its own. Turns keep running until they carry substance."""
    cues = [(i * 4, f"[SPEAKER_0{i % 2}]: Short reply number {i}.") for i in range(12)]
    ps = to_passages(cues)
    assert len(ps) <= 3, [p.text for p in ps]
    assert all(len(p.text) >= 40 for p in ps)


def test_a_passage_ends_where_a_thought_ends():
    """Breaking on length alone produced cards starting mid-clause — "in patients, we will still
    pherese" — which read as incoherent however relevant they were."""
    cues = []
    for i in range(30):
        cues.append((i * 6, "This clause runs on and on without stopping for quite a while indeed"))
        cues.append((i * 6 + 3, "and then it finally reaches its end."))
    ps = to_passages(cues, target_chars=200)
    assert len(ps) > 3
    assert all(p.text.rstrip().endswith((".", "!", "?")) for p in ps), [p.text[-40:] for p in ps]


def test_a_passage_never_exceeds_the_hard_cap_even_without_punctuation():
    cues = [(i * 5, "no punctuation here at all just words running on") for i in range(80)]
    ps = to_passages(cues, target_chars=300, max_chars=900)
    assert ps and all(len(p.text) <= 1000 for p in ps)


def test_studio_furniture_never_reaches_the_surface():
    from noesis_vertical_medical.voices_transcript import is_speech
    assert not is_speech("BTK Episode 2 take 3 - Audio Processed-esv2-50p-bg-10p-music-10p ===")
    assert not is_speech("Yeah.")
    assert not is_speech("Thanks for having us here!")
    assert is_speech("The label changed in 2016 and most of us are still quoting a creatinine cutoff.")


def test_a_long_single_speaker_stretch_is_split_rather_than_left_unquotable():
    cues = [(i * 5, f"Sentence number {i} about anticoagulation in atrial fibrillation and renal impairment.")
            for i in range(40)]
    ps = to_passages(cues, target_chars=400)
    assert len(ps) > 4
    assert all(len(p.text) <= 1400 for p in ps)
    assert [p.start for p in ps] == sorted(p.start for p in ps)   # offsets stay in order


def test_markdown_is_one_paragraph_per_passage_so_each_becomes_its_own_block():
    md = episode_markdown(to_passages(parse_cues(VTT)))
    paras = [p for p in md.split("\n\n") if p.strip()]
    assert len(paras) == 2
    assert paras[0].startswith("[00:00:02] SPEAKER_00: ")
    assert paras[1].startswith("[00:01:04] ")
    assert hhmmss(3671) == "01:01:11"


def test_an_uncued_transcript_keeps_its_paragraphs_rather_than_merging_them():
    ps = plain_passages("Dr Reyes: First paragraph of a plain transcript.\n\nSecond paragraph here.")
    assert len(ps) == 2 and all(p.start == 0 for p in ps)
    assert ps[0].speaker == "Dr Reyes" and ps[0].text.startswith("First paragraph")
    assert ps[1].speaker == "" and ps[1].text == "Second paragraph here."


# ---- connector: fetching is injected, so no test touches the network ----

FEED = """<?xml version="1.0"?>
<rss xmlns:podcast="https://podcastindex.org/namespace/1.0">
 <channel>
  <item>
    <title>Metformin in CKD</title><link>https://show.example/ep/1</link>
    <guid>ep-1</guid><pubDate>Mon, 01 Sep 2026 09:00:00 GMT</pubDate>
    <enclosure url="https://cdn.example/ep1.mp3" type="audio/mpeg"/>
    <podcast:transcript url="https://cdn.example/ep1.vtt" type="text/vtt"/>
  </item>
  <item>
    <title>No transcript here</title><guid>ep-2</guid>
    <enclosure url="https://cdn.example/ep2.mp3" type="audio/mpeg"/>
  </item>
 </channel>
</rss>"""


def _conn(pages: dict):
    return PodcastTranscriptConnector({"Test Show": "https://feed.example/rss"},
                                      fetch=lambda u: pages[u].encode("utf-8"))


def test_an_episode_without_a_transcript_is_skipped_entirely():
    c = _conn({"https://feed.example/rss": FEED})
    docs = asyncio.run(c.list_documents(
        asyncio.run(c.discover_entities({}))[0]))
    assert [d.title for d in docs] == ["Metformin in CKD"]
    assert docs[0].facets["source_kind"] == "transcript"
    assert docs[0].facets["audio_url"] == "https://cdn.example/ep1.mp3"
    assert docs[0].facets["episode_url"] == "https://show.example/ep/1"
    assert docs[0].facets["show"] == "Test Show"


def test_the_artifact_is_offset_prefixed_speech():
    c = _conn({"https://feed.example/rss": FEED, "https://cdn.example/ep1.vtt": VTT})
    doc = asyncio.run(c.list_documents(asyncio.run(c.discover_entities({}))[0]))[0]
    md = asyncio.run(c.fetch_artifact(doc)).decode()
    assert md.count("\n\n") == 1 and md.startswith("[00:00:02]")
    assert doc.facets["passages"] == 2 and doc.facets["duration_s"] == 69
    assert doc.facets["asr"] is False


def test_a_machine_written_transcript_is_flagged_so_it_is_never_shown_as_verbatim():
    feed = FEED.replace('type="text/vtt"', 'type="application/srt"').replace("ep1.vtt", "ep1.srt")
    c = _conn({"https://feed.example/rss": feed, "https://cdn.example/ep1.srt": SRT})
    doc = asyncio.run(c.list_documents(asyncio.run(c.discover_entities({}))[0]))[0]
    asyncio.run(c.fetch_artifact(doc))
    assert doc.facets["asr"] is True


def test_a_dead_feed_is_skipped_rather_than_failing_the_sweep():
    def boom(url):
        raise OSError("network is down")
    c = PodcastTranscriptConnector({"Dead": "https://nope.example/rss"}, fetch=boom)
    assert asyncio.run(c.list_documents(asyncio.run(c.discover_entities({}))[0])) == []


def test_a_cued_transcript_is_preferred_over_an_uncued_one():
    feed = FEED.replace(
        '<podcast:transcript url="https://cdn.example/ep1.vtt" type="text/vtt"/>',
        '<podcast:transcript url="https://cdn.example/ep1.txt" type="text/plain"/>'
        '<podcast:transcript url="https://cdn.example/ep1.vtt" type="text/vtt"/>')
    c = _conn({"https://feed.example/rss": feed})
    doc = asyncio.run(c.list_documents(asyncio.run(c.discover_entities({}))[0]))[0]
    assert doc.facets["transcript_url"].endswith(".vtt")
