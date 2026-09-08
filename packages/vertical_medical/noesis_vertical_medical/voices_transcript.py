"""Podcast-transcript connector — what clinicians and researchers actually SAID, in their own words.

WHY TRANSCRIPTS AND NOT CHAPTER MARKERS. The equivalent feature in a sibling product is built on
publisher-written chapter lists, because its feeds carry almost no `<podcast:transcript>`. Medicine
measures the other way round (2026-09-08, `probe_tr.py`): of 22 medical shows sampled, 9 publish the
tag and 4 were verified end to end as downloading and parsing into timestamped speech —

    Healthcare Unfiltered  100% of recent episodes   VTT   321 cues / 34 min
    Core IM                 85%                      VTT   461 cues / 44 min   (speaker-diarized)
    Run the List            55%                      VTT   243 cues / 26 min
    The Lancet Voice        45%                      SRT   385 cues / 22 min   (AI-generated)

while only 3 of 29 shows publish chapter lists at all. So the medical leg reads the transcript: a
real quote, attributable to a speaker, deep-linkable to the second — strictly more than a pointer
saying where to listen.

WHAT THIS IS NOT. A transcript is COMMENTARY, never evidence. These blocks carry
`source_kind="transcript"`, which the manifest lists in `non_evidence_facets`, so the retrieval
source refuses to return them to the research loop no matter what a caller asks. They are a browsing
surface: what is being argued and where practice is moving, not what the evidence supports.

MACHINE TRANSCRIPTION IS FLAGGED. Several feeds are ASR output and some say so in their first cue. A
misheard word becomes a misquote with a physician's name on it, so `asr=True` rides on the facets and
the surface must show it rather than presenting the line as verbatim.
"""
from __future__ import annotations

import re
import urllib.request
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from typing import Any

PODCAST_NS = "{https://podcastindex.org/namespace/1.0}"
_UA = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
                     "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"}

# Shows whose transcript coverage was MEASURED, with the number that earned the place. A show is
# added by measuring it, never by reputation.
VOICE_SHOWS: dict[str, str] = {
    # Feed URLs are RESOLVED through the public iTunes lookup, never hand-written: three of four
    # guessed URLs 404'd, and a 404 reads exactly like a publisher who ships no transcripts.
    "Core IM | Internal Medicine Podcast":
        "https://feeds.redcircle.com/2c03e755-c428-4b8e-9150-95ef1ed2492b",  # 85% of eps, VTT, diarized
    "Healthcare Unfiltered": "https://rss.buzzsprout.com/2536939.rss",       # 100%, VTT
    "Run the List": "https://feeds.redcircle.com/3afc5caf-efbb-4dc3-ae69-fb7f23cceb66",   # 55%, VTT
    "The Lancet Voice": "https://feed.podbean.com/lancetvoice/feed.xml",     # 45%, SRT (ASR)
    "Behind The Knife: The Surgery Podcast":
        "https://audioboom.com/channels/5046960.rss",                        # 95%, text/plain (uncued)
}

_CUE = re.compile(r"(?P<a>(?:\d{1,2}:)?\d{1,2}:\d{2}(?:[.,]\d{1,3})?)\s*-->\s*"
                  r"(?P<b>(?:\d{1,2}:)?\d{1,2}:\d{2}(?:[.,]\d{1,3})?)")
_SPEAKER = re.compile(r"^\s*(?:\[(?P<b>[^\]]{1,40})\]|(?P<p>[A-Z][A-Za-z .'-]{1,38})):\s*")
_TAGS = re.compile(r"<[^>]+>")
_ASR_HINT = re.compile(r"\b(ai[- ]generated|automated|machine[- ]generated)\s+transcript\b", re.I)


def _secs(ts: str) -> int:
    parts = [float(x) for x in ts.replace(",", ".").split(":")]
    while len(parts) < 3:
        parts.insert(0, 0.0)
    return int(parts[0] * 3600 + parts[1] * 60 + parts[2])


