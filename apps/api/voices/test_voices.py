"""Voices search tests. Each is named after a way the surface could mislead.

Everything here is pure: SQL strings and row reshaping, no database.
"""
from __future__ import annotations

import json

from api.voices.search import (
    VOICE_SOURCE_KEYS, build_query, dedupe, moment, terms, tsqueries,
)


# ---- query construction ----

def test_only_voice_sources_are_searched_so_the_evidence_corpus_never_leaks_in():
    sql, params = build_query(tsquery="metformin")
    assert "source_key = ANY($1::text[])" in sql
    assert params[0] == list(VOICE_SOURCE_KEYS)


def test_an_unknown_kind_narrows_to_nothing_rather_than_widening_to_everything():
    sql, params = build_query(tsquery="x", kinds=())
    assert params[0] == list(VOICE_SOURCE_KEYS)
    sql2, params2 = build_query(tsquery="x", kinds=("nonexistent_source",))
    assert params2[0] == ["nonexistent_source"]      # narrowed, not reset to the whole corpus


def test_ranking_is_length_normalised_so_a_long_episode_cannot_bury_a_short_passage():
    sql, _ = build_query(tsquery="sepsis")
    assert "ts_rank(tsv, to_tsquery('english', $2), 1)" in sql   # flag 1 = divide by length


def test_a_browse_with_no_query_orders_by_when_the_episode_published():
    sql, params = build_query(order="recent")
    assert "to_tsquery" not in sql and "tsv @@" not in sql
    assert "(facets ->> 'published_at') DESC" in sql


def test_filters_are_parameterised_never_interpolated():
    sql, params = build_query(tsquery="a", show="Core IM", speaker="Reyes", since="2026-01-01")
    assert "Core IM" not in sql and "Reyes" not in sql and "2026-01-01" not in sql
    assert "Core IM" in params and "reyes" in params and "2026-01-01" in params


def test_furniture_is_excluded_by_length():
    sql, _ = build_query(tsquery="a")
    assert "length(text) > 40" in sql


# ---- the strict-then-relax ladder ----

def test_a_question_is_asked_strictly_before_it_is_relaxed():
    ws = terms("What do experts say about metformin in chronic kidney disease?")
    rungs = tsqueries(ws)
    assert [r[0] for r in rungs] == ["all words", "most words", "any word"]
    assert " & " in rungs[0][1] and " | " in rungs[-1][1]


def test_generic_clinical_words_are_dropped_when_something_specific_survives():
    ws = terms("what do patients think about tirzepatide")
    assert "tirzepatide" in ws
    assert "patients" not in ws and "think" not in ws


def test_a_query_made_only_of_generic_words_still_searches_for_something():
    ws = terms("what do the doctors think about patients")
    assert ws, "a fully generic query must not collapse to nothing"


def test_stopwords_and_short_words_never_reach_the_query():
    ws = terms("is it the of a to")
    assert ws == []
    assert tsqueries([]) == []


# ---- the card ----

ROW = {"document_id": "voices_transcript:ep-1", "block_id": "b7",
       "text": "[00:12:34] SPEAKER_01: The threshold people remember is creatinine, which is wrong.",
       "document_title": "Metformin in CKD", "source_key": "voices_transcript",
       "facets": {"show": "Core IM", "episode_title": "Metformin in CKD", "kind": "podcast",
                  "audio_url": "https://cdn.example/ep1.mp3", "episode_url": "https://show.example/1",
                  "published": "01 Sep 2026", "asr": False},
       "snippet": "«creatinine»"}


def test_a_diarization_label_is_not_shown_as_a_persons_name():
    m = moment(ROW)
    assert m["speaker"] == "" and m["speaker_anonymous"] is True
    named = moment({**ROW, "text": "[00:12:34] Dr Reyes: The threshold people remember is creatinine."})
    assert named["speaker"] == "Dr Reyes" and named["speaker_anonymous"] is False


def test_the_snippet_never_shows_the_timestamp_inside_the_quotation():
    m = moment({**ROW, "snippet": "[00:12:34] SPEAKER_01: the «creatinine» threshold"})
    assert not m["snippet"].startswith("[")
    assert "SPEAKER_01" not in m["snippet"] and "«creatinine»" in m["snippet"]


