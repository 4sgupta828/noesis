"""Two more Voices legs: chaptered clinical VIDEO, and first-person expert ESSAYS.

Both are COMMENTARY, like the transcript leg, and carry `source_kind` values the manifest declares
non-evidence, so nothing here can reach a grounded answer.

WHY THESE TWO SHAPES. Measured 2026-09-08 across 33 YouTube channels and 19 expert blogs:

  video   — YouTube publishes no captions without a signed token, so a video is reachable only when
            the creator writes a CHAPTER LIST in the description. 8 of 33 channels do. A chapter is
            publisher-written, so it says WHERE to watch, never what was said: `quotable=False`.
  essay   — 13 of 19 clinical blogs ship FULL TEXT in RSS (median 4,900–21,000 chars). An essay is
            the author's own words, so it is quotable and attributed.

CURATION IS EDITORIAL, NOT MECHANICAL. Several channels that clear the chapter bar are career vlogs
or wellness commerce rather than clinical content, and a high chapter rate says nothing about whether
a clinician should hear it. The rosters below are filtered for a clinical audience — teaching from
clinicians, institutional medicine, and expert analysis — and each entry says why it is here.
"""
from __future__ import annotations

import re
import urllib.request
import xml.etree.ElementTree as ET

from .voices_transcript import _UA, _Ref, hhmmss

# ---------------------------------------------------------------- video (chapters)

# 33 channels probed; these clear 40% chaptered AND are clinical material. Deliberately excluded
# despite clearing the chapter bar: career/lifestyle vlogs (medical-school advice, day-in-the-life)
# and wellness-commerce channels whose claims run against mainstream evidence — a high chapter rate
# is a fetchability fact, not a quality one.
VOICE_CHANNELS: dict[str, str] = {
    "Rhesus Medicine": "UCRks8wB6vgz0E7buP0L_5RQ",      # 100% chaptered — clinical teaching
    "Dirty Medicine": "UCZaDAUF7UEcRXIFvGZu3O9Q",       # 87% — pharmacology / pathophysiology
    "Ninja Nerd": "UC6QYFutt9cluQ3uSM963_KQ",           # 60% — physiology and pathophysiology
    "Zero To Finals": "UCwZEjeak8ychtv2Unng5W2A",       # 53% — clinical medicine teaching
    "Mayo Clinic": "UC8fQzKHIhSoZeSq3bwQx4mw",          # 53% — institutional clinical explainers
}

_YT_FEED = "https://www.youtube.com/feeds/videos.xml?channel_id={cid}"
# a chapter line: "12:34 Title" or "(1:02:03) Title", at the start of a line
_CHAPTER = re.compile(r"^\s*[\(\[]?(?P<t>(?:\d{1,2}:)?\d{1,2}:\d{2})[\)\]]?[\s\-–—:.]*(?P<title>.{3,90}?)\s*$",
                      re.M)


def _secs(ts: str) -> int:
    parts = [int(x) for x in ts.split(":")]
    while len(parts) < 3:
        parts.insert(0, 0)
    return parts[0] * 3600 + parts[1] * 60 + parts[2]


def parse_chapters(description: str) -> list[tuple[int, str]]:
    """(second, chapter title) from a video description, in order.

    Requires a RUN of at least three, so a single stray timestamp in prose ("we covered this at
    12:30") is not mistaken for a chapter list.
    """
    found = [(_secs(m.group("t")), " ".join(m.group("title").split()))
             for m in _CHAPTER.finditer(description or "")]
    found = [(t, ti) for t, ti in found if ti and not ti.lower().startswith(("http", "www."))]
    return found if len(found) >= 3 else []


def chapters_markdown(chs: list[tuple[int, str]], video_url: str) -> str:
    """One paragraph per chapter, so the kernel splitter yields one block each."""
    return "\n\n".join(f"[{hhmmss(t)}] {title} — {video_url}&t={t}s" for t, title in chs)


