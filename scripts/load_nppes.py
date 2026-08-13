"""NPPES bulk loader — Frontier People P0 spine (spec E-6: OFFLINE streaming, never the
connector protocol / API container; documented exception to prod-direct-ingest).

Streams the NPPES dissemination CSV (from the ~1GB monthly zip, unzipped or piped) row by
row, filters to SPECIALIST taxonomies for the pilot specialties, and COPYs into
noesis_entity(+contact phone). Natural-key ids ('npi:<10 digits>', E-2). Memory-flat.

People-data manifest (E-0): NPPES is published BY CMS FOR public dissemination — public
domain, redistribution expected; suppression honored at our layer via status flips.

Usage:
  1) download: https://download.cms.gov/nppes/NPPES_Data_Dissemination_<Month>_<Year>.zip
     unzip → the npidata_pfile_*.csv (~9GB)
  2) .venv/bin/python scripts/load_nppes.py --csv <path> --dsn <PG_DSN> \
        [--vintage 2026-08-01] [--limit 0]
"""
from __future__ import annotations

import argparse
import asyncio
import csv
import datetime as dt
import pathlib
import sys

# Single source of truth for coverage: ALL physician taxonomies (NUCC grouping), owned by
# apps/api/people_taxonomies.py — the offline path must never drift from the server loader.
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "apps"))
from api.people_taxonomies import TAXONOMY_LABELS as PILOT_TAXONOMIES  # noqa: E402

# npidata_pfile column names (header-driven — robust to column order)
COLS = {
    "npi": "NPI", "type": "Entity Type Code",
    "last": "Provider Last Name (Legal Name)", "first": "Provider First Name",
    "cred": "Provider Credential Text",
    "org_city": "Provider Business Practice Location Address City Name",
    "org_state": "Provider Business Practice Location Address State Name",
    "phone": "Provider Business Practice Location Address Telephone Number",
    "deact": "NPI Deactivation Date",
}
TAX_COLS = [f"Healthcare Provider Taxonomy Code_{i}" for i in range(1, 16)]
PRIMARY_COLS = [f"Healthcare Provider Primary Taxonomy Switch_{i}" for i in range(1, 16)]


async def main(csv_path: str, dsn: str, vintage: str, limit: int) -> None:
    import asyncpg
    from noesis_kernel.people.store import PeopleStore
    store = PeopleStore(dsn)
    await store._get_pool()                     # ensure schema
    await store.close()
    conn = await asyncpg.connect(dsn)
    ent_rows, contact_rows = [], []
    seen = kept = 0
    vintage_d = dt.date.fromisoformat(vintage)

    async def flush():
        nonlocal ent_rows, contact_rows
        if ent_rows:
            await conn.executemany(
                """INSERT INTO noesis_entity (entity_id, vertical, kind, name, taxonomy,
                     specialty, credential, city, state, country, status, source, valid_as_of)
                   VALUES ($1,'medical','physician',$2,$3,$4,$5,$6,$7,'US',$8,'nppes',$9)
                   ON CONFLICT (entity_id) DO UPDATE SET
                     name=EXCLUDED.name, taxonomy=EXCLUDED.taxonomy, specialty=EXCLUDED.specialty,
                     credential=EXCLUDED.credential, city=EXCLUDED.city, state=EXCLUDED.state,
                     status=CASE WHEN noesis_entity.status='suppressed'
                                 THEN 'suppressed' ELSE EXCLUDED.status END,  -- E-0: suppression sticks
                     valid_as_of=EXCLUDED.valid_as_of, updated_at=now()""", ent_rows)
        if contact_rows:
            await conn.executemany(
                """INSERT INTO noesis_entity_contact (entity_id, kind, value, source)
                   VALUES ($1,'phone',$2,'nppes') ON CONFLICT DO NOTHING""", contact_rows)
        ent_rows, contact_rows = [], []

    with open(csv_path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            seen += 1
            if limit and kept >= limit:
                break
            if row.get(COLS["type"]) != "1":            # individuals only (NPI-1)
                continue
            taxes = [(row.get(t) or "").strip() for t in TAX_COLS]
            prim = [(row.get(p) or "").strip() for p in PRIMARY_COLS]
            code = ""
            for c, p in zip(taxes, prim):               # prefer the primary taxonomy
                if c in PILOT_TAXONOMIES and p == "Y":
                    code = c
                    break
            if not code:
                code = next((c for c in taxes if c in PILOT_TAXONOMIES), "")
            if not code:
                continue
            npi = (row.get(COLS["npi"]) or "").strip()
            if not (npi.isdigit() and len(npi) == 10):
                continue
            name = f"{(row.get(COLS['first']) or '').strip()} {(row.get(COLS['last']) or '').strip()}".strip()
            if not name:
                continue
            status = "retired" if (row.get(COLS["deact"]) or "").strip() else "active"
            eid = f"npi:{npi}"
            ent_rows.append([eid, name, code, PILOT_TAXONOMIES[code],
                             (row.get(COLS["cred"]) or "").strip()[:40],
                             (row.get(COLS["org_city"]) or "").strip()[:80],
                             (row.get(COLS["org_state"]) or "").strip()[:2], status, vintage_d])
            phone = (row.get(COLS["phone"]) or "").strip()
            if phone:
                contact_rows.append([eid, phone[:24]])
            kept += 1
            if len(ent_rows) >= 5000:
                await flush()
                print(f"  …{kept:,} kept of {seen:,} scanned", flush=True)
    await flush()
    n = await conn.fetchval("SELECT count(*) FROM noesis_entity WHERE source='nppes'")
    await conn.close()
    print(f"DONE: scanned {seen:,}, kept {kept:,}; noesis_entity(nppes) now {n:,}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--csv", required=True)
    ap.add_argument("--dsn", required=True)
    ap.add_argument("--vintage", default=dt.date.today().replace(day=1).isoformat())
    ap.add_argument("--limit", type=int, default=0, help="stop after N kept (pilot/testing)")
    a = ap.parse_args()
    sys.path.insert(0, "packages/kernel")
    asyncio.run(main(a.csv, a.dsn, a.vintage, a.limit))
