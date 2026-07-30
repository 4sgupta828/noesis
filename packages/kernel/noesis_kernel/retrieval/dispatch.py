"""Multi-query retrieval dispatch — the recall booster (parity with factra).

Runs the original query plus agent-generated reformulations against a source and
fuses across them with weighted RRF: the original query weighs more, and a block
retrieved by multiple variants gets a repeat bonus. Mirrors factra's dispatcher
(original weight 1.5, repeat bonus 0.15) — kept in the kernel, engine-agnostic.
Reformulation itself is the agent's job (LLM); this fuses the results.
"""
from __future__ import annotations

from collections import Counter
from dataclasses import replace

from noesis_kernel.contract.dto import BlockHit, RetrievalRequest
from noesis_kernel.contract.protocols import RetrievalSource
from noesis_kernel.providers.embeddings import Embedder
from noesis_kernel.retrieval.fusion import RRF_K

ORIGINAL_WEIGHT = 1.5
REPEAT_BONUS = 0.15


async def multi_query_retrieve(
    source: RetrievalSource,
    base_req: RetrievalRequest,
    variants: list[str],
    *,
    embedder: Embedder | None = None,
    original_weight: float = ORIGINAL_WEIGHT,
    repeat_bonus: float = REPEAT_BONUS,
) -> list[BlockHit]:
    queries: list[tuple[str, float]] = [(base_req.query, original_weight)]
    queries += [(v, 1.0) for v in variants if v and v != base_req.query]

    hit_by_id: dict[str, BlockHit] = {}
    scores: dict[str, float] = {}
    appears: Counter[str] = Counter()

    for q, w in queries:
        emb = list(embedder.embed([q])[0]) if embedder is not None else base_req.query_embedding
        req = replace(base_req, query=q, query_embedding=emb)
        hits = await source.search(req)
        for rank, h in enumerate(hits, start=1):
            hit_by_id.setdefault(h.block_id, h)
            scores[h.block_id] = scores.get(h.block_id, 0.0) + w * (1.0 / (RRF_K + rank))
            appears[h.block_id] += 1

    for bid in scores:
        scores[bid] *= (1.0 + repeat_bonus * (appears[bid] - 1))

    ranked = sorted(scores, key=lambda b: (-scores[b], b))[: base_req.k]
    return [replace(hit_by_id[bid], score=scores[bid],
                    extra={**hit_by_id[bid].extra, "queries_hit": appears[bid]})
            for bid in ranked]
