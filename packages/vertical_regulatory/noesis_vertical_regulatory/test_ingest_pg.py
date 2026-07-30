"""Integration: ingest the regulatory connector INTO Postgres, then research over
it. Skipped unless NOESIS_TEST_PG_DSN is set. Proves the real ingest→pg→agent path.

    NOESIS_TEST_PG_DSN=postgresql://strata:strata@localhost:5433/noesis_test \
      .venv/bin/python -m pytest .../test_ingest_pg.py -q
"""
from __future__ import annotations

import asyncio
import os

import pytest

from noesis_kernel.contract.dto import RetrievalRequest
from noesis_kernel.providers.embeddings import FakeEmbedder
from noesis_kernel.providers.llm import LLMResult
from noesis_kernel.research.react import AgentStep, ClaimOut
from noesis_kernel.retrieval.postgres import PostgresRetrievalSource
from noesis_kernel.runtime.ingest import ingest_connector_to_postgres
from noesis_kernel.runtime.research import ResearchService

import noesis_vertical_regulatory as reg
from noesis_vertical_regulatory.connector import RegulatoryConnector

DSN = os.environ.get("NOESIS_TEST_PG_DSN")
pytestmark = pytest.mark.skipif(not DSN, reason="set NOESIS_TEST_PG_DSN for pg integration")
DIM, TABLE = 16, "rs_ingest_test"


class _LLM:
    def __init__(self, steps): self._s = list(steps)
    async def complete(self, *, system, messages, response_format, max_tokens=2048, temperature=None):
        return LLMResult(parsed=self._s.pop(0), output_tokens=5)


def test_ingest_regulatory_to_pg_then_research() -> None:
    async def body():
        emb = FakeEmbedder(dim=DIM)
        pg = PostgresRetrievalSource(DSN, dim=DIM, table=TABLE, covers={"jurisdiction": ("OH",)})
        await pg.ensure_schema()
        pool = await pg._get_pool()
        async with pool.acquire() as conn:
            await conn.execute(f"TRUNCATE {TABLE}")
        try:
            # 1) ingest the connector's documents into the pg corpus
            n = await ingest_connector_to_postgres(
                RegulatoryConnector(), pg, tenant_id="acme", embedder=emb)
            assert n >= 1

            # 2) the pg corpus is searchable
            qv = list(emb.embed(["return on equity"])[0])
            hits = await pg.search(RetrievalRequest(
                query="return on equity", tenant_id="acme", query_embedding=qv, k=10))
            assert hits and any("return on equity" in h.text.lower() for h in hits)
            # narrowing facets carried through ingestion
            assert hits[0].facets.get("jurisdiction") == "OH"

            # 3) the agent researches over the pg corpus → grounded answer
            svc = ResearchService(
                llm=_LLM([
                    # grounded ask
                    AgentStep(action="search", query="commission return on equity"),
                    AgentStep(action="answer", claims=[
                        ClaimOut(text="the case concerns return on equity",
                                 atom_id="a1", quote="return on equity")]),
                    # intruder ask (sees no evidence → honest empty answer)
                    AgentStep(action="search", query="return on equity"),
                    AgentStep(action="answer", claims=[]),
                ]),
                embedder=emb, sources={"regulatory": pg},
                gating=reg.manifest.gating_policy,
                persona_prompt=reg.manifest.persona.system_prompt())
            res = await svc.ask(question="what does the case decide?",
                                tenant_id="acme", source_keys=["regulatory"])
            assert res.grounded and res.verified_claims[0].source_key == "regulatory"

            # 4) tenant isolation over the pg corpus
            other = await svc.ask(question="what does the case decide?",
                                  tenant_id="intruder", source_keys=["regulatory"])
            assert other.atoms_gathered == 0
        finally:
            await pg.close()
    asyncio.run(body())