def hhmmss(sec: int) -> str:
    sec = max(0, int(sec))
    return f"{sec // 3600:02d}:{(sec % 3600) // 60:02d}:{sec % 60:02d}"


def parse_cues(text: str) -> list[tuple[int, str]]:
    """(start_second, spoken text) from a VTT or SRT transcript.

    Both formats are 'timing line, then the words', so one reader covers them. Cue numbers, the
    WEBVTT banner and NOTE blocks are structure, not speech, and are dropped.
    """
    out: list[tuple[int, str]] = []
    start: int | None = None
    buf: list[str] = []
    for raw in (text or "").splitlines():
        line = raw.strip()
        m = _CUE.search(line)
        if m:
            if start is not None and buf:
                out.append((start, " ".join(buf).strip()))
            start, buf = _secs(m.group("a")), []
            continue
        if not line or line.isdigit() or line.startswith(("WEBVTT", "NOTE", "Kind:", "Language:", "STYLE")):
            continue
        buf.append(_TAGS.sub("", line))
    if start is not None and buf:
        out.append((start, " ".join(buf).strip()))
    return out


@dataclass
class Passage:
    start: int
    speaker: str
    text: str


def plain_passages(text: str) -> list["Passage"]:
    """A transcript with no cues: one passage per paragraph, no offsets.

    Grouping these by length would merge them, and paragraph breaks are the ONLY structure such a
    file has — losing them would leave a wall of text with nothing to quote or rank.
    """
    out: list[Passage] = []
    for para in re.split(r"\n\s*\n", text or ""):
        body = " ".join(para.split()).strip()
        if not body:
            continue
        speaker = ""
        m = _SPEAKER.match(body)
        if m:
            speaker = (m.group("b") or m.group("p") or "").strip()
            body = body[m.end():].strip()
        if body:
            out.append(Passage(0, speaker, body))
    return out


def to_passages(cues: list[tuple[int, str]], *, target_chars: int = 700,
                max_chars: int = 1200) -> list[Passage]:
    """Group cues into readable passages, each keeping the second it starts at.

    A cue is a couple of seconds of speech — far too small to quote or to rank. Passages break on a
    SPEAKER CHANGE first (a turn is the natural unit of "who said what") and otherwise at roughly
    `target_chars`, so a passage is a coherent stretch of one person talking.
    """
    passages: list[Passage] = []
    cur: list[str] = []
    cur_start: int | None = None
    cur_speaker = ""

    def flush():
        nonlocal cur, cur_start, cur_speaker
        if cur and cur_start is not None:
            body = " ".join(cur).strip()
            if body:
                passages.append(Passage(cur_start, cur_speaker, body))
        cur, cur_start, cur_speaker = [], None, ""

    for start, line in cues:
        speaker = ""
        m = _SPEAKER.match(line)
        if m:
            speaker = (m.group("b") or m.group("p") or "").strip()
            line = line[m.end():].strip()
        if not line:
            continue
        if cur_start is None:
            cur_start, cur_speaker = start, speaker
        elif (speaker and speaker != cur_speaker) or len(" ".join(cur)) >= target_chars:
            flush()
            cur_start, cur_speaker = start, speaker
        cur.append(line)
        if len(" ".join(cur)) >= max_chars:
            flush()
    flush()
    return passages


def episode_markdown(passages: list[Passage]) -> str:
    """One paragraph per passage, opening with its offset.

    The kernel splitter breaks on blank lines, so this yields exactly one searchable block per
    passage, and the offset survives inside the block text (the block table has no column for it).
    """
    return "\n\n".join(
        f"[{hhmmss(p.start)}] " + (f"{p.speaker}: " if p.speaker else "") + p.text
        for p in passages)


def _text(el, tag: str) -> str:
    node = el.find(tag)
    return (node.text or "").strip() if node is not None and node.text else ""


