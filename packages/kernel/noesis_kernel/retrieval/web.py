"""WebRetrievalSource — the web as just another pluggable RetrievalSource.

Turns web-search results into citable, grounded blocks: each result becomes a
block whose text is the fetched body, with a locator so the SAME span-check gate
verifies a cited quote actually exists in the retrieved page (no fabrication) —
identical provenance to corpus/workspace sources. This is the platform pattern:
every knowledge source (corpus, workspace, web, and later expert transcripts,
surveys, proprietary datasets) implements one port and the agent stays
source-agnostic.
"""
from __future__ import annotations

from noesis_kernel.contract.dto import BlockHit, Capability, FacetFilter, Locator, RetrievalRequest
from noesis_kernel.ingestion.storage import content_key
from noesis_kernel.providers.websearch import WebSearchClient


class WebRetrievalSource:
    def __init__(self, client: WebSearchClient, *, key: str = "web", max_results: int = 8):
        self.key = key
        self._client = client
        self._max = max_results
        self._cache: dict[tuple[str, str], str] = {}   # (url, block_id) -> body (loader)

    def capabilities(self) -> frozenset[Capability]:
        return frozenset({Capability.RETRIEVAL})

    def covers(self) -> FacetFilter:
        return {}          # web is unscoped (public); no facet limit

    def make_block_loader(self, tenant_id: str, workspace_id: str | None = None):
        # Web content is public; the loader is scoped to what THIS search fetched
        # (fail-closed on anything not retrieved this request).
        def _load(document_id: str, block_id: str) -> str | None:
            return self._cache.get((document_id, block_id))
        return _load

    async def search(self, req: RetrievalRequest) -> list[BlockHit]:
        results = await self._client.search(req.query, max_results=self._max)
        hits: list[BlockHit] = []
        n = len(results)
        for i, r in enumerate(results):
            body = r.body or r.snippet or ""
            bid = content_key(f"{r.url}|{body}".encode())
            self._cache[(r.url, bid)] = body
            hits.append(BlockHit(
                document_id=r.url, block_id=bid, text=body,
                score=float(n - i),                       # provider order → descending score
                # block_span locator: web grounding is "quote exists in the fetched
                # body", the same check as a doc span — one uniform provenance gate.
                # The url rides in ref for citation rendering.
                facets={}, locator=Locator("block_span", r.url, {"block_id": bid, "url": r.url}),
                document_title=r.title, content_type="text/html", source_key=self.key,
                legs=("web",),
            ))
        return hits[: req.k]