def test_the_offset_and_speaker_are_read_back_out_of_the_passage_text():
    m = moment(ROW)
    assert m["t_start"] == 754
    assert m["text"].startswith("The threshold")          # metadata is not part of the quote
    assert "[00:12:34]" not in m["text"] and "SPEAKER_01" not in m["text"]


def test_a_moment_deep_links_to_the_second_it_was_said():
    assert moment(ROW)["url"] == "https://cdn.example/ep1.mp3#t=754"


def test_a_podcast_moment_carries_what_to_play_and_from_where():
    m = moment(ROW)
    assert m["media"] == {"kind": "audio", "url": "https://cdn.example/ep1.mp3", "t": 754}


def test_a_video_chapter_plays_as_an_embed_at_its_offset():
    row = {"document_id": "voices_video:abc", "block_id": "b1",
           "text": "[00:12:30] Prerenal vs intrinsic — https://www.youtube.com/watch?v=abc123&t=750s",
           "facets": {"source_kind": "chapter", "kind": "video", "show": "Zero To Finals"},
           "snippet": ""}
    m = moment(row)
    assert m["media"] == {"kind": "youtube", "id": "abc123", "t": 750}
    assert m["quotable"] is False          # a chapter title is the publisher's, never a quotation
    assert m["text"] == "Prerenal vs intrinsic"      # the link is not part of the title


def test_a_chapter_link_never_leaks_into_the_displayed_title():
    row = {"document_id": "voices_video:abc", "block_id": "b1",
           "text": "[00:21:02] Sleep Apnea in PTSD — https://www.youtube.com/watch?v=abc&t=1262s",
           "facets": {"source_kind": "chapter", "kind": "video", "show": "Mayo Clinic"},
           "snippet": "[00:21:02] Sleep «Apnea» in PTSD — https://www.youtube.com/watch?v=abc&t=1262s"}
    m = moment(row)
    assert "http" not in m["text"] and "http" not in m["snippet"]
    assert m["snippet"] == "Sleep «Apnea» in PTSD"


def test_an_essay_has_nothing_to_play():
    row = {"document_id": "voices_essay:1", "block_id": "b1", "text": "A paragraph of argument.",
           "facets": {"source_kind": "essay", "kind": "essay", "show": "Sensible Medicine",
                      "episode_url": "https://blog.example/p/1"}, "snippet": ""}
    m = moment(row)
    assert m["media"] is None and m["url"] == "https://blog.example/p/1"


def test_without_audio_a_moment_falls_back_to_the_episode_page():
    row = {**ROW, "facets": {**ROW["facets"], "audio_url": ""}}
    assert moment(row)["url"] == "https://show.example/1"


def test_a_machine_transcript_is_marked_unquotable_and_says_why():
    row = {**ROW, "facets": {**ROW["facets"], "asr": True}}
    m = moment(row)
    assert m["quotable"] is False
    assert "Machine-generated" in m["register"] and "listen before quoting" in m["register"]
    assert moment(ROW)["quotable"] is True


def test_facets_arriving_as_json_text_are_still_read():
    row = {**ROW, "facets": json.dumps(ROW["facets"])}
    assert moment(row)["show"] == "Core IM"


def test_a_passage_with_no_offset_still_renders():
    row = {**ROW, "text": "A plain paragraph with no timestamp at all."}
    m = moment(row)
    assert m["t_start"] == 0 and m["text"].startswith("A plain paragraph")


# ---- result variety ----

def _m(doc, show, i):
    return {"id": f"{doc}::b{i}", "show": show}


def test_one_talkative_episode_cannot_fill_the_page():
    ms = [_m("ep1", "Core IM", i) for i in range(6)]
    top = dedupe(ms)[:2]
    assert all(m["id"].startswith("ep1") for m in top)
    assert dedupe(ms)[2]["id"] == "ep1::b2"      # the rest spill to the end, nothing is lost
    assert len(dedupe(ms)) == 6


def test_a_thin_result_set_is_not_starved_by_the_caps():
    ms = [_m("ep1", "Core IM", 0), _m("ep2", "Core IM", 0), _m("ep3", "Core IM", 0),
          _m("ep4", "Core IM", 0)]
    out = dedupe(ms, per_episode=1, per_show=2)
    assert len(out) == 4 and {m["id"] for m in out} == {m["id"] for m in ms}
