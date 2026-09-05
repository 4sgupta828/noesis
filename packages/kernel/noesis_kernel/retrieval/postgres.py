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

import json

from noesis_kernel.contract.dto import (
    BlockHit,
    Capability,
    FacetFilter,
    Locator,
    RetrievalRequest,
)
from noesis_kernel.retrieval.rank import Candidate, rank_candidates
from noesis_kernel.retrieval.scoring import tokens as _tokens

# ---- lexical candidate planning (document-frequency driven) -------------------------------------
# Postgres cannot rank a full-text match from the GIN index (no RUM/BM25 index on the managed
# image), so `WHERE tsv @@ q ORDER BY ts_rank_cd(...) LIMIT n` ranks EVERY matching row. With an
# any-term OR over a 1.5M-block corpus that was a full-table scan per search (108 s in prod). The
# principled fix is the one every inverted-index engine applies: RARE terms select candidates
# (small postings), COMMON terms only contribute to ranking. Which terms are rare is not guessed
# from a word list — it comes from the planner's own lexeme statistics (pg_stats.most_common_elems
# for the tsv column, refreshed by ANALYZE), i.e. measured document frequency on THIS corpus.
_LEX_RARE_DF = 0.005        # a lexeme in ≤ 0.5% of blocks may SELECT candidates (≤ ~7.5k rows/term at 1.5M)
_LEX_TIMEOUT_MS = 12000     # any lexical query slower than this is skipped, never waited on (dense leg carries on)
_DF_REFRESH_S = 900         # lexeme-frequency table is re-read from pg_stats at most this often
import logging as _logging
_log = _logging.getLogger(__name__)


def _parse_pg_text_array(raw: str | None) -> list[str]:
    """Parse the text form of a Postgres array ('{a,b,"c d"}') — pg_stats.most_common_elems is
    `anyarray`, which asyncpg cannot decode, so it is fetched as text."""
    if not raw or len(raw) < 2 or raw == "{}":
        return []
    out: list[str] = []
    buf: list[str] = []
    quoted = escaped = False
    for ch in raw[1:-1]:
        if escaped:
            buf.append(ch); escaped = False
        elif ch == "\\":
            escaped = True
        elif ch == '"':
            quoted = not quoted
        elif ch == "," and not quoted:
            out.append("".join(buf)); buf = []
        else:
            buf.append(ch)
    out.append("".join(buf))
    return out


