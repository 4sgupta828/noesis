"""PeopleStore — the kernel-generic ENTITY INVENTORY (Frontier People / spec E-series).

Domain-neutral: rows are professionals of ANY vertical (physicians now; lawyers/engineers
later) keyed by NATURAL registry ids (E-2: NPI / NMC reg no — relocation must never orphan
metrics). Write ethos mirrors the graph store (status lifecycle, per-field provenance,
append-only metrics, never-resurrect); READS are INDEXED SQL ONLY (E-5: the graph's
in-process snapshot caps ~20k rows — banned here at 1-2M entities).

Provenance/honesty (E-1/E-4): every metric carries source + period + retrieved_at and a
label chosen by the CALLER (e.g. "Original Medicare Part B claims, 2023" — never "patients
seen"). `discipline_status` defaults 'not_collected' (P0 is ADMIN-ONLY until P1 board
actions land). Suppression = status flip (right-of-reply), never deletion.
"""
from __future__ import annotations

_DDL = """
CREATE TABLE IF NOT EXISTS noesis_entity (
    entity_id     text PRIMARY KEY,            -- NATURAL key: 'npi:1234567890' | 'nmc:...'
    vertical      text NOT NULL DEFAULT 'medical',
    kind          text NOT NULL DEFAULT 'physician',
    name          text NOT NULL,
    taxonomy      text NOT NULL DEFAULT '',    -- vertical specialty code (NUCC for medical)
    specialty     text NOT NULL DEFAULT '',    -- human specialty label (vertical-mapped)
    credential    text NOT NULL DEFAULT '',    -- MD/DO/MBBS…
    org           text NOT NULL DEFAULT '',
    city          text NOT NULL DEFAULT '',
    state         text NOT NULL DEFAULT '',
    country       text NOT NULL DEFAULT 'US',
    license_status    text NOT NULL DEFAULT 'not_collected',   -- E-1 first-class
    board_certified   text NOT NULL DEFAULT 'not_collected',
    discipline_status text NOT NULL DEFAULT 'not_collected',
    status        text NOT NULL DEFAULT 'active',  -- active | suppressed | retired | deceased
    source        text NOT NULL DEFAULT '',        -- spine source (e.g. 'nppes')
    valid_as_of   date,                            -- the SOURCE file's vintage (staleness model)
    retrieved_at  timestamptz NOT NULL DEFAULT now(),
    updated_at    timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS ne_spec_geo ON noesis_entity (vertical, specialty, country, state);
CREATE INDEX IF NOT EXISTS ne_taxonomy ON noesis_entity (taxonomy);
CREATE INDEX IF NOT EXISTS ne_name ON noesis_entity (lower(name));
CREATE TABLE IF NOT EXISTS noesis_entity_metric (
    entity_id    text NOT NULL,
    metric_key   text NOT NULL,               -- e.g. 'medicare_partb_services'
    metric_label text NOT NULL DEFAULT '',    -- E-4 honest display label incl. skew
    value        double precision NOT NULL,
    unit         text NOT NULL DEFAULT '',
    period       text NOT NULL DEFAULT '',    -- e.g. '2023'
    detail       text NOT NULL DEFAULT '',    -- e.g. HCPCS family for per-procedure rollups
    source       text NOT NULL,
    retrieved_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (entity_id, metric_key, period, detail)
);
CREATE INDEX IF NOT EXISTS nem_metric ON noesis_entity_metric (metric_key, period, value DESC);
CREATE TABLE IF NOT EXISTS noesis_entity_contact (
    entity_id    text NOT NULL,
    kind         text NOT NULL,               -- phone | website | email
    value        text NOT NULL,
    source       text NOT NULL,
    published_by_subject boolean NOT NULL DEFAULT false,
    retrieved_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (entity_id, kind, value)
);
"""


