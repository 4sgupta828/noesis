"""What a piece actually says — a summary of the WHOLE essay or episode, read in place.

"Read here" used to expand the one passage the card already showed, which did nothing. This reads
every passage of the piece and reports what its author claims.

Two rules make it safe to put under a clinical answer:

  1. NOTHING IS INVENTED. A takeaway asserting a figure the source never states is DROPPED in code,
     not merely discouraged in the prompt. The model chooses what matters; it does not get to add
     numbers.
  2. IT REPORTS, IT DOES NOT ENDORSE. The prompt says so, the card says so, and the register line
     already says this is commentary rather than evidence.

With no model — or a failed call — it degrades to an extractive summary built from the source's own
sentences and says which it is, so the control always does something.
"""
from __future__ import annotations

import json
import re
from typing import Any

from pydantic import BaseModel, Field

VERSION = 2                       # bump to force a re-read after a shape change
TTL_DAYS = {"model": 365, "extractive": 3}   # a stopgap summary is retried when a model returns

DDL = """
CREATE TABLE IF NOT EXISTS vo_summary (
    document_id text PRIMARY KEY,
    heading     text NOT NULL DEFAULT '',
    points      jsonb NOT NULL DEFAULT '[]'::jsonb,
    quotes      jsonb NOT NULL DEFAULT '[]'::jsonb,
    basis       text NOT NULL DEFAULT '',
    v           int  NOT NULL DEFAULT 1,
    made_at     timestamptz NOT NULL DEFAULT now()
);
"""

SYSTEM = """You are summarising ONE piece of medical commentary — a podcast episode, a talk, or an \
essay — for a clinician deciding whether it is worth their time.

Report what THIS AUTHOR OR SPEAKER claims. You are not judging whether they are right, and you add \
no opinion, caveat or endorsement of your own.

Return strict JSON:
  heading: one line, under 12 words, naming what the piece is actually about.
  points:  3-6 takeaways, one sentence each, under 25 words. Prefer a number, a mechanism, a named \
trial, or a concrete recommendation the author makes. Every figure must appear in the source text.
  quotes:  0-2 VERBATIM sentences from the source, chosen because they carry the argument. Copy them \
exactly or leave the list empty.

Never state a figure, dose, date or trial name the source does not contain. If the piece is thin, \
return fewer points rather than padding."""


class Summary(BaseModel):
    heading: str = ""
    points: list[str] = Field(default_factory=list)
    quotes: list[str] = Field(default_factory=list)


_NUM = re.compile(r"\d[\d,.]*\s*%?")
_SENT = re.compile(r"(?<=[.!?])\s+")


def _norm(s: str) -> str:
    return re.sub(r"[\s,]", "", (s or "").lower()).replace("percent", "%")


def verify(points: list[str], source: str) -> list[str]:
    """Drop any takeaway asserting a figure the source never states.

    The prompt asks for grounded numbers; this enforces it. A summary that invents "a 30% reduction"
    under a clinical answer is exactly the failure the rest of the product is built to prevent.
    """
    hay = _norm(source)
    kept = []
    for p in points or []:
        figs = [f for f in _NUM.findall(p or "") if len(_norm(f)) > 1]
        if all(_norm(f) in hay for f in figs):
            kept.append(p.strip())
    return kept


def extractive(text: str, *, n: int = 4) -> list[str]:
    """A summary made only of the source's own sentences — the no-model path.

    Scores by content-word frequency, normalised for length so a long sentence cannot win by size
    alone, with a nudge for sentences carrying a figure.
    """
    sents = [s.strip() for s in _SENT.split(text or "") if 40 <= len(s.strip()) <= 320]
    if not sents:
        return []
    words: dict[str, int] = {}
    for s in sents:
        for w in re.findall(r"[a-z]{4,}", s.lower()):
            words[w] = words.get(w, 0) + 1
    def score(s: str) -> float:
        ws = re.findall(r"[a-z]{4,}", s.lower())
        if not ws:
            return 0.0
        base = sum(words.get(w, 0) for w in ws) / (len(ws) ** 0.6)
        return base * (1.15 if re.search(r"\d", s) else 1.0)
    best = sorted(sents, key=score, reverse=True)[:n]
    return [s for s in sents if s in best]          # keep the source's own order


async def summarize(*, title: str, source: str, llm=None) -> dict[str, Any]:
    """{heading, points, quotes, basis} for one piece. Never raises."""
    text = (source or "").strip()
    if not text:
        return {"heading": "", "points": [], "quotes": [], "basis": "empty"}
    if llm is not None:
        try:
            paras = [p for p in text.split("\n\n") if p.strip()][:60]
            user = f"TITLE: {title}\n\n" + "\n\n".join(paras)
            res = await llm.complete(system=SYSTEM, messages=[{"role": "user", "content": user}],
                                     response_format=Summary, max_tokens=900)
            got = res.parsed if hasattr(res, "parsed") else res
            if isinstance(got, str):
                got = Summary(**json.loads(got))
            points = verify(list(got.points or []), text)
            # a quote is only a quote if the source contains it
            flat = re.sub(r"\s+", " ", text).lower()
            quotes = [q.strip() for q in (got.quotes or [])
                      if q and re.sub(r"\s+", " ", q).strip().lower() in flat][:2]
            if points:
                return {"heading": (got.heading or title or "").strip(), "points": points,
                        "quotes": quotes, "basis": "model"}
        except Exception as e:      # noqa: BLE001 — a summary never breaks the card
            print(f"[voices] summary model failed: {type(e).__name__}: {e}", flush=True)
    pts = extractive(text)
    return {"heading": (title or "").strip(), "points": pts, "quotes": [],
            "basis": "extractive" if pts else "empty"}