class YouTubeChapterConnector:
    """Chaptered clinical video. A chapter is a POINTER, never a quotation."""

    key = "voices_video"
    fetch_strategy = "poll"

    def __init__(self, channels: dict[str, str] | None = None, *, fetch=None, timeout: int = 30,
                 max_videos: int = 12):
        self._channels = dict(channels or VOICE_CHANNELS)
        self._timeout = timeout
        self._max = max_videos
        self._fetch = fetch or self._http

    def _http(self, url: str) -> bytes:
        return urllib.request.urlopen(urllib.request.Request(url, headers=_UA),
                                      timeout=self._timeout).read()

    async def discover_entities(self, window: dict) -> list[_Ref]:
        return [_Ref(source_key=self.key, native_id=cid, title=name, facets={"show": name})
                for name, cid in self._channels.items()]

    async def list_documents(self, entity: _Ref) -> list[_Ref]:
        try:
            root = ET.fromstring(self._fetch(_YT_FEED.format(cid=entity.native_id)))
        except Exception:      # noqa: BLE001
            return []
        docs: list[_Ref] = []
        for e in [x for x in root.iter() if x.tag.split("}")[-1] == "entry"]:
            vid, title, published, desc, thumb = "", "", "", "", ""
            for el in e.iter():
                tag = el.tag.split("}")[-1]
                if tag == "videoId":
                    vid = (el.text or "").strip()
                elif tag == "title" and not title:
                    title = (el.text or "").strip()
                elif tag == "published":
                    published = (el.text or "").strip()
                elif tag == "description" and el.text and len(el.text) > len(desc):
                    desc = el.text
                elif tag == "thumbnail" and el.get("url"):
                    thumb = el.get("url") or ""
            if not vid or not parse_chapters(desc):
                continue           # no chapter list, no way in — captions need a signed token
            docs.append(_Ref(
                source_key=self.key, native_id=vid, title=title,
                facets={"source_kind": "chapter", "kind": "video", "show": entity.title,
                        "episode_title": title, "episode_url": f"https://www.youtube.com/watch?v={vid}",
                        "video_id": vid, "art": thumb, "published": published, "description": desc},
                dates={"published": published}))
            if len(docs) >= max(1, int(self._max)):
                break
        return docs

    async def fetch_artifact(self, doc: _Ref) -> bytes:
        chs = parse_chapters(doc.facets.pop("description", ""))
        doc.facets["passages"] = len(chs)
        doc.facets["duration_s"] = chs[-1][0] if chs else 0
        url = doc.facets.get("episode_url") or ""
        return chapters_markdown(chs, url).encode("utf-8")


# ---------------------------------------------------------------- essays (full text)

# 19 blogs probed, 13 ship full text; these are the clinically-relevant ones — practising clinicians,
# methodologists and research analysts writing under their own name.
# feed url: (writer, publication, path the item link must contain)
# The path filter is load-bearing: fharrell.com/index.xml is a SITE-wide feed whose recent items are
# 9 talk pages and 11 posts, so without it an "essay" card links to a page whose content is a video.
VOICE_ESSAYS: dict[str, tuple[str, str, str]] = {
    "https://erictopol.substack.com/feed": ("Eric Topol", "Ground Truths", "/p/"),
    "https://www.sensible-med.com/feed": ("Sensible Medicine", "evidence and clinical practice", "/p/"),
    "https://insidemedicine.substack.com/feed": ("Jeremy Faust", "Inside Medicine", "/p/"),
    "https://yourlocalepidemiologist.substack.com/feed":
        ("Katelyn Jetelina", "Your Local Epidemiologist", "/p/"),
    "https://www.fharrell.com/index.xml": ("Frank Harrell", "statistical thinking", "/post/"),
    "https://www.science.org/blogs/pipeline/feed": ("Derek Lowe", "In the Pipeline", ""),
    "https://absolutelymaybe.plos.org/feed/": ("Hilda Bastian", "Absolutely Maybe", ""),
    "https://bodyofevidence.substack.com/feed": ("The Body of Evidence", "clinical evidence", "/p/"),
    "https://cancerletter.com/feed/": ("The Cancer Letter", "oncology research and policy", ""),
}

_TAGS = re.compile(r"<[^>]+>")
_WS = re.compile(r"[ \t ]+")
# whole blocks that are never prose: source listings, output, figures, tables, markup furniture
_DROP_BLOCKS = re.compile(
    r"(?is)<(pre|code|script|style|table|figure|figcaption|svg|noscript)\b.*?</\1\s*>")
_BLOCK_END = re.compile(r"(?i)</(p|div|li|h[1-6]|blockquote|tr)\s*>|<br\s*/?>")
_ENTITIES = (("&nbsp;", " "), ("&#160;", " "), ("&amp;", "&"), ("&lt;", "<"), ("&gt;", ">"),
             ("&#8217;", "’"), ("&#8216;", "‘"), ("&quot;", '"'), ("&#8220;", "“"),
             ("&#8221;", "”"), ("&#8212;", "—"), ("&#8211;", "–"), ("&#39;", "'"))
# a line of code survives tag-stripping; this is what code looks like once the tags are gone
_CODEY = re.compile(r"(<-\s|=>|\bfunction\s*\(|\}\s*$|;\s*$|^\s*[#$>]\s|::|\w+\(\)|"
                    r"\[\s*\d+\s*\]|\bdef\s+\w+\(|</?\w+>)")


