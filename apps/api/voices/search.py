"""Searching spoken passages: SQL building, ranking, and the row → card shape.

Keyword-only, deliberately. The transcript corpus is ingested without vectors (the block tsvector is
a generated column, so rows are searchable the moment they land), which is what makes this leg
buildable while a model account is empty. Vectors can backfill later without changing this file.

Every function here is PURE — it builds SQL or reshapes a row and does no I/O — so the whole search
surface is testable without a database.
"""
from __future__ import annotations

import re
from typing import Any

# Only these source keys are voices. Naming them explicitly stops the surface from drifting into the
# evidence corpus, which is a different kind of material answering a different question.
VOICE_SOURCE_KEYS: tuple[str, ...] = ("voices_transcript", "voices_video", "voices_essay")

KIND_SOURCES: dict[str, tuple[str, ...]] = {
    "podcast": ("voices_transcript",),
    "video": ("voices_video",),
    "essay": ("voices_essay",),
}

# grammar words, and words so common in clinical speech that they select nothing
_STOP = {"the", "a", "an", "of", "in", "on", "for", "to", "and", "or", "is", "are", "was", "were",
         "be", "with", "as", "at", "by", "it", "its", "this", "that", "from", "what", "how", "why",
         "do", "does", "did", "can", "should", "would", "when", "which", "who", "about", "into"}
_GENERIC = {"patient", "patients", "clinical", "doctor", "doctors", "medicine", "medical", "care",
            "health", "treatment", "disease", "study", "studies", "data", "evidence", "think"}

_REGISTER = {
    "transcript": "Transcribed speech, attributed to the speaker on the recording",
    "asr": "Machine-generated transcript — wording may be inexact; listen before quoting",
    "chapter": "Chapter written by the publisher — it marks where to watch, not what was said",
    "essay": "First-person writing, attributed to its author",
}

_OFFSET = re.compile(r"^\[(?P<h>\d{2}):(?P<m>\d{2}):(?P<s>\d{2})\]\s*")
_SPEAKER = re.compile(r"^(?P<who>[A-Za-z0-9_ .'\-]{1,40}):\s*")


def terms(q: str) -> list[str]:
    """Query words worth searching on, longest first, generic clinical words dropped last."""
    words = [w.lower() for w in re.findall(r"[A-Za-z0-9][A-Za-z0-9\-']{1,}", q or "")]
    kept = [w for w in words if w not in _STOP and len(w) > 2]
    specific = [w for w in kept if w not in _GENERIC]
    # drop the near-universal words ONLY if something more specific survives, so a query made
    # entirely of them ("what do doctors think") still searches for something
    out = specific or kept
    seen, uniq = set(), []
    for w in sorted(out, key=lambda w: (-len(w), w)):
        if w not in seen:
            seen.add(w)
            uniq.append(w)
    return uniq[:8]


def tsqueries(ws: list[str]) -> list[tuple[str, str]]:
    """A strict → relaxed ladder of tsqueries: (label, expression).

    `plainto_tsquery` requires every word, so a spoken question phrased as a sentence matches almost
    nothing. The caller walks these rungs and stops at the strictest one that actually answers, then
    reports which rung it was — a result set the user can trust to be as tight as it could be.
    """
    if not ws:
        return []
    out = [("all words", " & ".join(ws))]
    if len(ws) > 2:
        pairs = [f"({a} & {b})" for i, a in enumerate(ws[:4]) for b in ws[i + 1:5]]
        if pairs:
            out.append(("most words", " | ".join(pairs)))
    if len(ws) > 1:
        out.append(("any word", " | ".join(ws)))
    return out


def build_query(*, tsquery: str = "", kinds: tuple[str, ...] = (), show: str = "",
                speaker: str = "", limit: int = 30, table: str = "rs_block",
                order: str = "relevance", since: str = "") -> tuple[str, list]:
    """(sql, params) for a voices search. No I/O — the SQL is the unit under test."""
    keys = list(kinds) if kinds else list(VOICE_SOURCE_KEYS)
    params: list[Any] = [keys]
    preds = [f"source_key = ANY($1::text[])"]

    # a passage with no words is furniture, never a moment
    preds.append("length(text) > 40")
    if show:
        params.append(show)
        preds.append(f"(facets ->> 'show') = ${len(params)}")
    if speaker:
        params.append(speaker.lower())
        preds.append(f"lower(text) LIKE '%' || ${len(params)} || '%'")
    if since:
        params.append(since)
        preds.append(f"(facets ->> 'published_at') >= ${len(params)}")

    if tsquery:
        params.append(tsquery)
        tq = f"to_tsquery('english', ${len(params)})"
        preds.append(f"tsv @@ {tq}")
        # normalisation flag 1 divides by document length: without it a long episode that says a
        # word twice outranks the passage that is ABOUT that word, and short passages never surface
        rank = f"ts_rank(tsv, {tq}, 1)"
        snippet = (f"ts_headline('english', text, {tq}, "
                   "'MaxWords=48, MinWords=20, ShortWord=3, MaxFragments=1, StartSel=«, StopSel=»')")
    else:
        rank = "0"
        snippet = "left(text, 400)"

    order_sql = {
        "relevance": f"{rank} DESC, (facets ->> 'published_at') DESC NULLS LAST",
        "recent": "(facets ->> 'published_at') DESC NULLS LAST",
    }.get(order, f"{rank} DESC")

    params.append(int(limit))
    sql = (f"SELECT document_id, block_id, text, document_title, source_key, facets, "
           f"{rank} AS rank, {snippet} AS snippet "
           f"FROM {table} WHERE " + " AND ".join(preds) +
           f" ORDER BY {order_sql} LIMIT ${len(params)}")
    return sql, params