def plan_lexical(lexemes: list[str], df: dict[str, float], *, rare_df: float = _LEX_RARE_DF
                 ) -> tuple[list[str], str]:
    """Candidate-selection plan for the lexical leg.

    Returns (select_queries, rank_query): `select_queries` are tried IN ORDER until the candidate
    pool is full — each is a tsquery whose match set is small by construction; `rank_query` is the
    FULL query (every lexeme OR'ed) used only inside ts_rank_cd, so common terms still shape the
    order without ever driving a scan. Final ranking (BM25 + cosine fusion) happens in Python over
    the returned pool, so the SQL's only job is a good, bounded candidate set.

    - rare terms (df ≤ rare_df, or absent from the common-lexeme stats → rarer still) SELECT:
        1. all rare terms together (most specific);  2. any rare term (union of small postings).
    - if the query has NO rare term (all common), the intersection of ALL terms selects, then the
      intersection of the two least-common — never a single common term on its own.
    """
    lex = [l for i, l in enumerate(lexemes) if l and l not in lexemes[:i]]
    if not lex:
        return [], ""
    rank_q = " | ".join(lex)
    rare = [l for l in lex if df.get(l, 0.0) <= rare_df]
    plans: list[str] = []
    if rare:
        plans.append(" & ".join(rare))
        if len(rare) > 1:
            plans.append(" | ".join(rare))
    else:
        by_df = sorted(lex, key=lambda l: df.get(l, 0.0))
        plans.append(" & ".join(lex))
        if len(by_df) > 2:
            plans.append(" & ".join(by_df[:2]))
    return plans, rank_q


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
-- TIME AXIS (Evidence Pulse): when each block first landed — the primitive that makes corpus
-- deltas queryable over time ("what arrived on topic T in the last 30 days"). Additive; rows
-- ingested before the column exists stay NULL (= unknown, honestly excluded from windows).
-- NOTE: added WITHOUT a default, then default set separately — ADD COLUMN ... DEFAULT now()
-- BACKFILLS every existing row with the migration instant (Postgres fast-path), which stamped
-- the whole legacy corpus as "new today" (the saturated first coverage board). Two statements
-- keep pre-existing rows NULL while new inserts get now().
ALTER TABLE {table} ADD COLUMN IF NOT EXISTS created_at timestamptz;
ALTER TABLE {table} ALTER COLUMN created_at SET DEFAULT now();
CREATE INDEX IF NOT EXISTS {table}_created ON {table} (created_at DESC);
-- Planner statistics drive BOTH the query plans (bitmap vs seq scan) AND the lexical candidate
-- planner (lexeme document frequencies from pg_stats). Default autovacuum thresholds (10% of a
-- 1.5M-row table) let stats go stale for months; analyze after ~2% churn instead.
ALTER TABLE {table} SET (autovacuum_analyze_scale_factor = 0.02, autovacuum_analyze_threshold = 5000);
"""


# Pooler-safe single-writer: every block write takes this TRANSACTION-level advisory lock first, so
# concurrent ingest across replicas serializes on the write (one at a time) — eliminating the rs_block
# row/HNSW-index lock contention that aborted jobs with "canceling statement due to lock timeout". A
# transaction-level lock (not session-level) is REQUIRED because the corpus DSN routes through a
# transaction pooler, which releases session advisory locks between statements; a txn lock is held for
# the write transaction and released at commit, so it works through the pooler. Reads never take it.
_WRITE_LOCK_KEY = 5132101


class PostgresRetrievalSource:
    def __init__(self, dsn: str, *, key: str = "postgres", dim: int = 1536,
                 table: str = "rs_block", covers: FacetFilter | None = None,
                 currency_demote: bool = False):
        self.key = key
        self._dsn = dsn
        self._dim = dim
        self._table = table
        self._covers = covers or {}
        self._df: dict[str, float] = {}      # lexeme → fraction of blocks containing it (pg_stats)
        self._df_at: float = 0.0
        self._pool = None
        self._schema_ready = False
        self._cache: dict[tuple[str, str, str], str] = {}
        # Evidence Pulse C1 (flag-fed by the app): exclude retracted / demote superseded at retrieval
        self._currency_demote = currency_demote

    # --- lifecycle ---
    async def _get_pool(self):
        if self._pool is None:
            import asyncpg
            from pgvector.asyncpg import register_vector

            async def _init(conn):
                await register_vector(conn)
                # HNSW recall knob (default 40): raised so the now index-accelerated ANN leg keeps
                # recall close to the old exact brute-force scan. Cheap once the index is actually used.
                try:
                    await conn.execute("SET hnsw.ef_search = 100")
                except Exception:   # noqa: BLE001 — pre-pgvector-0.5 / setting absent: ignore
                    pass

            # lock_timeout: any statement WAITING for a lock (e.g. a concurrent ingest's brief
            # AccessExclusiveLock from a CREATE INDEX/ALTER, or an overlapping block upsert) aborts
            # after 30s instead of hanging FOREVER — a plain lock-wait never self-aborts the way a
            # deadlock does, so without this an ingest job could stay 'running' indefinitely and
            # head-of-line-block the whole queue. Safe for retrieval: SELECTs take ACCESS SHARE and
            # effectively never wait this long, so read paths are unaffected.
            self._pool = await asyncpg.create_pool(
                self._dsn, init=_init, min_size=1, max_size=8,
                server_settings={"lock_timeout": "30000"})
        return self._pool

    async def ensure_schema(self) -> None:
        # The DDL (CREATE TABLE / ALTER TABLE / CREATE INDEX) each takes an AccessExclusiveLock on the
        # corpus table. In prod the table ALREADY EXISTS, so running the DDL is pointless — yet with many
        # replica workers it made every worker contend for that exclusive lock at once (deadlocks, then
        # lock-timeout aborts once we added lock_timeout), so EVERY ingest job failed at the write step.
        # Fix: only run the DDL when the table is ABSENT (first-ever setup). When it exists, take just a
        # cheap ACCESS-SHARE read (to_regclass) and skip all DDL — no exclusive lock, no contention.
        # Schema changes are deliberate migrations, not per-boot DDL. Cached per process either way.
        if self._schema_ready:
            return
        pool = await self._get_pool()
        async with pool.acquire() as conn:
            exists = await conn.fetchval("SELECT to_regclass($1)", self._table)
            if exists is None:
                await conn.execute(DDL.format(table=self._table, dim=self._dim))
        self._schema_ready = True

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
            async with conn.transaction():   # serialize writers (pooler-safe txn advisory lock)
                await conn.execute("SELECT pg_advisory_xact_lock($1)", _WRITE_LOCK_KEY)
                await conn.execute(
                    f"""INSERT INTO {self._table}
                        (tenant_id, workspace_id, document_id, block_id, text, embedding,
                         facets, document_title, content_type, source_key)
                        VALUES ($1,$2,$3,$4,$5,$6,$7::jsonb,$8,$9,$10)
                        ON CONFLICT (tenant_id, document_id, block_id) DO UPDATE
                        SET text=EXCLUDED.text, embedding=EXCLUDED.embedding,
                            facets=EXCLUDED.facets, document_title=EXCLUDED.document_title,
                            content_type=EXCLUDED.content_type, source_key=EXCLUDED.source_key""",
                    tenant_id, workspace_id, document_id, block_id, text, embedding,
                    json.dumps(facets or {}), document_title, content_type, source_key,
                )

    async def upsert_blocks(self, rows: list[dict]) -> None:
        """Batch upsert many blocks in one round-trip (executemany). Each row dict:
        tenant_id, document_id, block_id, text, embedding, facets, workspace_id,
        document_title, content_type, source_key."""
        if not rows:
            return
        import json
        pool = await self._get_pool()
        args = [(
            r["tenant_id"], r.get("workspace_id"), r["document_id"], r["block_id"],
            r["text"], r.get("embedding"), json.dumps(r.get("facets") or {}),
            r.get("document_title", ""), r.get("content_type", ""), r.get("source_key", ""),
        ) for r in rows]
        async with pool.acquire() as conn:
            async with conn.transaction():   # serialize writers (pooler-safe txn advisory lock)
                await conn.execute("SELECT pg_advisory_xact_lock($1)", _WRITE_LOCK_KEY)
                await conn.executemany(
                    f"""INSERT INTO {self._table}
                        (tenant_id, workspace_id, document_id, block_id, text, embedding,
                         facets, document_title, content_type, source_key)
                        VALUES ($1,$2,$3,$4,$5,$6,$7::jsonb,$8,$9,$10)
                        ON CONFLICT (tenant_id, document_id, block_id) DO UPDATE
                        SET text=EXCLUDED.text, embedding=EXCLUDED.embedding,
                            facets=EXCLUDED.facets, document_title=EXCLUDED.document_title,
                            content_type=EXCLUDED.content_type, source_key=EXCLUDED.source_key""",
                    args,
                )

    async def delete_stale_blocks(self, *, tenant_id: str, document_id: str,
                                  keep_block_ids: list[str]) -> int:
        """CLEAN-REPLACE (Evidence Pulse A1): after re-ingesting a document, remove rows whose
        block_id is not in this ingest's key set. Block ids are content-addressed, so an edited
        document INSERTS its changed blocks while the old text's rows would otherwise linger
        forever — the mixed-edition corpus bug (one document silently serving both editions).
        Returns rows deleted."""
        pool = await self._get_pool()
        async with pool.acquire() as conn:
            async with conn.transaction():   # serialize writers (pooler-safe txn advisory lock)
                await conn.execute("SELECT pg_advisory_xact_lock($1)", _WRITE_LOCK_KEY)
                res = await conn.execute(
                    f"""DELETE FROM {self._table}
                        WHERE tenant_id=$1 AND document_id=$2 AND NOT (block_id = ANY($3::text[]))""",
                    tenant_id, document_id, list(keep_block_ids))
        try:
            return int((res or "DELETE 0").split()[-1])
        except ValueError:
            return 0

    # NOTE: `tag_modality_by_journal` (journal-name LIKE-pattern retro-tag) was RETIRED 2026-08-16 —
    # Rule 18 forbids regex/keyword classification of meaning (it mis-caught mainstream journals like
    # "Chinese Medical Journal"). Modality is now stamped as explicit at-ingest provenance via
    # `facet_overrides={"modality": ...}` on the chosen source. See learnings/cam-practitioner-corpus.md.

    # --- lexical planning support ---
    async def _query_lexemes(self, conn, query: str) -> list[str]:
        """The query's lexemes under the SAME text-search config as the tsv column (stemmed,
        stop-words removed) — so document-frequency lookups and the tsquery speak one vocabulary."""
        try:
            arr = await conn.fetchval("SELECT tsvector_to_array(to_tsvector('english', $1))", query)
        except Exception:   # noqa: BLE001 — never let planning break retrieval
            arr = None
        if arr:
            return [str(x) for x in arr]
        return _tokens(query)

    async def _lexeme_df(self, conn) -> dict[str, float]:
        """lexeme → document frequency (fraction of blocks) for the corpus's common lexemes, from the
        planner's ANALYZE statistics. Cached; refreshed every `_DF_REFRESH_S`. Absent → {} (every
        term counts as rare — the strict-AND plan, still bounded)."""
        import time as _time
        now = _time.monotonic()
        if self._df and now - self._df_at < _DF_REFRESH_S:
            return self._df
        try:
            row = await conn.fetchrow(
                "SELECT most_common_elems::text AS elems, most_common_elem_freqs::float8[] AS freqs "
                "FROM pg_stats WHERE tablename = $1 AND attname = 'tsv'", self._table)
            if row and row["elems"]:
                elems = _parse_pg_text_array(row["elems"])
                freqs = list(row["freqs"] or [])
                self._df = {e: float(f) for e, f in zip(elems, freqs)}
        except Exception as e:   # noqa: BLE001 — stats unavailable: plan as if all terms were rare
            _log.warning("lexeme df stats unavailable for %s: %s", self._table, e)
        self._df_at = now
        return self._df

    async def _fetch_bounded(self, conn, sql: str, params: list):
        """Run a retrieval query under a statement timeout; a timeout yields [] (logged) instead of
        stalling the answer — the dense leg and the other legs still produce evidence."""
        try:
            async with conn.transaction():
                await conn.execute(f"SET LOCAL statement_timeout = {_LEX_TIMEOUT_MS}")
                return await conn.fetch(sql, *params)
        except Exception as e:   # noqa: BLE001
            _log.warning("retrieval query skipped (%s): %s", type(e).__name__, str(e)[:160])
            return []

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
        # exclusion: drop a block only if it HAS the key with a listed value (untagged passes)
        for key, banned in getattr(req, "exclude_facets", {}).items():
            vals = [banned] if isinstance(banned, str) else list(banned)
            params.append(key)
            key_idx = len(params)
            params.append(vals)
            preds.append(f"(NOT (facets ? ${key_idx}) OR (facets ->> ${key_idx}) <> ALL(${len(params)}))")
        return " AND ".join(preds), params

    async def search(self, req: RetrievalRequest) -> list[BlockHit]:
        pool = await self._get_pool()
        where, params = self._filter_sql(req)
        pool_n = req.fetch_pool
        qvec = req.query_embedding

        # candidate generation: lexical (tsv) ∪ dense (ANN), both within the filter.
        # PERF (2026-08-16): each candidate leg filters DIRECTLY on the base table, NOT through a
        # `WITH f AS (SELECT * FROM t WHERE ...)` CTE. Postgres cannot use the pgvector HNSW index (nor
        # the tsv GIN index) for an `ORDER BY embedding <=> $vec LIMIT n` that reads from a CTE — it
        # materializes the whole filtered set and brute-force sorts it, which scaled to ~30-50s as the
        # corpus grew past 1M blocks. Filtering inline lets the planner push the ORDER BY into the HNSW
        # index (hnsw.ef_search set on the pool). Same distance metric + same LIMIT = same candidates,
        # just index-accelerated. A separate JOIN back to the base table hydrates the row payload.
        # LEXICAL LEG (2026-09-04 rewrite): the old leg OR'ed every query token
        # (`metformin | dose | 30 | 45`) and ranked ALL matches with ts_rank_cd. Common tokens match
        # ~10% of a 1.5M-block corpus, so the planner ran a full sequential scan + TOAST reads (~10 GB
        # of I/O, 108 s measured in prod) on EVERY search — the long pole of every answer. Now:
        #   1. STRICT leg — AND of the content tokens → GIN bitmap scan, tens of rows, ~1 s.
        #   2. RELAXED leg (only when strict is sparse) — any-2-of-N token pairs, candidate set
        #      capped BEFORE ranking so cost stays bounded (no rank-the-whole-corpus path exists).
        # The dense HNSW leg carries semantic recall regardless; the lexical leg's job is exact-term
        # recall (drug names, codes), which the strict AND preserves.
        async with pool.acquire() as conn:
            lexemes = await self._query_lexemes(conn, req.query)
            plans, rank_q = plan_lexical(lexemes, await self._lexeme_df(conn))
            legs_sql: list[str] = []
            if plans:
                params.append(plans[0]); s_idx = len(params)
                params.append(rank_q);   r_idx = len(params)
                legs_sql.append(
                    f"SELECT tenant_id, document_id, block_id, 'lex' AS leg FROM {self._table} "
                    f"WHERE ({where}) AND tsv @@ to_tsquery('english', ${s_idx}) "
                    f"ORDER BY ts_rank_cd(tsv, to_tsquery('english', ${r_idx})) DESC LIMIT {pool_n}")
            if qvec is not None:
                params.append(qvec)
                v_idx = len(params)
                legs_sql.append(
                    f"SELECT tenant_id, document_id, block_id, 'vec' AS leg FROM {self._table} "
                    f"WHERE ({where}) AND embedding IS NOT NULL "
                    f"ORDER BY embedding <=> ${v_idx} LIMIT {pool_n}")
            if not legs_sql:
                return []
            # UNION ALL (not UNION): the leg tag makes rows distinct anyway; duplicates are dropped
            # below, and the tag lets us see how many candidates the lexical leg produced.
            cand_union = " UNION ALL ".join(f"({s})" for s in legs_sql)
            # JOIN on the FULL primary key (tenant_id, document_id, block_id) so hydration can never
            # cross-match the same content-addressed block under a different tenant.
            hydrate = (f"SELECT t.block_id, t.document_id, t.text, t.embedding, t.facets, "
                       f"t.document_title, t.content_type, t.source_key, cand.leg "
                       f"FROM {self._table} t JOIN cand USING (tenant_id, document_id, block_id)")
            rows = list(await self._fetch_bounded(conn, f"WITH cand AS ({cand_union}) {hydrate}", params))
            lex_n = sum(1 for r in rows if r["leg"] == "lex")
            # Second selection plan (union of rare postings / two least-common terms) only when the
            # first left the lexical pool thin. Bounded by construction and by the statement timeout.
            for sel_q in plans[1:]:
                if lex_n >= pool_n // 2:
                    break
                where2, params2 = self._filter_sql(req)
                params2.append(sel_q); s2 = len(params2)
                params2.append(rank_q); r2 = len(params2)
                more = await self._fetch_bounded(conn, (
                    f"WITH cand AS (SELECT tenant_id, document_id, block_id, 'lex' AS leg FROM {self._table} "
                    f"WHERE ({where2}) AND tsv @@ to_tsquery('english', ${s2}) "
                    f"ORDER BY ts_rank_cd(tsv, to_tsquery('english', ${r2})) DESC LIMIT {pool_n}) {hydrate}"),
                    params2)
                rows += list(more)
                lex_n += len(more)
        seen: set[tuple[str, str]] = set()
        deduped = []
        for r in rows:
            key = (r["document_id"], r["block_id"])
            if key in seen:
                continue
            seen.add(key)
            deduped.append(r)
        rows = deduped

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
        hits = rank_candidates(req.query, qvec, cands, k=req.k, fetch_pool=req.fetch_pool)
        # Corpus currency (Evidence Pulse C1): RETRACTED sources never ground an answer (hard
        # exclusion); SUPERSEDED blocks are stable-partitioned to the bottom — demoted, never
        # deleted (they may be the only source for an unrevised topic, and are the evidence a
        # change brief cites). Retrieval-level, so a superseded edition cannot crowd the current
        # one out of the candidate pool before claim ranking ever sees it (spec A3).
        if self._currency_demote:
            hits = [h for h in hits if not (h.facets or {}).get("retracted")]
            hits.sort(key=lambda h: bool((h.facets or {}).get("superseded_by")))
        return hits
