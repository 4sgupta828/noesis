"""ResearchService — the runnable multi-source research agent.

Composes an LLM + embedder + a set of named RetrievalSources (corpus, web,
workspace, …) and answers a question over any chosen combination, with the
vertical's gating policy + persona driving the loop. This is what the API calls.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from noesis_kernel.contract.protocols import Connector, GatingPolicy, RetrievalSource
from noesis_kernel.providers.embeddings import Embedder
from noesis_kernel.providers.llm import LLMClient
from noesis_kernel.research.budget import BudgetState
from noesis_kernel.research.react import AnswerResult, run_react
from noesis_kernel.retrieval.multi import MultiSourceRetriever


@dataclass
class ResearchService:
    llm: LLMClient
    embedder: Embedder
    sources: dict[str, RetrievalSource]
    gating: GatingPolicy | None = None
    persona_prompt: str = "You are an evidence-grounded research agent."
    max_calls: int = 40
    vertical_name: str = ""
    ui: object | None = None                # the vertical's UIContract (for /config)
    connectors: dict[str, Connector] = field(default_factory=dict)  # for /ingest
    corpus_source_key: str = ""             # the pg-backed corpus key (if any)

    def _retriever(self, source_keys: list[str] | None) -> MultiSourceRetriever:
        chosen = {k: v for k, v in self.sources.items()
                  if source_keys is None or k in source_keys} or self.sources
        return MultiSourceRetriever(chosen)

    async def ask(
        self,
        *,
        question: str,
        tenant_id: str,
        workspace_id: str | None = None,
        source_keys: list[str] | None = None,
        max_steps: int = 8,
    ) -> AnswerResult:
        return await run_react(
            question=question, llm=self.llm, embedder=self.embedder,
            source=self._retriever(source_keys),
            tenant_id=tenant_id, workspace_id=workspace_id,
            budget=BudgetState(max_calls=self.max_calls), gating=self.gating,
            system_prompt=self.persona_prompt, max_steps=max_steps,
        )

    async def search(
        self,
        *,
        question: str,
        tenant_id: str,
        workspace_id: str | None = None,
        source_keys: list[str] | None = None,
        k: int = 8,
    ):
        """Retrieval only — no LLM. Returns ranked evidence blocks. Works with just
        the embedder (OpenAI), so it's available even when the answer LLM isn't."""
        from noesis_kernel.contract.dto import RetrievalRequest
        qv = list(self.embedder.embed([question])[0])
        return await self._retriever(source_keys).search(RetrievalRequest(
            query=question, tenant_id=tenant_id, workspace_id=workspace_id,
            query_embedding=qv, k=k))