def moment(row: dict) -> dict:
    """A stored passage → the card the surface renders.

    The offset lives inside the block text (`[hh:mm:ss] Speaker: words`) because the block table has
    no column for it; this is where it is read back out, and where the spoken words are separated
    from the metadata wrapped around them.
    """
    facets = row.get("facets") or {}
    if isinstance(facets, str):
        import json
        try:
            facets = json.loads(facets)
        except Exception:      # noqa: BLE001
            facets = {}
    raw = (row.get("text") or "").strip()
    chapter_link = ""
    mlink = re.search(r"\s+—\s+(https?://\S+)$", raw)
    if mlink:
        chapter_link = mlink.group(1)
        raw = raw[:mlink.start()].strip()
    t_start = 0
    m = _OFFSET.match(raw)
    if m:
        t_start = int(m.group("h")) * 3600 + int(m.group("m")) * 60 + int(m.group("s"))
        raw = raw[m.end():]
    speaker = ""
    ms = _SPEAKER.match(raw)
    if ms:
        speaker = ms.group("who").strip()
        raw = raw[ms.end():]

    # The snippet comes from ts_headline over the RAW block, so it carries the same offset/speaker
    # prefix — which rendered inside the quotation as if the speaker had said their own timestamp.
    snip = (row.get("snippet") or "").strip()
    snip = _OFFSET.sub("", snip)
    ms2 = _SPEAKER.match(snip)
    if ms2 and (not speaker or ms2.group("who").strip() == speaker):
        snip = snip[ms2.end():]

    # A diarization label is not a name. Showing "SPEAKER_01" where a person belongs implies we know
    # who spoke when we do not, so it is kept out of the attribution line.
    anonymous = bool(re.fullmatch(r"SPEAKER[_ ]?\d+", speaker or "", re.I))
    asr = bool(facets.get("asr"))
    audio = facets.get("audio_url") or ""
    page = facets.get("episode_url") or ""
    video_id = facets.get("video_id") or ""
    if chapter_link:
        audio, page = "", chapter_link      # a chapter already carries its own &t= deep link
        mv = re.search(r"[?&]v=([\w-]{6,})", chapter_link)
        if mv and not video_id:
            video_id = mv.group(1)

    # What the card can PLAY in place, and from which second. Kept as structured fields rather than a
    # URL fragment: an <audio> element does not reliably honour #t=, so the client seeks explicitly.
    if video_id:
        media = {"kind": "youtube", "id": video_id, "t": t_start}
    elif audio:
        media = {"kind": "audio", "url": audio, "t": t_start}
    else:
        media = None
    return {
        "id": f"{row.get('document_id','')}::{row.get('block_id','')}",
        "kind": facets.get("kind") or "podcast",
        "text": raw,
        "speaker": "" if anonymous else speaker,
        "speaker_anonymous": anonymous,
        "show": facets.get("show") or row.get("document_title") or "",
        "episode": facets.get("episode_title") or row.get("document_title") or "",
        "published": facets.get("published") or "",
        "t_start": t_start,
        "url": (f"{audio}#t={t_start}" if audio else page),
        "art": facets.get("art") or "",
        "media": media,
        "episode_url": page,
        "asr": asr,
        # The register line is printed verbatim by the surface. A machine transcript is not a
        # quotation: a misheard word would become a misquote attributed to a named clinician.
        "register": _REGISTER["asr" if asr else (facets.get("source_kind") or "transcript")],
        # A chapter title is written by the publisher ABOUT the video — it says where to watch, never
        # what was said, so it can never be set as a quotation.
        "quotable": (not asr) and facets.get("source_kind") != "chapter",
        "writer": facets.get("writer") or "",
        "snippet": snip,
    }


def dedupe(moments: list[dict], *, per_episode: int = 2, per_show: int = 3) -> list[dict]:
    """Keep a result set varied: one talkative episode must not fill the page.

    Two passes, so a thin result set still fills up rather than being starved by the caps.
    """
    out, spill = [], []
    ep: dict[str, int] = {}
    show: dict[str, int] = {}
    for m in moments:
        doc = m["id"].split("::")[0]
        s = m.get("show") or ""
        if ep.get(doc, 0) >= per_episode or show.get(s, 0) >= per_show:
            spill.append(m)
            continue
        ep[doc] = ep.get(doc, 0) + 1
        show[s] = show.get(s, 0) + 1
        out.append(m)
    return out + spill
