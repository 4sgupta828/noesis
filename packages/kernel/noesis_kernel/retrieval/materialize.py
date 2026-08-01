"""Materialize the corpus repository into a retrieval index — domain-free.

Joins Document (facets + tenant/workspace) × Block (locator) × BlockContent
(embedding) into IndexedBlocks the retrieval source can search. This is the
in-memory analogue of the SQL join a PostgresRetrievalSource does at query time;
keeping it explicit lets the whole ingest→retrieve path run offline.
"""
from __future__ import annotations

from noesis_kernel.contract.dto import Locator
from noesis_kernel.corpus.repository import CorpusRepository
from noesis_kernel.retrieval.memory import IndexedBlock, InMemoryRetrievalSource


def materialize(repo: CorpusRepository, source: InMemoryRetrievalSource) -> int:
    """Load all embedded blocks from `repo` into `source`. Returns count added."""
    added = 0
    for doc in repo.iter_documents():
        for block in repo.blocks_for(doc.id):
            bc = repo.block_content(block.content_key)
            embedding = tuple(bc.embedding) if (bc and bc.embedding) else ()
            # narrowing facets: document dims + any per-block tags (block wins).
            facets = {**doc.facets, **block.facets}
            source.add(IndexedBlock(
                block_id=block.content_key,       # content-addressed block id
                document_id=doc.id,
                text=block.text,
                tenant_id=doc.tenant_id,
                workspace_id=doc.workspace_id,
                embedding=embedding,
                facets=facets,
                locator=Locator("block_span", doc.id, {"block_id": block.content_key}),
                document_title=doc.title,
                content_type=doc.content_type,
                source_key=doc.source_key,
            ))
            added += 1
    return added


async def materialize_to_postgres(repo: CorpusRepository, pg_source, *, batch_size: int = 500) -> int:
    """Same join, into a PostgresRetrievalSource's index table — BATCHED upserts
    (one round-trip per `batch_size` blocks instead of one per block)."""
    rows: list[dict] = []
    added = 0
    for doc in repo.iter_documents():
        for block in repo.blocks_for(doc.id):
            bc = repo.block_content(block.content_key)
            rows.append(dict(
                tenant_id=doc.tenant_id, document_id=doc.id, block_id=block.content_key,
                text=block.text, embedding=list(bc.embedding) if (bc and bc.embedding) else None,
                facets={**doc.facets, **block.facets}, workspace_id=doc.workspace_id,
                document_title=doc.title, content_type=doc.content_type, source_key=doc.source_key,
            ))
            if len(rows) >= batch_size:
                await pg_source.upsert_blocks(rows)
                added += len(rows)
                rows = []
    if rows:
        await pg_source.upsert_blocks(rows)
        added += len(rows)
    return added
