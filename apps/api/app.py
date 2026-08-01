"""FastAPI app — POST /research over the multi-source agent.

Vertical-neutral: it activates ONE vertical at boot (NOESIS_ACTIVE_VERTICAL) and
serves its sources + gating + persona. Providers run in NOESIS_PROVIDER_MODE
(replay by default → offline/free). A ResearchService can be injected for tests.
"""
from __future__ import annotations

import os
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel

from noesis_kernel.providers.base import resolve_mode
from noesis_kernel.providers.cassette import CassetteMiss
from noesis_kernel.retrieval.postgres import PostgresRetrievalSource
from noesis_kernel.retrieval.web import WebRetrievalSource
from noesis_kernel.runtime.build import build_embedder, build_llm, build_web, load_active_vertical
from noesis_kernel.runtime.ingest import ingest_connector_to_postgres
from noesis_kernel.runtime.research import ResearchService

_WEB_DIR = Path(__file__).resolve().parent.parent / "web"


class ResearchIn(BaseModel):
    question: str
    tenant_id: str
    workspace_id: str | None = None
    sources: list[str] | None = None      # subset of source keys; None = all


class Citation(BaseModel):
    text: str
    quote: str
    atom_id: str
    source: str = ""
    title: str = ""


class ResearchOut(BaseModel):
    grounded: bool
    claims: list[Citation]
    coverage_gaps: list[str]
    rejected: int
    source_stats: dict = {}          # source -> {retrieved, cited}
    degraded_sources: dict = {}      # sources that failed this request


def build_default_service() -> ResearchService:
    """Assemble the service from the active vertical + env providers.

    NOTE: the corpus source's embedding dimension must match the query embedder;
    in production the corpus is Postgres-backed with OpenAI embeddings (1536) and
    the query embedder matches. Deployment wiring finalizes this alignment.
    """
    manifest = load_active_vertical()
    mode = resolve_mode()
    embedder = build_embedder(mode=mode)
    dsn = os.environ.get("NOESIS_CORPUS_DSN")

    sources: dict = {}
    connectors: dict = {}
    corpus_key = ""
    if dsn:
        # Real pgvector corpus (empty until POST /ingest). One pg source, registered
        # under the vertical's corpus source key so gating/covers still align.
        covers = next((s.covers() for s in manifest.retrieval_sources.values()
                       if hasattr(s, "covers")), {})
        pg = PostgresRetrievalSource(dsn, dim=embedder.dim, table="rs_block", covers=covers)
        corpus_key = next(iter(manifest.retrieval_sources), "corpus")
        sources[corpus_key] = pg
        connectors = dict(manifest.connectors)
    else:
        sources = dict(manifest.retrieval_sources)      # fixture (in-memory) corpus
    sources["web"] = WebRetrievalSource(build_web(mode=mode))

    persona = manifest.persona.system_prompt() if manifest.persona else \
        "You are an evidence-grounded research agent."
    return ResearchService(
        llm=build_llm(mode=mode), embedder=embedder,
        sources=sources, gating=manifest.gating_policy, persona_prompt=persona,
        vertical_name=manifest.name, ui=manifest.ui,
        connectors=connectors, corpus_source_key=corpus_key,
    )


def create_app(service: ResearchService | None = None) -> FastAPI:
    app = FastAPI(title="Noesis Research", version="0")
    app.state.service = service   # lazily built on first request if None

    @app.get("/health")
    def health() -> dict:
        return {"status": "ok"}

    @app.get("/config")
    def config() -> dict:
        """The active vertical's declared UI + available sources (drives the shell)."""
        if app.state.service is None:
            app.state.service = build_default_service()
        svc = app.state.service
        ui = getattr(svc, "ui", None)
        return {
            "vertical": getattr(svc, "vertical_name", ""),
            "sources": list(svc.sources.keys()),
            "navigation": ui.navigation() if ui else [],
            "search_facets": ui.search_facets() if ui else [],
        }

    @app.post("/search")
    async def search(body: ResearchIn) -> dict:
        """Retrieval only (no LLM) — ranked evidence over the chosen sources.
        Always available (needs only the embedder), so the UI can show real
        evidence even when the answer model is unavailable."""
        if app.state.service is None:
            app.state.service = build_default_service()
        try:
            hits = await app.state.service.search(
                question=body.question, tenant_id=body.tenant_id,
                workspace_id=body.workspace_id, source_keys=body.sources, k=8)
        except Exception as e:
            raise HTTPException(status_code=502, detail=f"retrieval error: {e}") from e
        return {"evidence": [{
            "text": h.text[:600], "source": h.source_key or "corpus",
            "title": h.document_title, "score": round(h.score, 4),
        } for h in hits]}

    @app.post("/ingest")
    async def ingest(tenant_id: str = "demo") -> dict:
        """Populate the pg-backed corpus from the active vertical's connectors.
        No-op with a note if no NOESIS_CORPUS_DSN is configured (fixture corpus)."""
        if app.state.service is None:
            app.state.service = build_default_service()
        svc = app.state.service
        if not svc.connectors or not svc.corpus_source_key:
            return {"ingested": 0, "note": "no pg corpus configured — set NOESIS_CORPUS_DSN"}
        pg = svc.sources[svc.corpus_source_key]
        total = 0
        for conn in svc.connectors.values():
            total += await ingest_connector_to_postgres(
                conn, pg, tenant_id=tenant_id, embedder=svc.embedder)
        return {"ingested": total, "tenant_id": tenant_id}

    @app.get("/", response_class=HTMLResponse)
    def index() -> str:
        page = _WEB_DIR / "index.html"
        return page.read_text() if page.exists() else "<h1>Noesis</h1>"

    @app.post("/research", response_model=ResearchOut)
    async def research(body: ResearchIn) -> ResearchOut:
        if app.state.service is None:
            app.state.service = build_default_service()
        try:
            res = await app.state.service.ask(
                question=body.question, tenant_id=body.tenant_id,
                workspace_id=body.workspace_id, source_keys=body.sources,
            )
        except CassetteMiss as e:
            raise HTTPException(status_code=503, detail=(
                "No model available in replay mode. Set NOESIS_PROVIDER_MODE=live "
                "with ANTHROPIC_API_KEY + OPENAI_API_KEY to answer live, or record "
                "cassettes first.")) from e
        except Exception as e:   # provider errors (auth, credits, rate limit, timeout)
            raise HTTPException(status_code=502, detail=f"provider error: {e}") from e
        return ResearchOut(
            grounded=res.grounded,
            claims=[Citation(text=c.text, quote=c.quote, atom_id=c.atom_id,
                             source=c.source_key, title=c.document_title)
                    for c in res.verified_claims],
            coverage_gaps=res.coverage_gaps,
            rejected=len(res.rejected_claims),
            source_stats=res.source_stats,
        )

    return app
