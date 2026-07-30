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

    async def ask(
        self,
        *,
        question: str,
        tenant_id: str,
        workspace_id: str | None = None,
        source_keys: list[str] | None = None,
        max_steps: int = 8,
    ) -> AnswerResult:
        chosen = {k: v for k, v in self.sources.items()
                  if source_keys is None or k in source_keys} or self.sources
        retriever = MultiSourceRetriever(chosen)
        return await run_react(
            question=question, llm=self.llm, embedder=self.embedder, source=retriever,
            tenant_id=tenant_id, workspace_id=workspace_id,
            budget=BudgetState(max_calls=self.max_calls), gating=self.gating,
            system_prompt=self.persona_prompt, max_steps=max_steps,
        )
