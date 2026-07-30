"""PostgresRetrievalSource — the decided production backend (pgvector + tsvector).

Division of labor (panel decision): the DB does the expensive, scalable parts —
tenant/workspace/facet HARD FILTERS (JSONB `facets @>`/`->>`) and CANDIDATE
GENERATION (pgvector HNSW ANN + tsvector lexical prefilter). The shared,
already-tested `rank_candidates` (BM25 + dense + RRF + signal) ranks the pool, so
this source ranks identically to the in-memory reference. asyncpg is an optional
dep (lazy import); nothing here names a domain noun.

Provenance loader note: verification always runs over blocks just retrieved this
request, so `make_block_loader` reads a per-search cache keyed by
(tenant, document_id, block_id) — sync, no re-query, and cross-tenant-safe
(only the querying tenant's blocks are ever cached).
"""
from __future__ import annotations

from noesis_kernel.contract.dto import (
    BlockHit,
    Capability,
    FacetFilter,
    Locator,
    RetrievalRequest,
)
from noesis_kernel.retrieval.rank import Candidate, rank_candidates
from noesis_kernel.retrieval.scoring import tokens as _tokens

DDL = """
CREATE EXTENSION IF NOT EXISTS vector;
CREATE TABLE IF NOT EXISTS {table} (
    tenant_id       text        NOT NULL,
    workspace_id    text,
    document_id     text        NOT NULL,
    block_id        text        NOT NULL,
    text            text        NOT NULL,
    tsv             tsvector    GENERATED ALWAYS AS (to_tsvector('english', text)) STORED,
    embedding       vector({dim}),
    facets          jsonb       NOT NULL DEFAULT '{{}}'::jsonb,
    document_title  text        NOT NULL DEFAULT '',
    content_type    text        NOT NULL DEFAULT '',
    source_key      text        NOT NULL DEFAULT '',
    PRIMARY KEY (tenant_id, document_id, block_id)
);
CREATE INDEX IF NOT EXISTS {table}_facets_gin ON {table} USING gin (facets);
CREATE INDEX IF NOT EXISTS {table}_tsv_gin    ON {table} USING gin (tsv);
CREATE INDEX IF NOT EXISTS {table}_emb_hnsw   ON {table} USING hnsw (embedding vector_cosine_ops);
"""


