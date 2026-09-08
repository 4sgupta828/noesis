"""Voices HTTP surface: search, sources, and the admin ingest job.

Flag-gated (`NOESIS_VOICES`). OFF is a true no-op — no routes registered, no pool opened, no table
touched — so the feature cannot affect a deployment that has not asked for it.
"""
from __future__ import annotations

import os

from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel

from .search import (
    KIND_SOURCES, VOICE_SOURCE_KEYS, build_query, dedupe, moment, one_per_show, terms, tsqueries,
)


def voices_enabled() -> bool:
    return os.environ.get("NOESIS_VOICES", "").lower() in ("1", "true", "yes", "on")


class VoiceSearchIn(BaseModel):
    q: str = ""
    kind: str = ""            # "" = every voice source; otherwise a key of KIND_SOURCES
    show: str = ""
    speaker: str = ""
    limit: int = 30
    order: str = "relevance"  # "relevance" | "recent"


class VoiceRelatedIn(BaseModel):
    question: str = ""
    limit: int = 3


class VoiceJobIn(BaseModel):
    kind: str = "ingest"
    limit: int = 12           # episodes/videos/posts per source
    leg: str = ""             # "" = every leg; "podcast" | "video" | "essay"
    purge: bool = False       # drop this leg's existing blocks first — an extraction fix does not
                              # rewrite blocks whose ids it no longer produces, so junk would linger
    shows: list[str] | None = None


def _vec_literal(v) -> str:
    return "[" + ",".join(f"{float(x):.6f}" for x in v) + "]"


