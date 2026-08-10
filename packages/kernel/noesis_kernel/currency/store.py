"""CurrencyStore — the auditable change-event ledger + derived block stamps.

Design (spec v2, amendments A2/A4):
- `noesis_change_event` is the SOURCE OF TRUTH. Block facet stamps (`superseded_by`,
  `retracted`) are a derived cache: re-ingest overwrites facets, so stamps are re-derivable
  at any time from the approved events (`apply_stamps` is idempotent — run it after ingests).
- Events are idempotent on (relation, old, new) and carry a status:
    shadow   — recorded, no effect (future LLM-detected events start here);
    approved — stamps applied; declared (curator) lineage starts here (A4: high-confidence only);
    retracted_event — a mistake, undone (stamps removed, event kept for audit).
- Stamps DEMOTE (or, for retracted sources, exclude) — they never delete: the old edition is the
  evidence a change brief cites, and may be the only source for an unrevised topic.
"""
from __future__ import annotations

import hashlib
import json

RELATIONS = ("superseded_by", "retracted", "amended_by", "clarified_by")

_DDL = """
CREATE TABLE IF NOT EXISTS noesis_change_event (
    id               text PRIMARY KEY,
    relation         text NOT NULL,
    old_document_id  text NOT NULL DEFAULT '',
    new_document_id  text NOT NULL DEFAULT '',
    subjects         jsonb NOT NULL DEFAULT '[]'::jsonb,
    materiality      text NOT NULL DEFAULT 'major',
    confidence       text NOT NULL DEFAULT 'declared',
    brief_md         text NOT NULL DEFAULT '',
    brief_claims     jsonb NOT NULL DEFAULT '[]'::jsonb,
    status           text NOT NULL DEFAULT 'shadow',
    created_at       timestamptz NOT NULL DEFAULT now(),
    updated_at       timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS noesis_change_event_status ON noesis_change_event (status, created_at DESC);
"""


def _event_id(relation: str, old: str, new: str) -> str:
    return hashlib.sha256(f"{relation}|{old}|{new}".encode()).hexdigest()[:32]


