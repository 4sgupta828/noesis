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


def _chunk_text(text: str, *, max_chars: int = 900) -> list[str]:
    """Split a (possibly break-less HTML→text) body into length-bounded chunks, preferring a
    sentence/newline boundary near the budget so a verbatim span stays intact within one chunk."""
    text = (text or "").strip()
    if not text:
        return []
    if len(text) <= max_chars:
        return [text]
    chunks: list[str] = []
    i = 0
    while i < len(text):
        end = min(i + max_chars, len(text))
        if end < len(text):
            window = text[i:end]
            cut = max(window.rfind(". "), window.rfind("\n"), window.rfind("; "))
            if cut > max_chars * 0.5:            # only honor a boundary past the halfway point
                end = i + cut + 1
        piece = text[i:end].strip()
        if piece:
            chunks.append(piece)
        i = end
    return chunks


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
        # Chunk each fetched page body into length-bounded blocks so a verbatim span is findable
        # (a 4000-char blob is nearly unquotable). HTML→text often lacks paragraph breaks, so we
        # split on a char budget with sentence-boundary preference — not the corpus paragraph
        # splitter. Interleave chunks breadth-first so EVERY result contributes a quotable block
        # before we go deeper into any one page.
        per_result = [(r, _chunk_text(r.body or r.snippet or "")) for r in results]
        hits: list[BlockHit] = []
        ci = 0
        while len(hits) < req.k and any(ci < len(ch) for _, ch in per_result):
            for ri, (r, chunks) in enumerate(per_result):
                if ci >= len(chunks) or len(hits) >= req.k:
                    continue
                text = chunks[ci]
                bid = content_key(f"{r.url}|{ci}|{text}".encode())
                self._cache[(r.url, bid)] = text
                hits.append(BlockHit(
                    document_id=r.url, block_id=bid, text=text,
                    score=float(1000 - ri * 10 - ci),      # result rank primary, chunk index secondary
                    # block_span locator: web grounding is "quote exists in the fetched chunk", the
                    # same check as a doc span — one uniform provenance gate. url rides in ref.
                    facets={}, locator=Locator("block_span", r.url, {"block_id": bid, "url": r.url}),
                    document_title=r.title, content_type="text/html", source_key=self.key,
                    legs=("web",),
                ))
            ci += 1
        return hits[: req.k]
