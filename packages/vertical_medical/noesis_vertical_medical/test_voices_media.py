"""Video-chapter and essay leg tests. No test touches the network."""
from __future__ import annotations

import asyncio

from noesis_vertical_medical.voices_media import (
    ExpertEssayConnector, YouTubeChapterConnector, chapters_markdown, essay_text, looks_like_prose,
    parse_chapters,
)

DESC = """In this video we cover acute kidney injury from first principles.

0:00 Introduction
1:45 Definitions and staging
12:30 Prerenal vs intrinsic
25:05 Management priorities

Subscribe at https://example.com/join
"""


def test_a_chapter_list_is_read_in_order_with_its_offsets():
    chs = parse_chapters(DESC)
    assert [t for t, _ in chs] == [0, 105, 750, 1505]
    assert chs[1][1] == "Definitions and staging"
    assert not any(t.lower().startswith("http") for _, t in chs)   # links are not chapters


def test_a_single_stray_timestamp_in_prose_is_not_a_chapter_list():
    assert parse_chapters("We discussed this at 12:30 in the last episode, worth a listen.") == []
    assert parse_chapters("0:00 Intro\n1:00 Next") == []           # two is not a run


def test_each_chapter_becomes_its_own_deep_linked_block():
    md = chapters_markdown(parse_chapters(DESC), "https://www.youtube.com/watch?v=abc")
    paras = [p for p in md.split("\n\n") if p.strip()]
    assert len(paras) == 4
    assert paras[2].startswith("[00:12:30] Prerenal vs intrinsic")
    assert paras[2].endswith("watch?v=abc&t=750s")


YT = """<?xml version="1.0"?>
<feed xmlns="http://www.w3.org/2005/Atom" xmlns:yt="http://www.youtube.com/xml/schemas/2015"
      xmlns:media="http://search.yahoo.com/mrss/">
 <entry>
   <yt:videoId>abc123</yt:videoId><title>Acute Kidney Injury</title>
   <published>2026-08-01T10:00:00+00:00</published>
   <media:group>
     <media:description>0:00 Introduction
1:45 Definitions and staging
12:30 Prerenal vs intrinsic</media:description>
     <media:thumbnail url="https://i.ytimg.com/vi/abc123/hq.jpg"/>
   </media:group>
 </entry>
 <entry>
   <yt:videoId>zzz999</yt:videoId><title>No chapters here</title>
   <media:group><media:description>Just a plain description with no chapter list.</media:description></media:group>
 </entry>
</feed>"""


def test_a_video_without_chapters_is_skipped_because_there_is_no_text_to_index():
    c = YouTubeChapterConnector({"Test": "UC123"}, fetch=lambda u: YT.encode())
    docs = asyncio.run(c.list_documents(asyncio.run(c.discover_entities({}))[0]))
    assert [d.title for d in docs] == ["Acute Kidney Injury"]
    assert docs[0].facets["kind"] == "video" and docs[0].facets["source_kind"] == "chapter"
    assert docs[0].facets["art"].endswith("hq.jpg")
    assert docs[0].facets["episode_url"] == "https://www.youtube.com/watch?v=abc123"


def test_the_video_artifact_is_one_chapter_per_paragraph():
    c = YouTubeChapterConnector({"Test": "UC123"}, fetch=lambda u: YT.encode())
    doc = asyncio.run(c.list_documents(asyncio.run(c.discover_entities({}))[0]))[0]
    md = asyncio.run(c.fetch_artifact(doc)).decode()
    assert len([p for p in md.split("\n\n") if p.strip()]) == 3
    assert doc.facets["passages"] == 3 and doc.facets["duration_s"] == 750
    assert "description" not in doc.facets            # the raw blob does not ride into the corpus


# ---- essays ----

PROSE1 = ("The trial randomised just over four thousand adults and reported a hazard ratio of 0.79 for "
          "the primary composite endpoint, which is a larger effect than most of us expected given "
          "the earlier observational work in this population.")
PROSE2 = ("What matters clinically is whether that difference survives adjustment for baseline renal "
          "function, because the subgroup with an eGFR below thirty was small and the confidence "
          "interval there crosses one by a wide margin.")
PROSE3 = ("None of this settles the question for an individual patient in front of you, but it does "
          "change how much weight the guideline committee can put on a single trial when the "
          "replication attempt is still running and the populations differ so much.")
CODE = ("unpack &lt;- function (par) { list ( mu = par[ 1 ], sigma = exp (par[ 2 ]), "
        "theta = if ( length (par) &gt; 2 ) par[ 3 : length (par)] else numeric ( 0 )) }")