@dataclass
class _Ref:
    """Minimal EntityRef/DocumentRef shape the kernel ingest pipeline consumes."""
    source_key: str
    native_id: str
    title: str = ""
    content_type: str = "text/markdown"
    facets: dict = field(default_factory=dict)
    dates: dict = field(default_factory=dict)
    entity_ids: tuple = ()


class PodcastTranscriptConnector:
    """Feeds → episodes that publish a transcript → timestamped passages.

    Fetching is injectable so the tests never touch the network.
    """

    key = "voices_transcript"
    fetch_strategy = "poll"

    def __init__(self, shows: dict[str, str] | None = None, *, fetch=None, timeout: int = 30,
                 max_episodes: int = 12):
        self._shows = dict(shows or VOICE_SHOWS)
        self._timeout = timeout
        self._max = max_episodes
        self._fetch = fetch or self._http
        self._bodies: dict[str, bytes] = {}

    def _http(self, url: str) -> bytes:
        return urllib.request.urlopen(urllib.request.Request(url, headers=_UA),
                                      timeout=self._timeout).read()

    async def discover_entities(self, window: dict) -> list[_Ref]:
        """One entity per show. A show that fails to fetch is skipped, never fatal to the rest."""
        out = []
        for name, feed in self._shows.items():
            out.append(_Ref(source_key=self.key, native_id=feed, title=name,
                            facets={"show": name}))
        return out

    async def list_documents(self, entity: _Ref) -> list[_Ref]:
        show = entity.title
        try:
            root = ET.fromstring(self._fetch(entity.native_id))
        except Exception:      # noqa: BLE001 — one dead feed never stops the sweep
            return []
        docs: list[_Ref] = []
        limit = max(1, int(self._max))
        for item in [e for e in root.iter() if e.tag.split("}")[-1] == "item"]:
            trs = [el for el in item.iter() if el.tag == PODCAST_NS + "transcript"]
            if not trs:
                continue                     # no transcript, no moment — this leg quotes speech only
            # prefer a cued format: it carries the offsets that make a moment deep-linkable
            trs.sort(key=lambda e: 0 if "vtt" in (e.get("type") or "") else
                     1 if "srt" in (e.get("type") or "").lower() or "subrip" in (e.get("type") or "") else 2)
            url = trs[0].get("url") or ""
            if not url:
                continue
            title = _text(item, "title")
            page = _text(item, "link")
            audio = ""
            for enc in item.iter():
                if enc.tag.split("}")[-1] == "enclosure" and (enc.get("type") or "").startswith("audio"):
                    audio = enc.get("url") or ""
                    break
            guid = _text(item, "guid") or url
            docs.append(_Ref(
                source_key=self.key, native_id=guid, title=title,
                facets={"source_kind": "transcript", "kind": "podcast", "show": show,
                        "episode_title": title, "episode_url": page, "audio_url": audio,
                        "transcript_url": url, "transcript_type": trs[0].get("type") or "",
                        "published": _text(item, "pubDate")},
                dates={"published": _text(item, "pubDate")}))
            if len(docs) >= limit:
                break
        return docs

    async def fetch_artifact(self, doc: _Ref) -> bytes:
        """Download the transcript and render it as offset-prefixed passages."""
        url = doc.facets.get("transcript_url") or ""
        try:
            raw = self._fetch(url).decode("utf-8", "ignore")
        except Exception:      # noqa: BLE001
            return b""
        cues = parse_cues(raw)
        passages = to_passages(cues) if cues else plain_passages(raw)
        head = " ".join(t for _, t in cues[:3]) if cues else raw[:400]
        doc.facets["asr"] = bool(_ASR_HINT.search(head))
        doc.facets["passages"] = len(passages)
        doc.facets["duration_s"] = cues[-1][0] if cues else 0
        return episode_markdown(passages).encode("utf-8")