class PeopleStore:
    def __init__(self, dsn: str):
        self._dsn = dsn
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

    async def set_status(self, entity_id: str, status: str) -> bool:
        """Suppression/right-of-reply and lifecycle — flip, never delete (E-0)."""
        if status not in ("active", "suppressed", "retired", "deceased"):
            raise ValueError(f"bad status {status!r}")
        pool = await self._get_pool()
        async with pool.acquire() as conn:
            res = await conn.execute(
                "UPDATE noesis_entity SET status=$2, updated_at=now() WHERE entity_id=$1",
                entity_id, status)
        return res == "UPDATE 1"

    async def search(self, *, specialty: str = "", taxonomy: str = "", state: str = "",
                     country: str = "", name: str = "", metric_key: str = "",
                     metric_period: str = "", sort_metric: str = "",
                     limit: int = 50) -> list[dict]:
        """INDEXED SQL facet search (E-5). NO default ranking (E-3): rows come back in
        NEUTRAL name order unless the CALLER explicitly passes sort_metric — the user must
        actively choose the sort key; suppressed/retired/deceased are always excluded."""
        pool = await self._get_pool()
        preds, args = ["e.status = 'active'"], []

        def _p(clause, val):
            args.append(val)
            preds.append(clause.format(n=len(args)))
        if specialty:
            _p("e.specialty ILIKE ${n}", f"%{specialty}%")
        if taxonomy:
            _p("e.taxonomy = ${n}", taxonomy)
        if state:
            _p("e.state = ${n}", state.upper())
        if country:
            _p("e.country = ${n}", country.upper())
        if name:
            _p("lower(e.name) LIKE ${n}", f"%{name.lower()}%")
        join, order = "", "ORDER BY e.name"
        if sort_metric:
            args.append(sort_metric)
            k = len(args)
            args.append(metric_period or "")
            join = (f"LEFT JOIN LATERAL (SELECT sum(value) AS mv FROM noesis_entity_metric m "
                    f"WHERE m.entity_id = e.entity_id AND m.metric_key = ${k} "
                    f"AND (${k+1} = '' OR m.period = ${k+1})) mt ON true")
            order = "ORDER BY mt.mv DESC NULLS LAST, e.name"
        elif metric_key:
            args.append(metric_key)
            join = (f"JOIN LATERAL (SELECT 1 FROM noesis_entity_metric m WHERE "
                    f"m.entity_id = e.entity_id AND m.metric_key = ${len(args)} LIMIT 1) mx ON true")
        args.append(min(max(limit, 1), 200))
        sql = (f"SELECT e.*{', mt.mv AS sort_value' if sort_metric else ''} FROM noesis_entity e "
               f"{join} WHERE {' AND '.join(preds)} {order} LIMIT ${len(args)}")
        async with pool.acquire() as conn:
            rows = await conn.fetch(sql, *args)
        out = []
        for r in rows:
            d = dict(r)
            for k in ("retrieved_at", "updated_at"):
                d[k] = d[k].isoformat()
            d["valid_as_of"] = d["valid_as_of"].isoformat() if d["valid_as_of"] else None
            out.append(d)
        return out

    async def entity(self, entity_id: str) -> dict | None:
        """Full profile: entity + ALL metrics (with per-field provenance) + contacts."""
        pool = await self._get_pool()
        async with pool.acquire() as conn:
            e = await conn.fetchrow("SELECT * FROM noesis_entity WHERE entity_id=$1", entity_id)
            if not e:
                return None
            ms = await conn.fetch(
                "SELECT metric_key, metric_label, value, unit, period, detail, source, "
                "retrieved_at FROM noesis_entity_metric WHERE entity_id=$1 "
                "ORDER BY metric_key, period DESC", entity_id)
            cs = await conn.fetch(
                "SELECT kind, value, source, published_by_subject FROM noesis_entity_contact "
                "WHERE entity_id=$1", entity_id)
        d = dict(e)
        for k in ("retrieved_at", "updated_at"):
            d[k] = d[k].isoformat()
        d["valid_as_of"] = d["valid_as_of"].isoformat() if d["valid_as_of"] else None
        d["metrics"] = [{**dict(m), "retrieved_at": m["retrieved_at"].isoformat()} for m in ms]
        d["contacts"] = [dict(c) for c in cs]
        return d

    async def stats(self) -> dict:
        pool = await self._get_pool()
        async with pool.acquire() as conn:
            n = await conn.fetchrow(
                "SELECT count(*) AS entities, count(DISTINCT specialty) AS specialties, "
                "count(*) FILTER (WHERE status != 'active') AS non_active FROM noesis_entity")
            m = await conn.fetchval("SELECT count(*) FROM noesis_entity_metric")
            c = await conn.fetchval("SELECT count(*) FROM noesis_entity_contact")
        return {**dict(n), "metrics": m, "contacts": c}