def build_router(pool_of, *, manifest=None, pg_source_of=None, tenant_id: str = "demo",
                 admin_password_of=None, embedder=None, embedder_of=None) -> APIRouter:
    """`pool_of()` → an asyncpg pool; `pg_source_of()` → the corpus retrieval source (for ingest)."""
    router = APIRouter()

    @router.post("/voices/search")
    async def voices_search(body: VoiceSearchIn) -> dict:
        """Spoken passages matching a question.

        Walks the strict → relaxed ladder and STOPS at the tightest rung that actually answers, then
        says which rung it was, so a loose result set is never passed off as a precise one.
        """
        pool = await pool_of()
        if pool is None:
            return {"moments": [], "ranking": "", "terms": []}
        kinds = KIND_SOURCES.get(body.kind, ()) if body.kind else ()
        if body.kind and not kinds:
            return {"moments": [], "ranking": "no such kind", "terms": []}
        limit = max(1, min(int(body.limit or 30), 100))
        ws = terms(body.q)
        rungs = tsqueries(ws)

        # SEMANTIC leg: embed the question once. Failure is never fatal — the keyword ladder below
        # still answers, which is what kept this surface working while there was no embedder at all.
        vector = ""
        if body.q.strip() and embedder_of is not None:
            try:
                vector = _vec_literal(embedder_of().embed([body.q.strip()])[0])
            except Exception as e:      # noqa: BLE001
                print(f"[voices] embed failed, falling back to keywords: {type(e).__name__}: {e}",
                      flush=True)

        async def run(tsq: str, order: str, vec: str = ""):
            sql, params = build_query(tsquery=tsq, kinds=kinds, show=body.show,
                                      speaker=body.speaker, limit=limit, order=order, vector=vec)
            async with pool.acquire() as conn:
                return [dict(r) for r in await conn.fetch(sql, *params)]

        ranking, moments = "", []
        if vector:
            # one pass: meaning ranks, words only nudge. No ladder — there is nothing to relax.
            moments = [moment(r) for r in await run(rungs[0][1] if rungs else "", body.order, vector)]
            ranking = "by meaning"
        elif not rungs:                     # a browse: newest first, no ranking claim to make
            moments = [moment(r) for r in await run("", "recent")]
            ranking = "recent"
        else:
            # "enough to stop here" has to scale with what was ASKED for: demanding 6 rows when the
            # caller wants 3 can never be met, and the ladder would walk to its loosest rung every
            # time. Distinct shows are counted off the PARSED card, because facets come back from the
            # driver as JSON text — reading .get on the raw row silently counted one show forever.
            need = max(2, min(6, limit))
            for label, tsq in rungs:
                cand = [moment(r) for r in await run(tsq, body.order)]
                moments, ranking = cand, f"matched {label}"
                if len(cand) >= need and len({m["show"] for m in cand}) >= 2:
                    break
            if not moments:
                moments = [moment(r) for r in await run("", "recent")]
                ranking = "no match — showing recent"
        moments = dedupe(moments)
        return {"moments": moments, "ranking": ranking, "terms": ws,
                "counts": {"total": len(moments),
                           "quotable": sum(1 for m in moments if m["quotable"])}}

    @router.post("/voices/related")
    async def voices_related(body: VoiceRelatedIn) -> dict:
        """A few things people have SAID near this question — to sit beside a finished answer.

        Deliberately a SEPARATE lookup, not part of answering. The research path refuses these blocks
        outright (they are declared non-evidence), and that must stay true: this is further listening
        offered next to an answer, never a source the answer rests on. It runs after the answer, so a
        failure here can never affect one.
        """
        pool = await pool_of()
        q = (body.question or "").strip()
        if pool is None or not q or embedder_of is None:
            return {"moments": [], "basis": ""}
        try:
            vector = _vec_literal(embedder_of().embed([q])[0])
        except Exception as e:      # noqa: BLE001
            print(f"[voices] related embed failed: {type(e).__name__}: {e}", flush=True)
            return {"moments": [], "basis": ""}
        sql, params = build_query(vector=vector, limit=40, order="relevance")
        async with pool.acquire() as conn:
            rows = [dict(r) for r in await conn.fetch(sql, *params)]
        # Measured on prod: on-topic suggestions score 0.54-0.58; 0.39 returned a passage about CSF
        # drug penetration under a metformin question, while 0.42 on the same question was a useful
        # nephrology passage. Hence both tests — an absolute floor and a margin below the best match.
        picks = one_per_show([moment(r) for r in rows],
                             limit=max(1, min(int(body.limit or 3), 5)), floor=0.40, margin=0.08)
        return {"moments": picks, "basis": "commentary — not part of the evidence for this answer"}

    @router.get("/voices/sources")
    async def voices_sources() -> dict:
        """What is actually in here — the honest coverage answer, by show."""
        pool = await pool_of()
        if pool is None:
            return {"sources": []}
        async with pool.acquire() as conn:
            rows = await conn.fetch(
                "SELECT facets ->> 'show' AS show, count(DISTINCT document_id) AS episodes, "
                "count(*) AS passages, max(facets ->> 'published') AS latest "
                "FROM rs_block WHERE source_key = ANY($1::text[]) AND facets ? 'show' "
                "GROUP BY 1 ORDER BY 3 DESC", list(VOICE_SOURCE_KEYS))
        return {"sources": [dict(r) for r in rows]}

    @router.post("/admin/voices/jobs")
    async def voices_jobs(body: VoiceJobIn, x_admin_password: str = Header(default="")) -> dict:
        """Ingest transcripts. Admin-gated and on demand — there is no cron."""
        # resolved per request, so the gate follows a live env change and needs no import-order dance
        expected = admin_password_of() if admin_password_of else ""
        if not expected or x_admin_password != expected:
            raise HTTPException(status_code=401, detail="bad admin password")
        if body.kind != "ingest":
            raise HTTPException(status_code=400, detail=f"unknown job: {body.kind}")
        if pg_source_of is None:
            raise HTTPException(status_code=503, detail="ingest not configured")
        from noesis_kernel.runtime.ingest import ingest_connector_to_postgres

        from noesis_vertical_medical.voices_media import (
            ExpertEssayConnector, YouTubeChapterConnector,
        )
        from noesis_vertical_medical.voices_transcript import (
            VOICE_SHOWS, PodcastTranscriptConnector,
        )
        n = max(1, min(int(body.limit or 12), 50))
        keys = {"podcast": "voices_transcript", "video": "voices_video", "essay": "voices_essay"}
        purged = {}
        if body.purge:
            want = [keys[body.leg]] if body.leg in keys else list(keys.values())
            pool = await pool_of()
            if pool is not None:
                async with pool.acquire() as conn:
                    for k in want:
                        res = await conn.execute(
                            "DELETE FROM rs_block WHERE source_key = $1", k)
                        purged[k] = int(res.split()[-1]) if res.split()[-1].isdigit() else 0
        shows = {k: v for k, v in VOICE_SHOWS.items() if not body.shows or k in body.shows}
        legs = []
        if body.leg in ("", "podcast"):
            legs.append(PodcastTranscriptConnector(shows, max_episodes=n))
        if body.leg in ("", "video"):
            legs.append(YouTubeChapterConnector(max_videos=n))
        if body.leg in ("", "essay"):
            legs.append(ExpertEssayConnector(max_posts=n))
        out, blocks = {}, 0
        for leg in legs:
            # one failing leg never costs the others their ingest
            try:
                # embeddings are what make the search semantic; ~$0.03 for this whole corpus
                got = await ingest_connector_to_postgres(
                    leg, pg_source_of(), tenant_id=tenant_id,
                    embedder=(embedder_of() if embedder_of else embedder),
                    window={"limit": n})
            except Exception as e:      # noqa: BLE001
                out[leg.key] = f"failed: {type(e).__name__}: {e}"[:200]
                continue
            out[leg.key] = got
            blocks += got
        return {"kind": "ingest", "blocks": blocks, "legs": out, "purged": purged}

    return router
