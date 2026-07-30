"""RegulatoryConnector — a minimal REAL connector over the fixture.

Proves the discover → list → fetch seam (not an empty stub). A production
connector would scrape a commission portal via its FetchStrategy; this one
serves the bundled fixture so the whole ingest path is exercisable offline.
"""
from __future__ import annotations

from noesis_kernel.contract.dto import DocumentRef, EntityRef

from .fixtures import DOCKET, FIXTURE_DOCS, JURISDICTION


class HttpStrategy:
    egress_class = "datacenter"
    engine = "http"
    proxy_enabled = False
    async def fetch(self, url: str, **opts) -> bytes:  # noqa: ANN003
        return b""


class RegulatoryConnector:
    key = "regulatory"

    def __init__(self) -> None:
        self.fetch_strategy = HttpStrategy()

    async def discover_entities(self, window: dict) -> list[EntityRef]:
        return [EntityRef(source_key="regulatory", native_id=DOCKET,
                          title="Sample Electric Company rate case",
                          facets={"jurisdiction": JURISDICTION})]

    async def list_documents(self, entity: EntityRef) -> list[DocumentRef]:
        return [DocumentRef(source_key="regulatory", native_id=d["native_id"],
                            content_type=d["content_type"], facets=dict(d["facets"]),
                            entity_ids=(entity.native_id,))
                for d in FIXTURE_DOCS]

    async def fetch_artifact(self, doc: DocumentRef) -> bytes:
        return next(d["body"] for d in FIXTURE_DOCS if d["native_id"] == doc.native_id)