RSS = """<?xml version="1.0"?><rss xmlns:content="http://purl.org/rss/1.0/modules/content/"><channel>
 <item><title>What the trial actually showed</title><link>https://blog.example/p/1</link>
  <pubDate>Mon, 01 Sep 2026 09:00:00 GMT</pubDate>
  <content:encoded><![CDATA[<p>%s</p><pre><code>%s</code></pre><p>%s</p><p>%s</p><p>Subscribe</p>]]></content:encoded></item>
 <item><title>Teaser only</title><link>https://blog.example/p/2</link>
  <description>Read the rest at our site.</description></item>
 <item><title>A recorded talk</title><link>https://blog.example/talk/bthink/</link>
  <content:encoded><![CDATA[<p>%s</p><p>%s</p><p>%s</p>]]></content:encoded></item>
</channel></rss>""" % (PROSE1, CODE, PROSE2, PROSE3, PROSE1, PROSE2, PROSE3)


def _essays(feeds=None):
    return ExpertEssayConnector(feeds or {"https://f/x": ("Dr Writer", "The Blog", "", "")},
                                fetch=lambda u: RSS.encode())


def test_a_teaser_is_not_an_essay():
    c = _essays()
    docs = asyncio.run(c.list_documents(asyncio.run(c.discover_entities({}))[0]))
    assert "Teaser only" not in [d.title for d in docs]
    assert docs[0].facets["writer"] == "Dr Writer" and docs[0].facets["kind"] == "essay"


def test_source_code_is_never_shipped_as_writing():
    # the exact shape that reached production: R source, tag-stripped into "par[ 1 ]"
    assert essay_text(f"<p>{PROSE1}</p><pre><code>{CODE}</code></pre>") == PROSE1
    assert not looks_like_prose("unpack <- function (par) { list ( mu = par[ 1 ], sigma = exp (par[ 2 ]) ) }")
    assert looks_like_prose(PROSE1)


def test_inline_tags_do_not_insert_spaces_inside_words():
    out = essay_text(f"<p>The <em>eGFR</em> threshold is thirty. {PROSE2}</p>")
    assert "The eGFR threshold" in out and "e GFR" not in out


def test_a_site_wide_feed_is_filtered_to_posts_so_a_link_is_never_a_talk_page():
    c = _essays({"https://f/x": ("Dr Writer", "The Blog", "/p/", "")})
    docs = asyncio.run(c.list_documents(asyncio.run(c.discover_entities({}))[0]))
    assert [d.facets["episode_url"] for d in docs] == ["https://blog.example/p/1"]
    assert all("/talk/" not in d.facets["episode_url"] for d in docs)


def test_paid_placement_and_podcast_pages_are_excluded_by_path():
    rss = RSS.replace("https://blog.example/p/2", "https://blog.example/sponsored-article/x")
    c = ExpertEssayConnector({"https://f/x": ("W", "B", "", "/sponsored-article/,/podcastc/")},
                             fetch=lambda u: rss.encode())
    docs = asyncio.run(c.list_documents(asyncio.run(c.discover_entities({}))[0]))
    assert all("sponsored" not in d.facets["episode_url"] for d in docs)


def test_a_paragraph_left_full_of_holes_by_stripped_maths_is_dropped():
    # what Harrell's posts become once inline maths is removed
    broken = ("Consider a continuous, discrete, or mixed-type random variable having a cumulative "
              "distribution function . The empirical cumulative distribution function is the "
              "nonparametric maximum likelihood estimator of , and it is defined for all values of .")
    assert not looks_like_prose(broken)
    assert looks_like_prose(PROSE2)


def test_an_item_without_a_resolvable_link_is_dropped():
    rss = RSS.replace("<link>https://blog.example/p/1</link>", "<link></link>")
    c = ExpertEssayConnector({"https://f/x": ("W", "B", "", "")}, fetch=lambda u: rss.encode())
    docs = asyncio.run(c.list_documents(asyncio.run(c.discover_entities({}))[0]))
    assert all(d.facets["episode_url"].startswith("http") for d in docs)


def test_navigation_fragments_are_dropped_and_paragraphs_survive():
    txt = essay_text(f"<p>{PROSE1}</p><p>Subscribe</p><p>{PROSE2}</p>")
    paras = [p for p in txt.split("\n\n") if p.strip()]
    assert len(paras) == 2 and "Subscribe" not in txt


def test_html_entities_are_decoded_so_a_quote_reads_as_written():
    out = essay_text("<p>" + PROSE1 + " The author didn&#8217;t stop there.</p>")
    assert "didn\u2019t stop there" in out and "&#8217;" not in out


def test_a_dead_essay_feed_is_skipped_rather_than_failing_the_sweep():
    def boom(u):
        raise OSError("down")
    c = ExpertEssayConnector({"https://f/x": ("A", "B", "", "")}, fetch=boom)
    assert asyncio.run(c.list_documents(asyncio.run(c.discover_entities({}))[0])) == []