def looks_like_prose(p: str) -> bool:
    """Is this paragraph an ARGUMENT, or a code listing / caption / navigation fragment?

    Half of Frank Harrell's posts are R source, and stripping tags turns `unpack <- function(par)`
    into something that passes a length check but reads as nonsense to a clinician.
    """
    if len(p) < 120:
        return False                       # a fragment is a caption or a subscribe prompt
    if len(p.split()) < 18:
        return False
    symbols = sum(p.count(c) for c in "{}[]()<>=;|\\_$#")
    if symbols > len(p) * 0.06 or len(_CODEY.findall(p)) >= 2:
        return False                       # code is punctuation-dense
    letters = sum(1 for c in p if c.isalpha() or c.isspace())
    if letters < len(p) * 0.78:
        return False
    return (p.count(".") + p.count("?") + p.count("!")) >= 1


def essay_text(html: str) -> str:
    """RSS body HTML → prose paragraphs only.

    Code, output, tables and figures are removed as WHOLE BLOCKS before tags are stripped: replacing
    every tag with a space turned `par[1]` into `par[ 1 ]` and shipped source as if it were writing.
    """
    txt = _DROP_BLOCKS.sub("\n\n", html or "")
    txt = _BLOCK_END.sub("\n\n", txt)
    txt = _TAGS.sub("", txt)               # inline tags vanish; they never separated words
    for a, b in _ENTITIES:
        txt = txt.replace(a, b)
    txt = re.sub(r"&[a-z]+;|&#\d+;", " ", txt)
    paras = [_WS.sub(" ", p).strip() for p in re.split(r"\n\s*\n", txt)]
    return "\n\n".join(p for p in paras if looks_like_prose(p))


class ExpertEssayConnector:
    """Full-text expert blogs. The author's own words, so quotable and attributed."""

    key = "voices_essay"
    fetch_strategy = "poll"

    def __init__(self, feeds: dict[str, tuple[str, ...]] | None = None, *, fetch=None,
                 timeout: int = 30, max_posts: int = 12):
        self._feeds = dict(feeds or VOICE_ESSAYS)
        self._timeout = timeout
        self._max = max_posts
        self._fetch = fetch or self._http

    def _http(self, url: str) -> bytes:
        return urllib.request.urlopen(urllib.request.Request(url, headers=_UA),
                                      timeout=self._timeout).read()

    async def discover_entities(self, window: dict) -> list[_Ref]:
        out = []
        for url, spec in self._feeds.items():
            spec = tuple(spec) + ("", "", "")
            out.append(_Ref(source_key=self.key, native_id=url, title=spec[0],
                            facets={"show": spec[1] or spec[0], "writer": spec[0], "path": spec[2]}))
        return out

    async def list_documents(self, entity: _Ref) -> list[_Ref]:
        try:
            root = ET.fromstring(self._fetch(entity.native_id))
        except Exception:      # noqa: BLE001
            return []
        who = entity.title
        pub = entity.facets.get("show") or who
        need_path = entity.facets.get("path") or ""
        docs: list[_Ref] = []
        for it in [e for e in root.iter() if e.tag.split("}")[-1] in ("item", "entry")]:
            title, link, published, body = "", "", "", ""
            for el in it.iter():
                tag = el.tag.split("}")[-1]
                if tag == "title" and not title:
                    title = (el.text or "").strip()
                elif tag == "link" and not link:
                    link = (el.get("href") or el.text or "").strip()
                elif tag in ("pubDate", "published", "updated") and not published:
                    published = (el.text or "").strip()
                elif tag in ("encoded", "content", "description", "summary") and el.text:
                    if len(el.text) > len(body):
                        body = el.text
            if need_path and need_path not in (link or ""):
                continue           # a site-wide feed also carries talks and pages, not just posts
            if not title or not (link or "").startswith("http"):
                continue           # a card whose link does not resolve is worse than no card
            if len(essay_text(body)) < 600:
                continue           # a teaser, or a post that is mostly code, is not an essay
            docs.append(_Ref(
                source_key=self.key, native_id=link or title, title=title,
                facets={"source_kind": "essay", "kind": "essay", "show": pub, "writer": who,
                        "episode_title": title, "episode_url": link, "published": published,
                        "body": body},
                dates={"published": published}))
            if len(docs) >= max(1, int(self._max)):
                break
        return docs

    async def fetch_artifact(self, doc: _Ref) -> bytes:
        text = essay_text(doc.facets.pop("body", ""))
        paras = [p for p in text.split("\n\n") if p.strip()]
        doc.facets["passages"] = len(paras)
        return text.encode("utf-8")
