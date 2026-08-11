"""v3 growth campaign (KG spec C-6/C-7): draft masquerade candidates per covered condition,
verify each against the PROD corpus, write shadow edges + activate only corpus-supported,
clinically-notable ones (label capped at 'supported').

Auditable end to end: every candidate's decision lands in a jsonl (no silent drops — A4);
shadow edges are reviewable in the graph console before/after activation; sync-style
idempotency (re-runs dedup on edge identity, never resurrect demoted edges).

Usage:
  .venv/bin/python scripts/grow_graph_masquerade.py --conditions 20 --confirm-spend
  (drafting ≈ 1 call/condition; verification ≈ 1 call/candidate + 1 retrieval)
"""
from __future__ import annotations

import argparse
import asyncio
import datetime as dt
import json
import os
import pathlib
import subprocess
import sys
from typing import Literal

ROOT = pathlib.Path(__file__).resolve().parents[1]
for p in ("apps", "packages/kernel", "packages/vertical_medical"):
    sys.path.insert(0, str(ROOT / p))

from pydantic import BaseModel, Field  # noqa: E402


class _Cand(BaseModel):
    subject: str
    relation: Literal["underlies_presentation_of", "mimics"] = "underlies_presentation_of"
    context: str = ""
    distinguished_by: str = ""


class _Drafts(BaseModel):
    candidates: list[_Cand] = Field(default_factory=list)


def _prod_env() -> None:
    api = json.loads(subprocess.run(["railway", "variables", "--service", "noesis-api",
                                     "--json"], capture_output=True, text=True,
                                    cwd=ROOT).stdout)
    pg = json.loads(subprocess.run(["railway", "variables", "--service", "Postgres",
                                    "--json"], capture_output=True, text=True,
                                   cwd=ROOT).stdout)
    for k, v in api.items():
        if not k.startswith("RAILWAY_") and k != "PORT":
            os.environ[k] = v
    os.environ["NOESIS_CORPUS_DSN"] = pg["DATABASE_PUBLIC_URL"]


async def main(n_conditions: int, per_condition: int) -> None:
    import api.app as appmod
    from noesis_kernel.graph import GraphStore, edge_identity
    from noesis_kernel.graph.verify import verify_edge_candidate
    from noesis_vertical_medical.coverage import COVERED_CONDITIONS
    from noesis_vertical_medical.graph import DRAFT_MASQUERADE_PROMPT, GRAPH_RELATIONS

    svc = appmod.build_default_service()
    g = GraphStore(os.environ["NOESIS_CORPUS_DSN"], relations=GRAPH_RELATIONS)
    existing = {e["id"] for e in await g.list_edges(limit=1000)}
    conditions = [c["name"] for c in COVERED_CONDITIONS][:n_conditions]
    log_path = ROOT / "evals" / "graph" / (
        f"grow-{dt.datetime.now(dt.timezone.utc).strftime('%Y%m%dT%H%M%SZ')}.jsonl")
    decisions: list[dict] = []
    drafted = skipped = supported = notable_n = 0
    sem = asyncio.Semaphore(4)

    async def handle(cover: str) -> None:
        nonlocal drafted, skipped, supported, notable_n
        async with sem:
            try:
                comp = await svc.llm.complete(
                    system=DRAFT_MASQUERADE_PROMPT,
                    messages=[{"role": "user", "content": f"Condition (cover story): {cover}"}],
                    response_format=_Drafts, max_tokens=700)
                cands = comp.parsed.candidates[:per_condition]
            except Exception as e:               # noqa: BLE001
                decisions.append({"cover": cover, "stage": "draft", "error": str(e)[:200]})
                return
            for c in cands:
                drafted += 1
                eid = edge_identity(c.subject, c.relation, cover, c.context)
                if eid in existing:
                    skipped += 1
                    decisions.append({"cover": cover, "subject": c.subject, "stage": "dedup"})
                    continue
                q = f"{c.subject} presenting as {cover} {c.distinguished_by}".strip()
                try:
                    hits = await svc.search(question=q, tenant_id="graphgrow", k=6)
                except Exception as e:           # noqa: BLE001
                    decisions.append({"cover": cover, "subject": c.subject,
                                      "stage": "retrieval", "error": str(e)[:150]})
                    continue
                blocks = [(h.document_id, h.block_id, h.text) for h in hits]
                sentence = (f"{c.subject} {c.relation.replace('_', ' ')} {cover}"
                            + (f" (context: {c.context})" if c.context else "")
                            + (f"; discriminator: {c.distinguished_by}"
                               if c.distinguished_by else ""))
                v = await verify_edge_candidate(sentence=sentence, blocks=blocks, llm=svc.llm)
                status = "shadow"
                if v["supported"]:
                    supported += 1
                    if v["notable"]:
                        notable_n += 1
                        status = "active"
                await g.upsert_edge(
                    subject=c.subject, relation=c.relation, object_=cover,
                    context_topic=c.context, distinguished_by=c.distinguished_by,
                    label="supported" if v["supported"] else "hypothesized",
                    provenance="harvested", status=status,
                    confidence=0.7 if v["supported"] else 0.2,
                    note=f"grow-campaign {'corpus-verified' if v['supported'] else v.get('reason', '')}"[:200])
                existing.add(eid)
                if v["supported"]:
                    await g.add_evidence(edge_id=eid, document_id=v["document_id"],
                                         quote=v["quote"], label="supported")
                decisions.append({"cover": cover, "subject": c.subject,
                                  "relation": c.relation, "dx": c.distinguished_by,
                                  "stage": "verified", "supported": v["supported"],
                                  "notable": v.get("notable"), "status": status,
                                  "reason": v.get("reason", "")})

    await asyncio.gather(*(handle(c) for c in conditions))
    log_path.write_text("\n".join(json.dumps(d) for d in decisions))
    print(f"conditions={len(conditions)} drafted={drafted} dedup-skipped={skipped} "
          f"corpus-supported={supported} activated(notable)={notable_n}")
    print("decision log:", log_path)
    print("stats:", await g.stats())
    await g.close()


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--conditions", type=int, default=20)
    ap.add_argument("--per-condition", type=int, default=4)
    ap.add_argument("--confirm-spend", action="store_true")
    a = ap.parse_args()
    print(f"PROJECTED SPEND: ~{a.conditions} drafting calls + up to "
          f"{a.conditions * a.per_condition} verification calls (+retrievals)")
    if not a.confirm_spend:
        raise SystemExit("refusing without --confirm-spend")
    _prod_env()
    asyncio.run(main(a.conditions, a.per_condition))
