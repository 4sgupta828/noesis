"""MedicalRetrievalSource — a corpus over the bundled sample trials (offline).

Builds by running each sample trial through trial_doc -> the REAL kernel pipeline
(parse -> split -> embed) -> materialize, so every BlockHit has a verifiable
block_span locator. Production uses PostgresRetrievalSource fed by
ingest_connector_to_postgres(ClinicalTrialsConnector, ...). covers() = {} (the
registry spans all conditions).
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

from . import trial_doc
from .fixtures import sample_studies


class MedicalRetrievalSource:
    key = "clinicaltrials"

    def __init__(self, *, tenant_id: str = "demo", embedder: Embedder | None = None,
                 studies: list[dict] | None = None):
        self._inner = InMemoryRetrievalSource()
        self._build(tenant_id, embedder or FakeEmbedder(dim=16), studies or sample_studies())

    def _build(self, tenant_id, embedder, studies):
        store, repo = InMemoryObjectStore(), InMemoryCorpusRepository()
        parsers = default_registry()
        for s in studies:
            nct = trial_doc.nct_id(s)
            body = trial_doc.to_markdown(s).encode("utf-8")
            sha = store.put(body)
            doc = Document(id=f"ct:{nct}", sha256=sha, content_type="text/markdown",
                           source_key=self.key, tenant_id=tenant_id,
                           title=trial_doc.title(s), facets=trial_doc.facets(s))
            repo.upsert_document(doc)
            index_document(doc, body, parsers=parsers, embedder=embedder, repo=repo)
        materialize(repo, self._inner)

    def capabilities(self) -> frozenset[Capability]:
        return frozenset({Capability.RETRIEVAL, Capability.PRECISION})

    def covers(self) -> FacetFilter:
        return {}

    def make_block_loader(self, tenant_id: str, workspace_id: str | None = None):
        return self._inner.make_block_loader(tenant_id, workspace_id)

    async def search(self, req: RetrievalRequest) -> list[BlockHit]:
        return await self._inner.search(req)
