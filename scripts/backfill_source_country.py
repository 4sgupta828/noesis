"""Backfill the `source_country` facet on existing rs_block rows (one-time, idempotent, batched).

The country-scope hard filter is `(facets->>'source_country') = ANY($vals)`; a block with NO
source_country facet is NULL → EXCLUDED by the filter. Connectors now tag source_country at ingest,
but the ~400k LEGACY blocks predate that, so a scoped query would return nothing until they're tagged.
This backfills them by source_key, batched to avoid a single 400k-row lock / WAL spike, and creates
the expression index the filter actually uses (the generic facets GIN doesn't serve `->>` equality well).

DO NOT flip NOESIS_COUNTRY_SCOPE on in prod until this reports ~0 untagged blocks (the legacy-null trap).

  NOESIS_CORPUS_DSN=postgresql://... .venv/bin/python scripts/backfill_source_country.py [--dsn ...] [--batch 20000]
"""
from __future__ import annotations

import argparse
import asyncio
import os

# source_key → source_country. US regulatory/public-health vs global literature/trials. India
# connectors tag "IN" at ingest, so they never need backfilling here.
COUNTRY_BY_SOURCE = {
    "openfda": "US", "faers": "US", "dailymed": "US", "cdc": "US",
    "clinicaltrials": "global", "europepmc": "global",
}


async def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dsn", default=os.environ.get("NOESIS_CORPUS_DSN") or os.environ.get("DATABASE_PUBLIC_URL"))
    ap.add_argument("--batch", type=int, default=20000)
    args = ap.parse_args()
    if not args.dsn:
        raise SystemExit("set NOESIS_CORPUS_DSN or pass --dsn")
    import asyncpg
    c = await asyncpg.connect(args.dsn.replace("postgresql+asyncpg://", "postgresql://"))
    try:
        # expression index matching the real predicate (facets->>'source_country'); CONCURRENTLY = no
        # long table lock. IF NOT EXISTS makes it idempotent.
        print("creating expression index (concurrently)…")
        try:
            await c.execute("CREATE INDEX CONCURRENTLY IF NOT EXISTS rs_block_source_country_idx "
                            "ON rs_block ((facets->>'source_country'))")
        except Exception as e:  # noqa: BLE001
            print(f"  index note: {e}")

        total_tagged = 0
        for src, country in COUNTRY_BY_SOURCE.items():
            # batch by ctid ranges within this source_key, only rows missing the facet (idempotent)
            n = 0
            while True:
                res = await c.execute(
                    "WITH b AS (SELECT ctid FROM rs_block "
                    "  WHERE source_key = $1 AND NOT (facets ? 'source_country') LIMIT $2) "
                    "UPDATE rs_block r SET facets = facets || jsonb_build_object('source_country', $3::text) "
                    "FROM b WHERE r.ctid = b.ctid",
                    src, args.batch, country)
                got = int(res.split()[-1]) if res.startswith("UPDATE") else 0
                if got == 0:
                    break
                n += got
                print(f"  {src} → {country}: +{got} (running {n})")
            total_tagged += n
            print(f"{src}: tagged {n}")

        untagged = await c.fetchval("SELECT count(*) FROM rs_block WHERE NOT (facets ? 'source_country')")
        by = await c.fetch("SELECT facets->>'source_country' c, count(*) n FROM rs_block GROUP BY 1 ORDER BY 2 DESC")
        print(f"\ntagged this run: {total_tagged}")
        print("distribution:", {r["c"]: r["n"] for r in by})
        print(f"REMAINING UNTAGGED: {untagged}  (must be ~0 before enabling NOESIS_COUNTRY_SCOPE)")
    finally:
        await c.close()


if __name__ == "__main__":
    asyncio.run(main())
