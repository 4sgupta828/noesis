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
    created_at     TIMESTAMPTZ NOT NULL DEFAULT now()
);
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
                   coverage_gaps: list[str], rejected: int, sources: list[str] | None) -> str:
        await self._ensure()
        sid = uuid.uuid4().hex
        pool = await self._get_pool()
        async with pool.acquire() as conn:
            await conn.execute(
                """INSERT INTO noesis_research_session
                   (id, vertical, tenant_id, workspace_id, question, answer, grounded, claims,
                    source_stats, coverage_gaps, rejected, sources)
                   VALUES ($1,$2,$3,$4,$5,$6,$7,$8::jsonb,$9::jsonb,$10::jsonb,$11,$12::jsonb)""",
                sid, self._vertical, tenant_id, workspace_id, question, answer, grounded,
                json.dumps(claims), json.dumps(source_stats), json.dumps(coverage_gaps),
                rejected, json.dumps(sources or []),
            )
        return sid

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

    async def list(self, *, tenant_id: str, limit: int = 50) -> list[dict[str, Any]]:
        await self._ensure()
        pool = await self._get_pool()
        async with pool.acquire() as conn:
            rows = await conn.fetch(
                """SELECT id, question, grounded, video_filename, created_at
                   FROM noesis_research_session
                   WHERE vertical=$1 AND tenant_id=$2 ORDER BY created_at DESC LIMIT $3""",
                self._vertical, tenant_id, limit)
        return [{
            "id": r["id"], "question": r["question"], "grounded": r["grounded"],
            "has_video": bool(r["video_filename"]),
            "created_at": r["created_at"].isoformat(),
        } for r in rows]

    async def get(self, session_id: str) -> dict[str, Any] | None:
        await self._ensure()
        pool = await self._get_pool()
        async with pool.acquire() as conn:
            r = await conn.fetchrow(
                "SELECT * FROM noesis_research_session WHERE id=$1 AND vertical=$2",
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
            "created_at": r["created_at"].isoformat(),
        }
