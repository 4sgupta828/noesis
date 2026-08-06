"""Research-session persistence — save each Q&A (and any generated video) like factra's
`rs_research_session`. App-level (NOT kernel): keeps the kernel generic. Backed by the same
Postgres the corpus uses (NOESIS_CORPUS_DSN); a no-op store is used when no DSN is set so the
API still runs against the fixture corpus.

VERTICAL-ISOLATED: the store is bound to ONE vertical (the deployment's active vertical) and
every query is scoped by it, so sessions never cross verticals even if a DB were shared. This
composes with tenant isolation (both are filtered).

Saving is best-effort: a persistence failure must never break the /research response.
"""
from __future__ import annotations

import json
import uuid
from typing import Any

_DDL = """
CREATE TABLE IF NOT EXISTS noesis_research_session (
    id             TEXT PRIMARY KEY,
    vertical       TEXT NOT NULL,
    tenant_id      TEXT NOT NULL,
    workspace_id   TEXT,
    question       TEXT NOT NULL,
    answer         TEXT NOT NULL DEFAULT '',
    grounded       BOOLEAN NOT NULL DEFAULT FALSE,
    claims         JSONB NOT NULL DEFAULT '[]'::jsonb,
    source_stats   JSONB NOT NULL DEFAULT '{}'::jsonb,
    coverage_gaps  JSONB NOT NULL DEFAULT '[]'::jsonb,
    rejected       INTEGER NOT NULL DEFAULT 0,
    sources        JSONB NOT NULL DEFAULT '[]'::jsonb,
    video_filename TEXT,
    video_title    TEXT,
    video_duration DOUBLE PRECISION,
    user_name      TEXT,
    user_email     TEXT,
    visual_observation TEXT,
    attachments    JSONB NOT NULL DEFAULT '[]'::jsonb,
    layman_answer  TEXT,
    deleted        BOOLEAN NOT NULL DEFAULT FALSE,
    thread         JSONB NOT NULL DEFAULT '[]'::jsonb,
    created_at     TIMESTAMPTZ NOT NULL DEFAULT now()
);
-- additive columns for pre-existing tables (expand-only; safe to re-run)
ALTER TABLE noesis_research_session ADD COLUMN IF NOT EXISTS user_name  TEXT;
ALTER TABLE noesis_research_session ADD COLUMN IF NOT EXISTS user_email TEXT;
ALTER TABLE noesis_research_session ADD COLUMN IF NOT EXISTS visual_observation TEXT;
ALTER TABLE noesis_research_session ADD COLUMN IF NOT EXISTS attachments JSONB NOT NULL DEFAULT '[]'::jsonb;
ALTER TABLE noesis_research_session ADD COLUMN IF NOT EXISTS layman_answer TEXT;
ALTER TABLE noesis_research_session ADD COLUMN IF NOT EXISTS deleted BOOLEAN NOT NULL DEFAULT FALSE;
ALTER TABLE noesis_research_session ADD COLUMN IF NOT EXISTS thread JSONB NOT NULL DEFAULT '[]'::jsonb;
ALTER TABLE noesis_research_session ADD COLUMN IF NOT EXISTS audience TEXT NOT NULL DEFAULT 'clinician';
CREATE INDEX IF NOT EXISTS idx_nrs_vertical_tenant_created
    ON noesis_research_session (vertical, tenant_id, created_at DESC);
"""


