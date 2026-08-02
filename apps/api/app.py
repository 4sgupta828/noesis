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


def structured_answers() -> bool:
    """Flag (default OFF, Rule 20): when ON, the active vertical's answer_format
    directive shapes the synthesized answer (markdown sections). OFF = flat prose,
    byte-identical to the pre-flag path."""
    return os.environ.get("NOESIS_STRUCTURED_ANSWERS", "").lower() in ("1", "true", "yes")


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
    url: str | None = None           # canonical source page (opens in a new tab)
    document_id: str = ""


class ResearchOut(BaseModel):
    grounded: bool
    answer: str = ""                 # synthesized prose answer, grounded in findings
    claims: list[Citation]           # the verified findings (evidence for the answer)
    coverage_gaps: list[str]
    rejected: int
    source_stats: dict = {}          # source -> {retrieved, cited}
    degraded_sources: dict = {}      # sources that failed this request
    session_id: str | None = None    # saved Q&A id (for history + linking a video)
    stopped_reason: str = ""         # answered | budget | max_steps (observability)
    atoms_gathered: int = 0          # evidence blocks the agent saw (observability)
    retried_empty: bool = False      # the abstention-recovery re-ask fired (observability)


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
    # Flag-gated (Rule 20): only pass the vertical's answer-structure directive when ON.
    # OFF → None → the kernel's flat-prose compose path, byte-identical to pre-flag.
    answer_format = manifest.answer_format if structured_answers() else None
    return ResearchService(
        llm=build_llm(mode=mode), embedder=embedder,
        sources=sources, gating=manifest.gating_policy, persona_prompt=persona,
        answer_format=answer_format,
        vertical_name=manifest.name, ui=manifest.ui,
        connectors=connectors, corpus_source_key=corpus_key,
    )


def create_app(service: ResearchService | None = None) -> FastAPI:
    app = FastAPI(title="Noesis Research", version="0")
    app.state.service = service   # lazily built on first request if None

    def _store():
        """Vertical-isolated research-session store (Postgres-backed). Built once when a
        corpus DSN is configured; None (no persistence) against the fixture corpus."""
        if getattr(app.state, "session_store", "unset") == "unset":
            dsn = os.environ.get("NOESIS_CORPUS_DSN")
            if dsn:
                from api.sessions import SessionStore
                app.state.session_store = SessionStore(dsn, vertical=load_active_vertical().name)
            else:
                app.state.session_store = None
        return app.state.session_store

    async def _attach_video(session_id: str, **kw) -> None:
        store = _store()
        if store is not None:
            await store.attach_video(session_id, **kw)

    # Answer-video add-on — separate, flag-gated router (default OFF). Kept fully out of
    # the research path: mounting it changes nothing about how answers are produced.
    from api.video import build_video_router, video_enabled
    if video_enabled():
        app.include_router(build_video_router(attach_video=_attach_video))

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
        from api.video import video_enabled
        console = ui.console() if ui and hasattr(ui, "console") else {}
        return {
            "vertical": getattr(svc, "vertical_name", ""),
            "sources": list(svc.sources.keys()),
            "navigation": ui.navigation() if ui else [],
            "search_facets": ui.search_facets() if ui else [],
            "console": console,
            "video_enabled": video_enabled(),
            "structured_answers": structured_answers(),
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

    @app.get("/{name}.png")
    def web_png(name: str):
        """Serve a PNG asset from apps/web (logo, brand mark). Basename-only + .png
        guard → no path traversal; only files that exist in the web dir are served."""
        from fastapi.responses import FileResponse
        safe = os.path.basename(name) + ".png"
        f = _WEB_DIR / safe
        if not f.exists():
            raise HTTPException(status_code=404, detail="not found")
        return FileResponse(str(f), media_type="image/png")

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
        ui = getattr(app.state.service, "ui", None)
        def _url(c):
            fn = getattr(ui, "source_url", None)
            try:
                return fn(c.document_id, c.quote) if fn and c.document_id else None
            except Exception:
                return None
        claims = [Citation(text=c.text, quote=c.quote, atom_id=c.atom_id,
                           source=c.source_key, title=c.document_title,
                           url=_url(c), document_id=c.document_id)
                  for c in res.verified_claims]
        # Persist the Q&A (best-effort, vertical-isolated) — never fail the response.
        session_id = None
        store = _store()
        if store is not None:
            try:
                session_id = await store.save(
                    tenant_id=body.tenant_id, workspace_id=body.workspace_id,
                    question=body.question, answer=res.composed_answer,
                    grounded=res.grounded, claims=[c.model_dump() for c in claims],
                    source_stats=res.source_stats, coverage_gaps=res.coverage_gaps,
                    rejected=len(res.rejected_claims), sources=body.sources)
            except Exception:
                session_id = None
        return ResearchOut(
            grounded=res.grounded,
            answer=res.composed_answer,
            claims=claims,
            coverage_gaps=res.coverage_gaps,
            rejected=len(res.rejected_claims),
            source_stats=res.source_stats,
            session_id=session_id,
            stopped_reason=res.stopped_reason,
            atoms_gathered=res.atoms_gathered,
            retried_empty=res.retried_empty,
        )

    @app.get("/sessions")
    async def list_sessions(tenant_id: str = "demo", limit: int = 50) -> dict:
        """Recent saved Q&A for this vertical + tenant (history)."""
        store = _store()
        if store is None:
            return {"sessions": []}
        try:
            return {"sessions": await store.list(tenant_id=tenant_id, limit=min(limit, 200))}
        except Exception as e:
            raise HTTPException(status_code=502, detail=f"session store error: {e}") from e

    @app.get("/sessions/{session_id}")
    async def get_session(session_id: str) -> dict:
        """Full saved Q&A (answer, claims, and any linked video)."""
        store = _store()
        if store is None:
            raise HTTPException(status_code=404, detail="no session store")
        row = await store.get(session_id)
        if row is None:
            raise HTTPException(status_code=404, detail="session not found")
        return row

    return app
