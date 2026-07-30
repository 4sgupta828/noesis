"""The generic acquisition pipeline: discover → list → fetch → store → document.

Ties a vertical's Connector to the kernel's ObjectStore + CorpusRepository. Fully
domain-neutral: entities/documents carry only `facets`. Parse → block → embed is
a later stage (needs a Parser + Embedder); this stage lands raw artifacts in the
content-addressed store and the document spine.
"""
from __future__ import annotations

from dataclasses import dataclass

from noesis_kernel.contract.protocols import Connector
from noesis_kernel.corpus.models import Document
from noesis_kernel.corpus.repository import CorpusRepository
from noesis_kernel.ingestion.storage import ObjectStore


@dataclass
class IngestSummary:
    entities: int = 0
    documents: int = 0
    objects_stored: int = 0     # unique bytes actually stored (dedup misses)


async def ingest_source(
    connector: Connector,
    store: ObjectStore,
    repo: CorpusRepository,
    *,
    window: dict | None = None,
) -> IngestSummary:
    summary = IngestSummary()
    entities = await connector.discover_entities(window or {})
    summary.entities = len(entities)
    for entity in entities:
        docs = await connector.list_documents(entity)
        for ref in docs:
            raw = await connector.fetch_artifact(ref)
            key = store.put(raw)
            doc = Document(
                id=f"{ref.source_key}:{ref.native_id}",
                sha256=key,
                content_type=ref.content_type,
                source_key=ref.source_key,
                facets=dict(ref.facets),
                dates=dict(ref.dates),
                entity_ids=tuple(ref.entity_ids) or (entity.native_id,),
            )
            repo.upsert_document(doc)
            summary.documents += 1
    summary.objects_stored = getattr(store, "put_count", 0)
    return summary