class SessionStore:
    """Async Postgres-backed store, BOUND to one vertical. Schema ensured lazily.

    Every read/write is scoped by `self._vertical` so a deployment can only ever see its
    own vertical's sessions.
    """

    def __init__(self, dsn: str, *, vertical: str):
        self._dsn = dsn
        self._vertical = vertical
        self._pool = None
        self._ready = False

    async def _get_pool(self):
        if self._pool is None:
            import asyncpg
            self._pool = await asyncpg.create_pool(self._dsn, min_size=1, max_size=4)
        return self._pool

    async def _ensure(self) -> None:
        if self._ready:
            return
        pool = await self._get_pool()
        async with pool.acquire() as conn:
            await conn.execute(_DDL)
        self._ready = True

    async def save(self, *, tenant_id: str, workspace_id: str | None, question: str,
                   answer: str, grounded: bool, claims: list[dict], source_stats: dict,
                   coverage_gaps: list[str], rejected: int, sources: list[str] | None,
                   user_name: str | None = None, user_email: str | None = None,
                   visual_observation: str | None = None,
                   attachments: list[dict] | None = None,
                   audience: str = "clinician",
                   charts: list[dict] | None = None) -> str:
        await self._ensure()
        sid = uuid.uuid4().hex
        # turn 0 also lives in `thread` so a conversation is one shareable row; the flat columns
        # keep the first turn for the list view + backward compatibility.
        turn0 = {"question": question, "answer": answer, "grounded": grounded, "claims": claims,
                 "source_stats": source_stats, "coverage_gaps": coverage_gaps, "rejected": rejected,
                 "visual_observation": visual_observation, "attachments": attachments or []}
        if audience and audience != "clinician":
            turn0["audience"] = audience     # per-turn tag; the flat column drives list segmentation
        if charts:
            turn0["charts"] = charts         # grounded charts persist in the shareable session (JSONB)
        pool = await self._get_pool()
        async with pool.acquire() as conn:
            await conn.execute(
                """INSERT INTO noesis_research_session
                   (id, vertical, tenant_id, workspace_id, question, answer, grounded, claims,
                    source_stats, coverage_gaps, rejected, sources, user_name, user_email,
                    visual_observation, attachments, thread, audience)
                   VALUES ($1,$2,$3,$4,$5,$6,$7,$8::jsonb,$9::jsonb,$10::jsonb,$11,$12::jsonb,
                           $13,$14,$15,$16::jsonb,$17::jsonb,$18)""",
                sid, self._vertical, tenant_id, workspace_id, question, answer, grounded,
                json.dumps(claims), json.dumps(source_stats), json.dumps(coverage_gaps),
                rejected, json.dumps(sources or []),
                (user_name or None), (user_email or None),
                (visual_observation or None), json.dumps(attachments or []),
                json.dumps([turn0]), (audience or "clinician"),
            )
        return sid

    async def append_turn(self, session_id: str, turn: dict, *, audience: str = "clinician") -> bool:
        """Append a follow-up turn to a conversation thread (in place). Returns True if it matched.

        AUDIENCE-GUARDED: only appends when the session's audience matches `audience`. A mismatch
        (e.g. the asker toggled clinician→patient mid-thread) returns False, so the caller saves a
        FRESH session instead of corrupting a thread that mixes audiences."""
        await self._ensure()
        pool = await self._get_pool()
        async with pool.acquire() as conn:
            res = await conn.execute(
                "UPDATE noesis_research_session SET thread = thread || $3::jsonb "
                "WHERE id=$1 AND vertical=$2 AND NOT deleted AND audience=$4",
                session_id, self._vertical, json.dumps([turn]), (audience or "clinician"))
        return res.endswith("1")

    async def save_layman(self, session_id: str, text: str) -> bool:
        await self._ensure()
        pool = await self._get_pool()
        async with pool.acquire() as conn:
            res = await conn.execute(
                "UPDATE noesis_research_session SET layman_answer=$3 WHERE id=$1 AND vertical=$2",
                session_id, self._vertical, text)
        return res.endswith("1")

    async def soft_delete(self, session_id: str) -> bool:
        await self._ensure()
        pool = await self._get_pool()
        async with pool.acquire() as conn:
            res = await conn.execute(
                "UPDATE noesis_research_session SET deleted=TRUE WHERE id=$1 AND vertical=$2",
                session_id, self._vertical)
        return res.endswith("1")

    async def attach_video(self, session_id: str, *, filename: str, title: str,
                           duration: float) -> bool:
        await self._ensure()
        pool = await self._get_pool()
        async with pool.acquire() as conn:
            res = await conn.execute(
                """UPDATE noesis_research_session
                   SET video_filename=$3, video_title=$4, video_duration=$5
                   WHERE id=$1 AND vertical=$2""",
                session_id, self._vertical, filename, title, duration)
        return res.endswith("1")   # "UPDATE 1" when a row matched

    async def list(self, *, tenant_id: str, limit: int = 50,
                   q: str | None = None, audience: str | None = None) -> list[dict[str, Any]]:
        await self._ensure()
        pool = await self._get_pool()
        # optional full-text-ish search over the question + asker (name/email)
        where = "vertical=$1 AND tenant_id=$2 AND NOT deleted"
        params: list[Any] = [self._vertical, tenant_id]
        if q and q.strip():
            params.append(f"%{q.strip()}%")
            where += (f" AND (question ILIKE ${len(params)} OR user_name ILIKE ${len(params)}"
                      f" OR user_email ILIKE ${len(params)})")
        if audience in ("clinician", "patient"):
            params.append(audience)
            where += f" AND audience=${len(params)}"
        params.append(limit)
        async with pool.acquire() as conn:
            rows = await conn.fetch(
                f"""SELECT id, question, grounded, video_filename, user_name, user_email,
                           jsonb_array_length(attachments) AS n_attach, audience, created_at
                    FROM noesis_research_session
                    WHERE {where} ORDER BY created_at DESC LIMIT ${len(params)}""",
                *params)
        return [{
            "id": r["id"], "question": r["question"], "grounded": r["grounded"],
            "has_video": bool(r["video_filename"]), "n_attach": r["n_attach"] or 0,
            "user_name": r["user_name"], "user_email": r["user_email"],
            "audience": r["audience"] or "clinician",
            "created_at": r["created_at"].isoformat(),
        } for r in rows]

    async def list_videos(self, *, tenant_id: str, limit: int = 200) -> list[dict[str, Any]]:
        """All sessions that have a briefing video (for the video catalogue)."""
        await self._ensure()
        pool = await self._get_pool()
        async with pool.acquire() as conn:
            rows = await conn.fetch(
                """SELECT id, question, video_filename, video_title, video_duration,
                          user_name, user_email, created_at
                   FROM noesis_research_session
                   WHERE vertical=$1 AND tenant_id=$2 AND NOT deleted AND video_filename IS NOT NULL
                   ORDER BY created_at DESC LIMIT $3""",
                self._vertical, tenant_id, limit)
        return [{
            "id": r["id"], "question": r["question"],
            "video_filename": r["video_filename"], "video_title": r["video_title"],
            "video_duration": r["video_duration"],
            "user_name": r["user_name"], "user_email": r["user_email"],
            "created_at": r["created_at"].isoformat(),
        } for r in rows]

    async def get(self, session_id: str) -> dict[str, Any] | None:
        await self._ensure()
        pool = await self._get_pool()
        async with pool.acquire() as conn:
            r = await conn.fetchrow(
                "SELECT * FROM noesis_research_session WHERE id=$1 AND vertical=$2 AND NOT deleted",
                session_id, self._vertical)
        if r is None:
            return None
        # asyncpg returns jsonb columns as text (no codec set) — decode them here.
        def _j(v, default):
            if v is None:
                return default
            return json.loads(v) if isinstance(v, str) else v
        return {
            "id": r["id"], "tenant_id": r["tenant_id"], "workspace_id": r["workspace_id"],
            "question": r["question"], "answer": r["answer"], "grounded": r["grounded"],
            "claims": _j(r["claims"], []), "source_stats": _j(r["source_stats"], {}),
            "coverage_gaps": _j(r["coverage_gaps"], []), "rejected": r["rejected"],
            "sources": _j(r["sources"], []),
            "video_filename": r["video_filename"], "video_title": r["video_title"],
            "video_duration": r["video_duration"],
            "user_name": r["user_name"], "user_email": r["user_email"],
            "visual_observation": r["visual_observation"],
            "attachments": _j(r["attachments"], []),
            "layman_answer": r["layman_answer"],
            "thread": _j(r["thread"], []),
            "audience": r["audience"] or "clinician",
            "created_at": r["created_at"].isoformat(),
        }
