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
    planner_llm: LLMClient | None = None     # fast model for ReAct planning steps (compose uses llm)
    gating: GatingPolicy | None = None
    persona_prompt: str = "You are an evidence-grounded research agent."
    answer_format: str | None = None        # vertical answer-structure directive (opaque)
    vision_prompt: str | None = None        # vertical image-description directive (opaque)
    layman_prompt: str | None = None        # vertical layman-rephrasing directive (opaque)
    gap_prompt: str | None = None           # vertical gap-fill-planner directive (opaque)
    suggest_prompt: str | None = None       # vertical suggested-follow-ups directive (opaque)
    max_calls: int = 40
    vertical_name: str = ""
    ui: object | None = None                # the vertical's UIContract (for /config)
    connectors: dict[str, Connector] = field(default_factory=dict)  # for /ingest
    corpus_source_key: str = ""             # the pg-backed corpus key (if any)
    aux_source_keys: tuple[str, ...] = ("web",)   # queried once/step (no variant fan-out) — e.g. web

    def _retriever(self, source_keys: list[str] | None) -> MultiSourceRetriever:
        chosen = {k: v for k, v in self.sources.items()
                  if source_keys is None or k in source_keys} or self.sources
        return MultiSourceRetriever(chosen)

    def _split_retriever(self, source_keys):
        """Corpus (vector, multi-query) and AUX (web, single-query per step) retrievers. Web is
        split out so it's queried ONCE per step on the original query — not fanned out per
        reformulation — which keeps web latency bounded while still adding breadth."""
        chosen = {k: v for k, v in self.sources.items()
                  if source_keys is None or k in source_keys} or self.sources
        aux = {k: v for k, v in chosen.items() if k in self.aux_source_keys}
        corpus = {k: v for k, v in chosen.items() if k not in self.aux_source_keys}
        if not corpus:                       # web-only selection → treat it as the primary source
            return MultiSourceRetriever(chosen), None
        return MultiSourceRetriever(corpus), (MultiSourceRetriever(aux) if aux else None)

    async def ask(
        self,
        *,
        question: str,
        tenant_id: str,
        workspace_id: str | None = None,
        source_keys: list[str] | None = None,
        images: list[dict] | None = None,
        documents: list[dict] | None = None,
        history: list[dict] | None = None,
        on_event=None,                       # async callback(dict) for live progress (SSE)
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

        # Prior conversation turns → a compact context block (a follow-up can be elliptical). This
        # only frames search/interpretation; it never becomes a grounded claim (like attachments).
        history_context = None
        if history:
            turns = []
            for t in history:
                qy = (t.get("question") or "").strip()
                an = (t.get("answer") or "").strip()
                if qy:
                    turns.append(f"Q: {qy}\nA: {an[:1200]}" if an else f"Q: {qy}")
            history_context = "\n\n".join(turns) or None

        corpus_src, web_src = self._split_retriever(source_keys)
        res = await run_react(
            question=question, llm=self.llm, embedder=self.embedder,
            source=corpus_src, aux_source=web_src,
            tenant_id=tenant_id, workspace_id=workspace_id,
            budget=budget, gating=self.gating,
            system_prompt=self.persona_prompt, answer_format=self.answer_format,
            attachment_context=attachment_context, history_context=history_context,
            planner_llm=self.planner_llm, on_event=on_event,
            max_steps=max_steps,
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

    async def plan_gaps(self, *, question: str, answer: str, coverage_gaps: list[str]):
        """On-demand plan of what to ADD to the corpus so an under-evidenced question could be
        answered — actionable ingest jobs (over THIS deployment's connectors) + gold-source
        recommendations. Returns None when gap-healing isn't configured for the vertical."""
        if not self.gap_prompt or not self.connectors:
            return None
        from noesis_kernel.research.gap_planner import plan_gap_fill
        return await plan_gap_fill(
            llm=self.llm, gap_prompt=self.gap_prompt, question=question, answer=answer,
            coverage_gaps=coverage_gaps, available_connectors=list(self.connectors.keys()))

    async def suggest(self, *, question: str, answer: str, history: str = "") -> list[str]:
        """On-demand suggested follow-up questions that deepen discovery. [] when unavailable."""
        if not self.suggest_prompt:
            return []
        from noesis_kernel.research.suggest import suggest_followups
        return await suggest_followups(
            llm=self.llm, suggest_prompt=self.suggest_prompt,
            question=question, answer=answer, history=history)

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
