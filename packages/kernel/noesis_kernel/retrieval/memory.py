"""InMemoryRetrievalSource — the reference RetrievalSource impl (offline).

Implements the kernel retrieval port with a lexical leg + a dense (cosine) leg
fused by RRF, generic facet IN-filters, and FIRST-CLASS tenant/workspace
isolation. The PostgresRetrievalSource (pgvector HNSW + tsvector + SQL RRF) is a
later adapter behind this same port; this one keeps the whole dev/eval loop
offline and is the tenant-isolation conformance probe.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from noesis_kernel.contract.dto import (
    BlockHit,
    Capability,
    Facets,
    FacetFilter,
    Locator,
    RetrievalRequest,
)
from noesis_kernel.retrieval.fusion import rrf_fuse

_TOKEN = re.compile(r"[a-z0-9]+")


def _tokens(s: str) -> list[str]:
    return _TOKEN.findall(s.lower())


def _facets_match(have: Facets, want: FacetFilter) -> bool:
    for key, allowed in want.items():
        allowed_set = (allowed,) if isinstance(allowed, str) else tuple(allowed)
        if have.get(key) not in allowed_set:
            return False
    return True


def _cosine(a: tuple[float, ...], b: tuple[float, ...]) -> float:
    # embeddings are stored L2-normalized → dot product is cosine.
    return sum(x * y for x, y in zip(a, b))


@dataclass
class IndexedBlock:
    block_id: str
    document_id: str
    text: str
    tenant_id: str
    embedding: tuple[float, ...] = ()
    workspace_id: str | None = None          # None = tenant-wide corpus
    facets: Facets = field(default_factory=dict)
    locator: Locator | None = None


class InMemoryRetrievalSource:
    key = "memory"

    def __init__(self) -> None:
        self._blocks: list[IndexedBlock] = []

    def add(self, block: IndexedBlock) -> None:
        self._blocks.append(block)

    def capabilities(self) -> frozenset[Capability]:
        return frozenset({Capability.RETRIEVAL, Capability.PRECISION})

    def covers(self) -> FacetFilter:
        return {}   # in-memory reference source covers everything

    def make_block_loader(self, tenant_id: str, workspace_id: str | None = None):
        """A block loader scoped to (tenant, workspace) — the provenance gate's
        isolation boundary. It can only return blocks visible to that scope, so a
        cited quote can never be verified against another tenant's document."""
        def _load(document_id: str, block_id: str) -> str | None:
            for b in self._blocks:
                if b.block_id != block_id or b.document_id != document_id:
                    continue
                if b.tenant_id != tenant_id:
                    return None
                if b.workspace_id is not None and b.workspace_id != workspace_id:
                    return None
                return b.text
            return None
        return _load

    def _visible(self, req: RetrievalRequest) -> list[IndexedBlock]:
        """Hard isolation + facet filter — applied BEFORE ranking, always."""
        out = []
        for b in self._blocks:
            if b.tenant_id != req.tenant_id:                 # tenant boundary (security)
                continue
            if b.workspace_id is not None and b.workspace_id != req.workspace_id:
                continue                                     # workspace-scoped: only its own workspace
            if not _facets_match(b.facets, req.facets):
                continue
            out.append(b)
        return out

    async def search(self, req: RetrievalRequest) -> list[BlockHit]:
        cands = self._visible(req)
        if not cands:
            return []
        by_id = {b.block_id: b for b in cands}
        pool = req.fetch_pool

        # lexical leg: term-frequency overlap, deterministic tie-break by id
        q_tokens = _tokens(req.query)
        lex_scored = []
        for b in cands:
            bt = _tokens(b.text)
            score = sum(bt.count(t) for t in q_tokens)
            if score > 0:
                lex_scored.append((b.block_id, score))
        lex_scored.sort(key=lambda t: (-t[1], t[0]))
        lexical = [bid for bid, _ in lex_scored[:pool]]

        # dense leg: cosine vs the kernel-supplied query embedding
        dense: list[str] = []
        if req.query_embedding is not None:
            qv = tuple(req.query_embedding)
            dense_scored = [
                (b.block_id, _cosine(qv, b.embedding))
                for b in cands if b.embedding
            ]
            dense_scored = [(bid, s) for bid, s in dense_scored if s > 0.0]  # drop orthogonal/opposite
            dense_scored.sort(key=lambda t: (-t[1], t[0]))
            dense = [bid for bid, _ in dense_scored[:pool]]

        legs: dict[str, list[str]] = {}
        if lexical:
            legs["lexical"] = lexical
        if dense:
            legs["dense"] = dense
        if not legs:
            return []

        fused = rrf_fuse(legs)[: req.k]
        return [
            BlockHit(
                document_id=by_id[bid].document_id,
                block_id=bid,
                text=by_id[bid].text,
                score=score,
                facets=dict(by_id[bid].facets),
                locator=by_id[bid].locator,
                legs=legs_hit,
            )
            for bid, score, legs_hit in fused
        ]
