"""RegulatoryRetrievalSource — a real source over genuinely-parsed fixture blocks.

Builds its corpus by running the fixture bytes through the REAL kernel pipeline
(parse → split → embed) and materializing — so every BlockHit has a valid
block_span locator the provenance gate can verify against. Wraps the kernel's
InMemoryRetrievalSource; the production impl would query Postgres behind the same
port. Declares `covers()` = the jurisdictions it holds, so the kernel routes by
facet match with no domain noun in the kernel.
"""
from __future__ import annotations

from noesis_kernel.contract.dto import BlockHit, Capability, FacetFilter, RetrievalRequest
from noesis_kernel.corpus.models import Document
from noesis_kernel.corpus.parsers import default_registry
from noesis_kernel.corpus.repository import InMemoryCorpusRepository
from noesis_kernel.ingestion.pipeline import index_document
from noesis_kernel.ingestion.storage import InMemoryObjectStore
from noesis_kernel.providers.embeddings import Embedder, FakeEmbedder
from noesis_kernel.retrieval.materialize import materialize
from noesis_kernel.retrieval.memory import InMemoryRetrievalSource

from .fixtures import FIXTURE_DOCS, JURISDICTION


class RegulatoryRetrievalSource:
    key = "regulatory"

    def __init__(self, *, tenant_id: str = "demo", embedder: Embedder | None = None):
        self._inner = InMemoryRetrievalSource()
        self._build(tenant_id, embedder or FakeEmbedder(dim=16))

    def _build(self, tenant_id: str, embedder: Embedder) -> None:
        store, repo = InMemoryObjectStore(), InMemoryCorpusRepository()
        parsers = default_registry()
        for spec in FIXTURE_DOCS:
            sha = store.put(spec["body"])
            doc = Document(
                id=f"reg:{spec['native_id']}", sha256=sha,
                content_type=spec["content_type"], source_key="regulatory",
                tenant_id=tenant_id, title=spec.get("title", ""),
                facets=dict(spec["facets"]),
            )
            repo.upsert_document(doc)
            index_document(doc, spec["body"], parsers=parsers, embedder=embedder, repo=repo)
        materialize(repo, self._inner)

    # --- RetrievalSource port ---
    def capabilities(self) -> frozenset[Capability]:
        return frozenset({Capability.RETRIEVAL, Capability.PRECISION})

    def covers(self) -> FacetFilter:
        return {"jurisdiction": (JURISDICTION,)}

    def make_block_loader(self, tenant_id: str, workspace_id: str | None = None):
        return self._inner.make_block_loader(tenant_id, workspace_id)

    async def search(self, req: RetrievalRequest) -> list[BlockHit]:
        return await self._inner.search(req)
