"""FastAPI app — POST /research over the multi-source agent.

Vertical-neutral: it activates ONE vertical at boot (NOESIS_ACTIVE_VERTICAL) and
serves its sources + gating + persona. Providers run in NOESIS_PROVIDER_MODE
(replay by default → offline/free). A ResearchService can be injected for tests.
"""
from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from pydantic import BaseModel

_WEB_DIR = Path(__file__).resolve().parent.parent / "web"

from noesis_kernel.providers.base import resolve_mode
from noesis_kernel.runtime.build import build_embedder, build_llm, build_web, load_active_vertical
from noesis_kernel.runtime.research import ResearchService
from noesis_kernel.retrieval.web import WebRetrievalSource


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


def build_default_service() -> ResearchService:
    """Assemble the service from the active vertical + env providers.

    NOTE: the corpus source's embedding dimension must match the query embedder;
    in production the corpus is Postgres-backed with OpenAI embeddings (1536) and
    the query embedder matches. Deployment wiring finalizes this alignment.
    """
    manifest = load_active_vertical()
    mode = resolve_mode()
    sources = dict(manifest.retrieval_sources)
    sources["web"] = WebRetrievalSource(build_web(mode=mode))
    persona = manifest.persona.system_prompt() if manifest.persona else \
        "You are an evidence-grounded research agent."
    return ResearchService(
        llm=build_llm(mode=mode), embedder=build_embedder(mode=mode),
        sources=sources, gating=manifest.gating_policy, persona_prompt=persona,
        vertical_name=manifest.name, ui=manifest.ui,
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

    @app.get("/", response_class=HTMLResponse)
    def index() -> str:
        page = _WEB_DIR / "index.html"
        return page.read_text() if page.exists() else "<h1>Noesis</h1>"

    @app.post("/research", response_model=ResearchOut)
    async def research(body: ResearchIn) -> ResearchOut:
        if app.state.service is None:
            app.state.service = build_default_service()
        res = await app.state.service.ask(
            question=body.question, tenant_id=body.tenant_id,
            workspace_id=body.workspace_id, source_keys=body.sources,
        )
        return ResearchOut(
            grounded=res.grounded,
            claims=[Citation(text=c.text, quote=c.quote, atom_id=c.atom_id,
                             source=c.source_key, title=c.document_title)
                    for c in res.verified_claims],
            coverage_gaps=res.coverage_gaps,
            rejected=len(res.rejected_claims),
        )

    return app