class CurrencyStore:
    def __init__(self, dsn: str, *, block_table: str = "rs_block"):
        self._dsn = dsn
        self._block_table = block_table
        self._pool = None

    async def _get_pool(self):
        if self._pool is None:
            import asyncpg
            self._pool = await asyncpg.create_pool(self._dsn, min_size=1, max_size=3)
            async with self._pool.acquire() as conn:
                await conn.execute(_DDL)
        return self._pool

    async def close(self) -> None:
        if self._pool is not None:
            await self._pool.close()
            self._pool = None

    # ---- events (source of truth) -------------------------------------------------------------

    async def record(self, *, relation: str, old_document_id: str = "", new_document_id: str = "",
                     subjects: list[str] | None = None, materiality: str = "major",
                     confidence: str = "declared", status: str = "shadow") -> str:
        """Idempotent on (relation, old, new): re-recording NEVER downgrades an existing event's
        status or overwrites its audit trail — a swept declared relation that was manually
        retracted stays retracted. Returns the event id."""
        if relation not in RELATIONS:
            raise ValueError(f"unknown relation {relation!r}")
        eid = _event_id(relation, old_document_id, new_document_id)
        pool = await self._get_pool()
        async with pool.acquire() as conn:
            await conn.execute(
                """INSERT INTO noesis_change_event
                     (id, relation, old_document_id, new_document_id, subjects,
                      materiality, confidence, status)
                   VALUES ($1,$2,$3,$4,$5::jsonb,$6,$7,$8)
                   ON CONFLICT (id) DO NOTHING""",
                eid, relation, old_document_id, new_document_id,
                json.dumps(list(subjects or [])), materiality, confidence, status)
        return eid

    async def list_events(self, *, status: str | None = None, limit: int = 100) -> list[dict]:
        pool = await self._get_pool()
        where = "WHERE status=$2" if status else ""
        args = [min(limit, 500)] + ([status] if status else [])
        async with pool.acquire() as conn:
            rows = await conn.fetch(
                f"""SELECT id, relation, old_document_id, new_document_id, subjects, materiality,
                           confidence, brief_md, status, created_at, updated_at
                    FROM noesis_change_event {where}
                    ORDER BY created_at DESC LIMIT $1""", *args)
        out = []
        for r in rows:
            d = dict(r)
            d["subjects"] = json.loads(d["subjects"]) if isinstance(d["subjects"], str) else d["subjects"]
            d["created_at"] = d["created_at"].isoformat()
            d["updated_at"] = d["updated_at"].isoformat()
            out.append(d)
        return out

    async def set_status(self, event_id: str, status: str) -> bool:
        """approve | retract an event. Retraction un-stamps its blocks (kept for audit)."""
        if status not in ("shadow", "approved", "retracted_event"):
            raise ValueError(f"bad status {status!r}")
        pool = await self._get_pool()
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                "UPDATE noesis_change_event SET status=$2, updated_at=now() WHERE id=$1 "
                "RETURNING relation, old_document_id, new_document_id", event_id, status)
        if row is None:
            return False
        if status == "approved":
            await self._stamp(row["relation"], row["old_document_id"], row["new_document_id"])
        elif status == "retracted_event":
            await self._unstamp(row["relation"], row["old_document_id"])
        return True

    # ---- derived stamps (re-derivable cache on the block table) --------------------------------

    async def apply_stamps(self) -> int:
        """Idempotently (re-)derive block stamps from ALL approved events — run after any ingest
        (re-ingest overwrites facets, erasing stamps; the ledger restores them). Returns events
        applied."""
        pool = await self._get_pool()
        async with pool.acquire() as conn:
            rows = await conn.fetch(
                "SELECT relation, old_document_id, new_document_id FROM noesis_change_event "
                "WHERE status='approved'")
        for r in rows:
            await self._stamp(r["relation"], r["old_document_id"], r["new_document_id"])
        return len(rows)

    async def _stamp(self, relation: str, old_doc: str, new_doc: str) -> None:
        if not old_doc:
            return
        pool = await self._get_pool()
        patch = json.dumps({"retracted": "true"} if relation == "retracted"
                           else {relation: new_doc})
        async with pool.acquire() as conn:
            await conn.execute(
                f"UPDATE {self._block_table} SET facets = facets || $2::jsonb WHERE document_id=$1",
                old_doc, patch)

    async def _unstamp(self, relation: str, old_doc: str) -> None:
        if not old_doc:
            return
        key = "retracted" if relation == "retracted" else relation
        pool = await self._get_pool()
        async with pool.acquire() as conn:
            await conn.execute(
                f"UPDATE {self._block_table} SET facets = facets - $2 WHERE document_id=$1",
                old_doc, key)

    async def list_document_ids(self, *, prefix: str, limit: int = 50000) -> list[str]:
        """Distinct corpus document ids under a source prefix (e.g. 'europepmc:') — the input a
        detector sweeps. Structural read on the block table."""
        pool = await self._get_pool()
        async with pool.acquire() as conn:
            rows = await conn.fetch(
                f"""SELECT DISTINCT document_id FROM {self._block_table}
                    WHERE document_id LIKE $1 LIMIT $2""", prefix + "%", limit)
        return [r["document_id"] for r in rows]

    # ---- P0 sweep: curator-declared lineage → approved events + stamps -------------------------

    async def sweep_declared(self, lineage: list[dict]) -> dict:
        """Record vertical-declared relations (highest confidence → status approved, A4) and apply
        stamps. Idempotent; safe to run on every ingest completion or admin trigger."""
        recorded = 0
        for rel in lineage or []:
            relation = rel.get("relation", "")
            if relation not in RELATIONS:
                continue
            await self.record(
                relation=relation,
                old_document_id=rel.get("old_document_id", ""),
                new_document_id=rel.get("new_document_id", ""),
                subjects=rel.get("subjects") or [],
                confidence="declared", status="shadow")   # record first; approve applies stamps
            eid = _event_id(relation, rel.get("old_document_id", ""), rel.get("new_document_id", ""))
            # approve ONLY if still shadow (a manually-retracted event stays retracted)
            pool = await self._get_pool()
            async with pool.acquire() as conn:
                row = await conn.fetchrow(
                    "SELECT status FROM noesis_change_event WHERE id=$1", eid)
            if row and row["status"] == "shadow":
                await self.set_status(eid, "approved")
            recorded += 1
        stamped = await self.apply_stamps()
        return {"declared": recorded, "stamps_applied": stamped}
