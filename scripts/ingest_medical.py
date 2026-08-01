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


async def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--condition", default="diabetes")
    ap.add_argument("--trials", type=int, default=150)
    ap.add_argument("--drugs", type=int, default=100)
    ap.add_argument("--drug-query", default="")  # e.g. openfda.route:ORAL
    ap.add_argument("--tenant", default="demo")
    args = ap.parse_args()

    dsn = os.environ["NOESIS_CORPUS_DSN"]
    embedder = OpenAIEmbedder()                     # 1536-d, real
    pg = PostgresRetrievalSource(dsn, dim=embedder.dim, table="rs_block")
    store = S3ObjectStore.from_env(prefix="medical")

    total = 0
    if args.trials:
        ct = ClinicalTrialsConnector(page_size=min(args.trials, 100))
        n = await ingest_connector_to_postgres(
            ct, pg, tenant_id=args.tenant, embedder=embedder, object_store=store,
            window={"query": args.condition, "limit": args.trials})
        print(f"[trials] condition={args.condition!r}: {n} blocks indexed")
        total += n
    if args.drugs:
        fda = OpenFdaConnector(page_size=min(args.drugs, 100))
        n = await ingest_connector_to_postgres(
            fda, pg, tenant_id=args.tenant, embedder=embedder, object_store=store,
            window={"query": args.drug_query, "limit": args.drugs})
        print(f"[drugs] {n} blocks indexed")
        total += n

    print(f"raw artifacts stored to R2: {store.put_count} | total blocks: {total}")
    await pg.close()


if __name__ == "__main__":
    asyncio.run(main())
