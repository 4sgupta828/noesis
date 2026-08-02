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
    answer_format: str | None = None        # vertical answer-structure directive (opaque)
    vision_prompt: str | None = None        # vertical image-description directive (opaque)
    layman_prompt: str | None = None        # vertical layman-rephrasing directive (opaque)
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
        images: list[dict] | None = None,
        documents: list[dict] | None = None,
        max_steps: int = 8,
    ) -> AnswerResult:
        budget = BudgetState(max_calls=self.max_calls)
        # Attachment context (never corpus evidence, never a verified claim):
        #  - images/scans → a labeled DESCRIPTIVE vision observation (vision pre-step),
        #  - uploaded documents (e.g. a paper PDF) → their extracted TEXT.
        # Both are combined into attachment_context that only frames the search.
        visual_obs = ""
        if images and self.vision_prompt:
            from noesis_kernel.research.vision import observe_images
            try:
                visual_obs = await observe_images(
                    llm=self.llm, vision_prompt=self.vision_prompt,
                    images=images, budget=budget)
            except Exception:
                visual_obs = ""             # a failed vision read must not break research
        parts: list[str] = []
        if visual_obs:
            parts.append("IMAGE (automated visual description):\n" + visual_obs)
        for d in documents or []:
            txt = (d.get("text") or "").strip()
            if txt:
                name = d.get("name") or "document"
                parts.append(f"DOCUMENT — {name} (user-provided text):\n{txt}")
        attachment_context = "\n\n".join(parts) or None

        res = await run_react(
            question=question, llm=self.llm, embedder=self.embedder,
            source=self._retriever(source_keys),
            tenant_id=tenant_id, workspace_id=workspace_id,
            budget=budget, gating=self.gating,
            system_prompt=self.persona_prompt, answer_format=self.answer_format,
            attachment_context=attachment_context, max_steps=max_steps,
        )
        res.visual_observation = visual_obs      # surface the image reading (UI panel)
        return res

    async def explain(self, *, question: str, answer: str) -> str:
        """On-demand plain-language rephrasing of a grounded answer (adds no new facts)."""
        if not self.layman_prompt:
            return ""
        from noesis_kernel.research.explain import explain_for_layperson
        return await explain_for_layperson(
            llm=self.llm, layman_prompt=self.layman_prompt, question=question, answer=answer)

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
