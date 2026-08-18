"""Historical Cases persistence — generated noesis answers + doctor evaluations.

App-level (not kernel), vertical-isolated, backed by the same Postgres as the corpus/sessions
(NOESIS_CORPUS_DSN). Case DEFINITIONS are static curated content (historical_cases.py); this store
holds only the mutable per-case artifacts:

  * noesis_case_run  — a noesis-generated answer for a case (append-only; latest = current).
  * noesis_case_eval — a clinician's structured rubric score for a case (append-only; latest = current).

Schema is ensured lazily via CREATE TABLE IF NOT EXISTS (same no-Alembic pattern as SessionStore).
All writes are best-effort at the call site; a persistence failure must never break a response.
"""
from __future__ import annotations

import json
import uuid

_DDL = """
CREATE TABLE IF NOT EXISTS noesis_case_run (
    id           TEXT PRIMARY KEY,
    vertical     TEXT NOT NULL,
    case_id      TEXT NOT NULL,
    answer       TEXT NOT NULL DEFAULT '',
    grounded     BOOLEAN NOT NULL DEFAULT FALSE,
    citations    JSONB NOT NULL DEFAULT '[]'::jsonb,
    payload      JSONB NOT NULL DEFAULT '{}'::jsonb,   -- extra answer fields (charts, reasoning, gaps, ...)
    engine       TEXT NOT NULL DEFAULT '',
    error        TEXT,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_ncr_vertical_case_created
    ON noesis_case_run (vertical, case_id, created_at DESC);

CREATE TABLE IF NOT EXISTS noesis_case_eval (
    id             TEXT PRIMARY KEY,
    vertical       TEXT NOT NULL,
    case_id        TEXT NOT NULL,
    run_id         TEXT,
    accuracy       INTEGER,
    completeness   INTEGER,
    safety         INTEGER,
    decision_useful INTEGER,
    verdict        TEXT NOT NULL DEFAULT '',   -- accept | revise | reject
    notes          TEXT NOT NULL DEFAULT '',
    reviewer       TEXT NOT NULL DEFAULT '',
    created_at     TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_nce_vertical_case_created
    ON noesis_case_eval (vertical, case_id, created_at DESC);
"""


class CaseStore:
    """Async Postgres store for Historical-Cases runs + evaluations, BOUND to one vertical."""

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

    # ---- runs (generated answers) ----
    async def save_run(self, *, case_id: str, answer: str, grounded: bool,
                       citations: list[dict] | None = None, payload: dict | None = None,
                       engine: str = "", error: str | None = None) -> str:
        await self._ensure()
        rid = uuid.uuid4().hex
        pool = await self._get_pool()
        async with pool.acquire() as conn:
            await conn.execute(
                "INSERT INTO noesis_case_run (id, vertical, case_id, answer, grounded, citations, "
                "payload, engine, error) VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9)",
                rid, self._vertical, case_id, answer or "", bool(grounded),
                json.dumps(citations or []), json.dumps(payload or {}), engine or "", error)
        return rid

    async def latest_runs(self) -> dict[str, dict]:
        """Most-recent run per case_id → {case_id: run_dict}."""
        await self._ensure()
        pool = await self._get_pool()
        async with pool.acquire() as conn:
            rows = await conn.fetch(
                "SELECT DISTINCT ON (case_id) case_id, id, answer, grounded, citations, payload, "
                "engine, error, created_at FROM noesis_case_run WHERE vertical=$1 "
                "ORDER BY case_id, created_at DESC", self._vertical)
        out: dict[str, dict] = {}
        for r in rows:
            out[r["case_id"]] = {
                "run_id": r["id"], "answer": r["answer"], "grounded": r["grounded"],
                "citations": json.loads(r["citations"]) if isinstance(r["citations"], str) else (r["citations"] or []),
                "payload": json.loads(r["payload"]) if isinstance(r["payload"], str) else (r["payload"] or {}),
                "engine": r["engine"], "error": r["error"],
                "generated_at": r["created_at"].isoformat() if r["created_at"] else None}
        return out

    # ---- evaluations (doctor rubric) ----
    async def save_eval(self, *, case_id: str, run_id: str | None, accuracy: int | None,
                        completeness: int | None, safety: int | None, decision_useful: int | None,
                        verdict: str, notes: str, reviewer: str) -> str:
        await self._ensure()
        eid = uuid.uuid4().hex
        pool = await self._get_pool()
        async with pool.acquire() as conn:
            await conn.execute(
                "INSERT INTO noesis_case_eval (id, vertical, case_id, run_id, accuracy, completeness, "
                "safety, decision_useful, verdict, notes, reviewer) "
                "VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11)",
                eid, self._vertical, case_id, run_id, accuracy, completeness, safety,
                decision_useful, (verdict or "")[:16], (notes or "")[:4000], (reviewer or "")[:120])
        return eid

    async def latest_evals(self) -> dict[str, dict]:
        """Most-recent evaluation per case_id → {case_id: eval_dict}."""
        await self._ensure()
        pool = await self._get_pool()
        async with pool.acquire() as conn:
            rows = await conn.fetch(
                "SELECT DISTINCT ON (case_id) case_id, id, run_id, accuracy, completeness, safety, "
                "decision_useful, verdict, notes, reviewer, created_at FROM noesis_case_eval "
                "WHERE vertical=$1 ORDER BY case_id, created_at DESC", self._vertical)
        out: dict[str, dict] = {}
        for r in rows:
            out[r["case_id"]] = {
                "eval_id": r["id"], "run_id": r["run_id"], "accuracy": r["accuracy"],
                "completeness": r["completeness"], "safety": r["safety"],
                "decision_useful": r["decision_useful"], "verdict": r["verdict"],
                "notes": r["notes"], "reviewer": r["reviewer"],
                "evaluated_at": r["created_at"].isoformat() if r["created_at"] else None}
        return out