class PostgresRetrievalSource:
    def __init__(self, dsn: str, *, key: str = "postgres", dim: int = 1536,
                 table: str = "rs_block", covers: FacetFilter | None = None):
        self.key = key
        self._dsn = dsn
        self._dim = dim
        self._table = table
        self._covers = covers or {}
        self._pool = None
        self._cache: dict[tuple[str, str, str], str] = {}

    # --- lifecycle ---
    async def _get_pool(self):
        if self._pool is None:
            import asyncpg
            from pgvector.asyncpg import register_vector

            async def _init(conn):
                await register_vector(conn)

            self._pool = await asyncpg.create_pool(self._dsn, init=_init, min_size=1, max_size=4)
        return self._pool

    async def ensure_schema(self) -> None:
        pool = await self._get_pool()
        async with pool.acquire() as conn:
            await conn.execute(DDL.format(table=self._table, dim=self._dim))

    async def close(self) -> None:
        if self._pool is not None:
            await self._pool.close()
            self._pool = None

    async def upsert_block(self, *, tenant_id: str, document_id: str, block_id: str,
                           text: str, embedding: list[float] | None = None,
                           facets: dict | None = None, workspace_id: str | None = None,
                           document_title: str = "", content_type: str = "",
                           source_key: str = "") -> None:
        import json
        pool = await self._get_pool()
        async with pool.acquire() as conn:
            await conn.execute(
                f"""INSERT INTO {self._table}
                    (tenant_id, workspace_id, document_id, block_id, text, embedding,
                     facets, document_title, content_type, source_key)
                    VALUES ($1,$2,$3,$4,$5,$6,$7::jsonb,$8,$9,$10)
                    ON CONFLICT (tenant_id, document_id, block_id) DO UPDATE
                    SET text=EXCLUDED.text, embedding=EXCLUDED.embedding,
                        facets=EXCLUDED.facets""",
                tenant_id, workspace_id, document_id, block_id, text, embedding,
                json.dumps(facets or {}), document_title, content_type, source_key,
            )

    # --- port ---
    def capabilities(self) -> frozenset[Capability]:
        return frozenset({Capability.RETRIEVAL, Capability.PRECISION})

    def covers(self) -> FacetFilter:
        return dict(self._covers)

    def make_block_loader(self, tenant_id: str, workspace_id: str | None = None):
        def _load(document_id: str, block_id: str) -> str | None:
            return self._cache.get((tenant_id, document_id, block_id))
        return _load

    def _filter_sql(self, req: RetrievalRequest) -> tuple[str, list]:
        preds = ["tenant_id = $1"]
        params: list = [req.tenant_id]
        if req.workspace_id is None:
            preds.append("workspace_id IS NULL")
        else:
            params.append(req.workspace_id)
            preds.append(f"(workspace_id IS NULL OR workspace_id = ${len(params)})")
        for key, allowed in req.facets.items():
            vals = [allowed] if isinstance(allowed, str) else list(allowed)
            params.append(key)
            key_idx = len(params)
            params.append(vals)
            preds.append(f"(facets ->> ${key_idx}) = ANY(${len(params)})")
        return " AND ".join(preds), params

    async def search(self, req: RetrievalRequest) -> list[BlockHit]:
        pool = await self._get_pool()
        where, params = self._filter_sql(req)
        pool_n = req.fetch_pool
        qvec = req.query_embedding

        # candidate generation: lexical (tsv) ∪ dense (ANN), both within the filter.
        legs_sql: list[str] = []
        q_terms = _tokens(req.query)
        if q_terms:
            params.append(" | ".join(q_terms))          # OR query for recall (like factra)
            q_idx = len(params)
            legs_sql.append(
                f"SELECT block_id, document_id FROM f "
                f"WHERE tsv @@ to_tsquery('english', ${q_idx}) "
                f"ORDER BY ts_rank_cd(tsv, to_tsquery('english', ${q_idx})) DESC LIMIT {pool_n}")
        if qvec is not None:
            params.append(qvec)
            v_idx = len(params)
            legs_sql.append(
                f"SELECT block_id, document_id FROM f "
                f"WHERE embedding IS NOT NULL ORDER BY embedding <=> ${v_idx} LIMIT {pool_n}")
        if not legs_sql:
            return []
        cand_union = " UNION ".join(f"({s})" for s in legs_sql)
        sql = f"""
            WITH f AS (SELECT * FROM {self._table} WHERE {where}),
                 cand AS ({cand_union})
            SELECT f.block_id, f.document_id, f.text, f.embedding, f.facets,
                   f.document_title, f.content_type, f.source_key
            FROM f JOIN cand USING (block_id, document_id)
        """
        async with pool.acquire() as conn:
            rows = await conn.fetch(sql, *params)

        import json
        cands: list[Candidate] = []
        for r in rows:
            self._cache[(req.tenant_id, r["document_id"], r["block_id"])] = r["text"]
            raw = r["embedding"]
            if raw is None:
                emb = ()
            elif hasattr(raw, "to_list"):        # pgvector.Vector
                emb = tuple(raw.to_list())
            else:                                # numpy array / sequence
                emb = tuple(float(x) for x in raw)
            facets = r["facets"] if isinstance(r["facets"], dict) else json.loads(r["facets"])
            cands.append(Candidate(
                block_id=r["block_id"], document_id=r["document_id"], text=r["text"],
                embedding=emb, facets=facets,
                locator=Locator("block_span", r["document_id"], {"block_id": r["block_id"]}),
                document_title=r["document_title"], content_type=r["content_type"],
                source_key=r["source_key"],
            ))
        return rank_candidates(req.query, qvec, cands, k=req.k, fetch_pool=req.fetch_pool)
