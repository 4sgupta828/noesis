"""Download real medical data → R2 (raw) + fresh pgvector (index), OpenAI embeds.

Usage (env from .env.medical):
  set -a; . ./.env.medical; set +a
  .venv/bin/python scripts/ingest_medical.py --condition diabetes --trials 150 --drugs 100

Raw artifacts (assembled trial/label markdown) are content-addressed into R2;
the searchable blocks (OpenAI text-embedding-3-small, 1536-d) go to Postgres.
"""
from __future__ import annotations

import argparse
import asyncio
import os

from noesis_kernel.ingestion.s3_storage import S3ObjectStore
from noesis_kernel.providers.embeddings import OpenAIEmbedder
from noesis_kernel.retrieval.postgres import PostgresRetrievalSource
from noesis_kernel.runtime.ingest import ingest_connector_to_postgres

from noesis_vertical_medical.connector import ClinicalTrialsConnector
from noesis_vertical_medical.openfda import OpenFdaConnector
from noesis_vertical_medical.europepmc import EuropePmcConnector
from noesis_vertical_medical.faers import FaersConnector
from noesis_vertical_medical.cdc import CdcConnector


async def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--condition", default="diabetes")
    ap.add_argument("--trials", type=int, default=150)
    ap.add_argument("--drugs", type=int, default=100)
    ap.add_argument("--drug-query", default="")  # e.g. openfda.route:ORAL
    ap.add_argument("--papers", type=int, default=0)   # Europe PMC literature
    ap.add_argument("--faers", type=int, default=0)    # adverse-event reports
    ap.add_argument("--faers-drug", default="")        # drug name for FAERS (else condition)
    ap.add_argument("--cdc", type=int, default=0)      # CDC public-health datasets
    ap.add_argument("--tenant", default="demo")
    args = ap.parse_args()

    dsn = os.environ["NOESIS_CORPUS_DSN"]
    embedder = OpenAIEmbedder()                     # 1536-d, real
    pg = PostgresRetrievalSource(dsn, dim=embedder.dim, table="rs_block")
    store = S3ObjectStore.from_env(prefix="medical")

    total = 0
    by_source: dict[str, int] = {}
    if args.trials:
        ct = ClinicalTrialsConnector(page_size=min(args.trials, 100))
        n = await ingest_connector_to_postgres(
            ct, pg, tenant_id=args.tenant, embedder=embedder, object_store=store,
            window={"query": args.condition, "limit": args.trials})
        print(f"[trials] condition={args.condition!r}: {n} blocks indexed")
        total += n; by_source["clinicaltrials"] = n
    if args.drugs:
        fda = OpenFdaConnector(page_size=min(args.drugs, 100))
        n = await ingest_connector_to_postgres(
            fda, pg, tenant_id=args.tenant, embedder=embedder, object_store=store,
            window={"query": args.drug_query, "limit": args.drugs})
        print(f"[drugs] {n} blocks indexed")
        total += n; by_source["openfda"] = n
    if args.papers:
        n = await ingest_connector_to_postgres(
            EuropePmcConnector(), pg, tenant_id=args.tenant, embedder=embedder, object_store=store,
            window={"query": args.condition, "limit": args.papers})
        print(f"[papers] europepmc: {n} blocks indexed")
        total += n; by_source["europepmc"] = n
    if args.faers:
        n = await ingest_connector_to_postgres(
            FaersConnector(), pg, tenant_id=args.tenant, embedder=embedder, object_store=store,
            window={"query": args.faers_drug or args.condition, "limit": args.faers})
        print(f"[faers] {n} blocks indexed")
        total += n; by_source["faers"] = n
    if args.cdc:
        n = await ingest_connector_to_postgres(
            CdcConnector(), pg, tenant_id=args.tenant, embedder=embedder, object_store=store,
            window={"query": args.condition, "limit": args.cdc})
        print(f"[cdc] {n} blocks indexed")
        total += n; by_source["cdc"] = n

    print(f"raw artifacts stored to R2: {store.put_count} | total blocks: {total}")
    await _record_run(pg, condition=args.condition, by_source=by_source, total=total, tenant=args.tenant)
    await pg.close()


async def _record_run(pg, *, condition, by_source, total, tenant) -> None:
    """Record this run to rs_ingest_run so the admin coverage page shows exactly what was
    downloaded, per source, per condition. Best-effort — never fail the ingest."""
    import json
    try:
        pool = await pg._get_pool()
        async with pool.acquire() as conn:
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS rs_ingest_run (
                    id serial PRIMARY KEY, condition text, by_source jsonb,
                    total_blocks int, tenant text, created_at timestamptz DEFAULT now())""")
            await conn.execute(
                "INSERT INTO rs_ingest_run (condition, by_source, total_blocks, tenant) "
                "VALUES ($1,$2::jsonb,$3,$4)",
                condition, json.dumps(by_source), total, tenant)
    except Exception as e:  # noqa: BLE001
        print(f"[warn] could not record ingest run: {e}")


if __name__ == "__main__":
    asyncio.run(main())
