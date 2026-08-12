"""Restore Noesis from an R2 recreatability backup (apps/api/backup.py's output).

Restores every critical table + the corpus text/facets into a TARGET Postgres, then prints
the re-embed instruction (embeddings/tsv are recreated, not restored). REFUSES to write into
a non-empty table unless --force (never silently clobbers a live DB).

Usage:
  R2_* env set (or pulled via railway) ·
  .venv/bin/python scripts/restore_from_backup.py --date 2026-08-12 --dsn <TARGET_DSN> [--force]
Then: re-run embeddings (scripts/reembed.py or the ingest pipeline's embed pass) and let
ensure_schema recreate indexes on first boot.
"""
from __future__ import annotations

import argparse
import asyncio
import gzip
import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
for p in ("apps", "packages/kernel"):
    sys.path.insert(0, str(ROOT / p))


async def main(date: str, dsn: str, force: bool) -> None:
    import asyncpg
    from api.backup import CRITICAL_TABLES, R2Named
    store = R2Named()
    base = f"backups/{date}"
    manifest = json.loads(store.get(f"{base}/MANIFEST.json"))
    print("manifest:", {k: manifest[k] for k in ("date", "corpus_parts")},
          "| tables:", sum(manifest["tables"].values()))
    conn = await asyncpg.connect(dsn)
    try:
        # schemas: boot each store's DDL first (CurrencyStore/GraphStore/Session/Account ensure
        # their own tables); here we only guard + insert.
        for t in CRITICAL_TABLES:
            key = f"{base}/{t}.jsonl.gz"
            try:
                rows = [json.loads(ln) for ln in
                        gzip.decompress(store.get(key)).decode().splitlines() if ln.strip()]
            except Exception as e:   # noqa: BLE001
                print(f"  skip {t}: {e}")
                continue
            if not rows:
                continue
            n = await conn.fetchval(f"SELECT count(*) FROM {t}")   # noqa: S608
            if n and not force:
                print(f"  REFUSING {t}: target has {n} rows (use --force)")
                continue
            cols = list(rows[0].keys())
            await conn.executemany(
                f"INSERT INTO {t} ({', '.join(cols)}) VALUES "   # noqa: S608
                f"({', '.join(f'${i+1}' for i in range(len(cols)))}) ON CONFLICT DO NOTHING",
                [[r.get(c) for c in cols] for r in rows])
            print(f"  {t}: {len(rows)} rows")
        parts = sorted(k for k in store.list(base) if "rs_block-part" in k)
        total = 0
        for pk in parts:
            rows = [json.loads(ln) for ln in
                    gzip.decompress(store.get(pk)).decode().splitlines() if ln.strip()]
            await conn.executemany(
                """INSERT INTO rs_block (tenant_id, workspace_id, document_id, block_id, text,
                                         facets, document_title, content_type, source_key, created_at)
                   VALUES ($1,$2,$3,$4,$5,$6::jsonb,$7,$8,$9,$10::timestamptz)
                   ON CONFLICT (tenant_id, document_id, block_id) DO NOTHING""",
                [[r["tenant_id"], r["workspace_id"], r["document_id"], r["block_id"], r["text"],
                  r["facets"] if isinstance(r["facets"], str) else json.dumps(r["facets"]),
                  r["document_title"], r["content_type"], r["source_key"], r["created_at"]]
                 for r in rows])
            total += len(rows)
            print(f"  {pk.split('/')[-1]}: +{len(rows)} (total {total})")
        print(f"\nRESTORED. Now re-embed: blocks have NULL embeddings — run the embed pass, "
              f"then queries work (tsv/indexes regenerate via DDL).")
    finally:
        await conn.close()


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--date", required=True)
    ap.add_argument("--dsn", required=True)
    ap.add_argument("--force", action="store_true")
    a = ap.parse_args()
    asyncio.run(main(a.date, a.dsn, a.force))
