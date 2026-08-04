"""FastAPI app — POST /research over the multi-source agent.

Vertical-neutral: it activates ONE vertical at boot (NOESIS_ACTIVE_VERTICAL) and
serves its sources + gating + persona. Providers run in NOESIS_PROVIDER_MODE
(replay by default → offline/free). A ResearchService can be injected for tests.
"""
from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path

from fastapi import FastAPI, Header, HTTPException
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


def clinical_synthesis() -> bool:
    """Flag (default OFF, Rule 20): when ON (and structured answers are ON), the medical vertical's
    SHARPER clinical-synthesis directive shapes the answer — scope-up-front, registry=protocol-not-
    efficacy, surrogate≠clinical endpoints, preserve specific figures, no citation stacking, no vague
    hype. Same adaptive section set — provenance unchanged. OFF → the base answer_format, byte-identical."""
    return os.environ.get("NOESIS_CLINICAL_SYNTHESIS", "").lower() in ("1", "true", "yes")


def vision_enabled() -> bool:
    """Flag (default OFF, Rule 20): when ON, uploaded image/PDF/DICOM attachments are
    described by the vision pre-step and used as CONTEXT for the grounded research. The
    description is never a verified claim. OFF → attachments are ignored."""
    return os.environ.get("NOESIS_VISION", "").lower() in ("1", "true", "yes")


def gap_healing_enabled() -> bool:
    """Flag (default OFF, Rule 20): when ON, an under-evidenced answer can surface a gap-fill
    plan (LLM-proposed connector ingest jobs) that the user queues, and a background processor
    ingests them into the corpus — self-healing. OFF → no gap plan, endpoints 404, no processor."""
    return os.environ.get("NOESIS_GAP_HEALING", "").lower() in ("1", "true", "yes")


def stream_enabled() -> bool:
    """Flag (default OFF, Rule 20): when ON, /research/stream serves live SSE progress events
    (searching/found/verifying/composing → final). OFF → the endpoint 404s; /research unchanged."""
    return os.environ.get("NOESIS_STREAM", "").lower() in ("1", "true", "yes")


def conversation_enabled() -> bool:
    """Flag (default OFF, Rule 20): when ON, answers become a multi-turn thread — follow-up
    questions carry prior turns as context, the thread persists on one session, and suggested
    follow-ups are offered. OFF → single-answer behavior (each ask is a fresh session)."""
    return os.environ.get("NOESIS_CONVERSATION", "").lower() in ("1", "true", "yes")


class Attachment(BaseModel):
    data: str                              # base64-encoded file bytes
    media_type: str = ""                   # e.g. image/png, application/pdf, application/dicom
    name: str = ""


class ResearchIn(BaseModel):
    question: str
    tenant_id: str
    workspace_id: str | None = None
    sources: list[str] | None = None      # subset of source keys; None = all
    attachments: list[Attachment] | None = None   # images/PDF/DICOM → vision context
    user_name: str | None = None          # asker identity (captured at landing)
    user_email: str | None = None
    history: list[dict] | None = None     # prior turns [{question, answer}] → follow-up context
    session_id: str | None = None         # thread to append this turn to (conversation)


class SuggestIn(BaseModel):
    question: str
    answer: str = ""
    history: list[dict] | None = None


class ExplainIn(BaseModel):
    question: str
    answer: str
    session_id: str | None = None


class GapPlanIn(BaseModel):
    question: str
    answer: str = ""
    coverage_gaps: list[str] = []


class GapQueueIn(BaseModel):
    question: str = ""
    tenant_id: str = "demo"
    jobs: list[dict] = []                  # [{connector, query, limit, kind, rationale, quality}]


class CorpusIngestIn(BaseModel):
    """Bulk prod-direct ingest — the replacement for local download + push. Enqueues connector
    jobs into the corpus queue that the prod processor drains straight into the prod corpus."""
    conditions: list[str] = []             # each → a clinicaltrials + a europepmc job
    trials: int = 300                      # per-condition trial limit
    papers: int = 150                      # per-condition literature limit
    faers_drugs: list[str] = []            # each → a faers adverse-event job
    jobs: list[dict] = []                  # explicit passthrough {connector, query, limit, ...}


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
    visual_observation: str = ""     # labeled AI image description (context, NOT a finding)
    attachment_notes: list[str] = [] # anything skipped when reading attachments


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
    sources["web"] = WebRetrievalSource(
        build_web(mode=mode, domains=getattr(manifest, "web_domains", ())))

    persona = manifest.persona.system_prompt() if manifest.persona else \
        "You are an evidence-grounded research agent."
    # Flag-gated (Rule 20): only pass the vertical's answer-structure directive when ON.
    # OFF → None → the kernel's flat-prose compose path, byte-identical to pre-flag. When the
    # separate clinical-synthesis flag is ALSO on, swap in the sharper directive (A/B seam);
    # falls back to the base format if the vertical doesn't supply one.
    if structured_answers():
        answer_format = manifest.answer_format
        if clinical_synthesis():
            answer_format = getattr(manifest, "clinical_answer_format", None) or manifest.answer_format
    else:
        answer_format = None
    vision_prompt = manifest.vision_prompt if vision_enabled() else None
    gap_prompt = manifest.gap_prompt if gap_healing_enabled() else None
    suggest_prompt = manifest.suggest_prompt if conversation_enabled() else None
    # Use the BEST model for EVERY research step (planning + claim extraction + compose). A cheaper
    # planner (haiku) paraphrased quotes → span-verification rejected them (grounding regression),
    # so planner_llm is left unset and run_react uses `llm` throughout. Optional explicit override.
    planner_model = os.environ.get("NOESIS_PLANNER_MODEL", "")   # empty → same strong model as compose
    planner_llm = build_llm(mode=mode, model=planner_model) if planner_model else None
    claims_first = os.environ.get("NOESIS_CLAIMS_FIRST", "").lower() in ("1", "true", "yes")
    # Evidence selection (flag, default OFF): raise the extractor's per-atom window so full-text
    # effect-size/CI sentences aren't truncated, AND keep the claims most RELEVANT to the question
    # for compose (not the first-come 30). Both are provenance-safe (span+entail gates unchanged).
    evidence_select = os.environ.get("NOESIS_EVIDENCE_SELECT", "").lower() in ("1", "true", "yes")
    atom_cap = int(os.environ.get("NOESIS_ATOM_CAP", "6000" if evidence_select else "1600"))
    return ResearchService(
        llm=build_llm(mode=mode), embedder=embedder, planner_llm=planner_llm,
        claims_first=claims_first, extraction_lenses=getattr(manifest, "extraction_lenses", ()),
        evidence_select=evidence_select, atom_cap=atom_cap,
        sources=sources, gating=manifest.gating_policy, persona_prompt=persona,
        answer_format=answer_format, vision_prompt=vision_prompt,
        layman_prompt=manifest.layman_prompt, gap_prompt=gap_prompt,
        suggest_prompt=suggest_prompt,
        vertical_name=manifest.name, ui=manifest.ui,
        connectors=connectors, corpus_source_key=corpus_key,
    )


def _run_gap_processor(dsn: str, vertical: str) -> None:
    """Entry point for the DEDICATED ingest thread. Runs its own event loop so the heavy work
    (connector fetch + blocking OpenAI embed + index) never blocks the API's serving loop — this
    is what makes prod-direct ingestion, at bulk scale, safe to run inside the API process."""
    import asyncio as _a
    _a.run(_gap_processor_loop(dsn, vertical))


async def _gap_processor_loop(dsn: str, vertical: str) -> None:
    """One-at-a-time queue drain, on the ingest thread's own loop with its own pg pool + embedder +
    connectors. Atomic claim → replica-safe; a single job's error is recorded and the loop continues
    (Rule 13). Connectors open a fresh httpx client per call, so they are safe on this loop."""
    import asyncio
    from api.gap_queue import GapQueue
    from noesis_kernel.providers.base import resolve_mode
    from noesis_kernel.retrieval.postgres import PostgresRetrievalSource
    from noesis_kernel.runtime.build import build_embedder, load_active_vertical
    q = GapQueue(dsn, vertical=vertical)
    embedder = build_embedder(mode=resolve_mode())
    pg = PostgresRetrievalSource(dsn, dim=embedder.dim, table="rs_block")
    connectors = dict(load_active_vertical().connectors)
    while True:
        try:
            job = await q.claim_one()
        except Exception:
            await asyncio.sleep(10); continue
        if job is None:
            await asyncio.sleep(8); continue
        conn = connectors.get(job["connector"])
        if conn is None:
            await q.fail(job["id"], f"unknown connector {job['connector']}"); continue
        try:
            n = await ingest_connector_to_postgres(
                conn, pg, tenant_id=job["tenant_id"], embedder=embedder,
                window={"query": job["query"], "limit": job["limit"]})
            await q.complete(job["id"], n)
        except Exception as e:   # noqa: BLE001 — record + move on
            await q.fail(job["id"], str(e))


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

    def _gap_queue():
        """Vertical-isolated corpus gap-fill queue (Postgres). None unless a corpus DSN is set
        AND gap-healing is enabled — so OFF is a true no-op."""
        if getattr(app.state, "gap_queue", "unset") == "unset":
            dsn = os.environ.get("NOESIS_CORPUS_DSN")
            if dsn and gap_healing_enabled():
                from api.gap_queue import GapQueue
                app.state.gap_queue = GapQueue(dsn, vertical=load_active_vertical().name)
            else:
                app.state.gap_queue = None
        return app.state.gap_queue

    @app.on_event("startup")
    async def _start_gap_processor() -> None:
        """Launch the corpus-ingest processor in a DEDICATED daemon thread (own loop + pools), so
        prod-direct ingestion (gap-fill AND bulk batches) never blocks the API's serving loop.
        Replica-safe: each replica's thread claims jobs atomically, so N replicas share the drain."""
        dsn = os.environ.get("NOESIS_CORPUS_DSN")
        if gap_healing_enabled() and dsn and not getattr(app.state, "_gap_thread", None):
            import threading
            vertical = load_active_vertical().name
            t = threading.Thread(target=_run_gap_processor, args=(dsn, vertical),
                                 daemon=True, name="corpus-ingest")
            t.start()
            app.state._gap_thread = t

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
            "clinical_synthesis": clinical_synthesis() and structured_answers(),
            "evidence_select": bool(getattr(svc, "evidence_select", False)),
            "vision_enabled": vision_enabled(),
            "layman_enabled": bool(getattr(svc, "layman_prompt", None)),
            "gap_healing_enabled": gap_healing_enabled() and bool(getattr(svc, "gap_prompt", None)),
            "conversation_enabled": conversation_enabled(),
            "suggest_enabled": conversation_enabled() and bool(getattr(svc, "suggest_prompt", None)),
            "stream_enabled": stream_enabled(),
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
        try:
            return await _do_research(body)
        except CassetteMiss as e:
            raise HTTPException(status_code=503, detail=(
                "No model available in replay mode. Set NOESIS_PROVIDER_MODE=live "
                "with ANTHROPIC_API_KEY + OPENAI_API_KEY to answer live, or record "
                "cassettes first.")) from e
        except Exception as e:   # provider errors (auth, credits, rate limit, timeout)
            raise HTTPException(status_code=502, detail=f"provider error: {e}") from e

    async def _do_research(body: ResearchIn, on_event=None) -> ResearchOut:
        """Shared research core: attachments → ask (optional live on_event) → persist → ResearchOut.
        Raises CassetteMiss / provider errors for the caller to handle."""
        if app.state.service is None:
            app.state.service = build_default_service()
        images, docs, attach_notes, previews = None, None, [], []
        if body.attachments and vision_enabled():
            from api.media import attachments_to_media, session_previews
            images, docs, attach_notes = attachments_to_media(
                [a.model_dump() for a in body.attachments])
            previews = session_previews(images or [], docs or [])
        history = body.history if conversation_enabled() else None
        res = await app.state.service.ask(
            question=body.question, tenant_id=body.tenant_id,
            workspace_id=body.workspace_id, source_keys=body.sources,
            images=images, documents=docs, history=history, on_event=on_event)
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
        # Persist the Q&A (best-effort). Conversation follow-up (session_id + flag) APPENDS a turn.
        session_id = None
        store = _store()
        claim_dicts = [c.model_dump() for c in claims]
        if store is not None:
            turn = {"question": body.question, "answer": res.composed_answer,
                    "grounded": res.grounded, "claims": claim_dicts,
                    "source_stats": res.source_stats, "coverage_gaps": res.coverage_gaps,
                    "rejected": len(res.rejected_claims),
                    "visual_observation": res.visual_observation, "attachments": previews}
            try:
                if conversation_enabled() and body.session_id and \
                        await store.append_turn(body.session_id, turn):
                    session_id = body.session_id
                else:
                    session_id = await store.save(
                        tenant_id=body.tenant_id, workspace_id=body.workspace_id,
                        question=body.question, answer=res.composed_answer,
                        grounded=res.grounded, claims=claim_dicts,
                        source_stats=res.source_stats, coverage_gaps=res.coverage_gaps,
                        rejected=len(res.rejected_claims), sources=body.sources,
                        user_name=body.user_name, user_email=body.user_email,
                        visual_observation=res.visual_observation, attachments=previews)
            except Exception:
                session_id = None
        return ResearchOut(
            grounded=res.grounded, answer=res.composed_answer, claims=claims,
            coverage_gaps=res.coverage_gaps, rejected=len(res.rejected_claims),
            source_stats=res.source_stats, session_id=session_id,
            stopped_reason=res.stopped_reason, atoms_gathered=res.atoms_gathered,
            retried_empty=res.retried_empty, visual_observation=res.visual_observation,
            attachment_notes=attach_notes,
        )

    @app.post("/research/stream")
    async def research_stream(body: ResearchIn):
        """Live SSE progress for a research request: emits step/search/found/verifying/composing
        events as the ReAct loop runs, then a `final` event carrying the full ResearchOut. Progress
        events are read-only (never unverified claims); persistence + the final payload happen once
        at the end, exactly like /research."""
        if not stream_enabled():
            raise HTTPException(status_code=404, detail="streaming not enabled")
        from fastapi.responses import StreamingResponse
        queue: asyncio.Queue = asyncio.Queue()

        async def on_event(ev: dict) -> None:
            await queue.put(ev)

        async def run() -> None:
            try:
                out = await _do_research(body, on_event=on_event)
                await queue.put({"type": "final", "result": out.model_dump()})
            except CassetteMiss:
                await queue.put({"type": "error", "detail": "No model available in replay mode."})
            except Exception as e:   # noqa: BLE001
                await queue.put({"type": "error", "detail": f"provider error: {e}"})
            finally:
                await queue.put(None)   # sentinel: stream complete

        async def gen():
            task = asyncio.create_task(run())
            try:
                yield ": open\n\n"                        # flush headers immediately
                while True:
                    try:
                        ev = await asyncio.wait_for(queue.get(), timeout=15)
                    except asyncio.TimeoutError:
                        yield ": ping\n\n"; continue      # keepalive so proxies don't cut the stream
                    if ev is None:
                        break
                    yield f"data: {json.dumps(ev)}\n\n"
            finally:
                if not task.done():
                    task.cancel()

        return StreamingResponse(gen(), media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no", "Connection": "keep-alive"})

    @app.post("/explain")
    async def explain(body: ExplainIn) -> dict:
        """On-demand plain-language re-explanation of a grounded answer (same doctor →
        patient). Saved on the session when a session_id is given."""
        if app.state.service is None:
            app.state.service = build_default_service()
        svc = app.state.service
        if not getattr(svc, "layman_prompt", None):
            raise HTTPException(status_code=404, detail="plain-language explanation not available")
        try:
            text = await svc.explain(question=body.question, answer=body.answer)
        except CassetteMiss as e:
            raise HTTPException(status_code=503, detail="No model available in replay mode.") from e
        except Exception as e:
            raise HTTPException(status_code=502, detail=f"provider error: {e}") from e
        if body.session_id and text:
            store = _store()
            if store is not None:
                try:
                    await store.save_layman(body.session_id, text)
                except Exception:
                    pass
        return {"explanation": text}

    @app.post("/suggest")
    async def suggest(body: SuggestIn) -> dict:
        """On-demand suggested follow-up questions for deeper discovery (conversation feature).
        Called after an answer renders, so it never adds latency to the answer itself."""
        if not conversation_enabled():
            raise HTTPException(status_code=404, detail="suggestions not enabled")
        if app.state.service is None:
            app.state.service = build_default_service()
        svc = app.state.service
        if not getattr(svc, "suggest_prompt", None):
            raise HTTPException(status_code=404, detail="suggestions not available for this vertical")
        hist = ""
        if body.history:
            hist = "\n\n".join(
                f"Q: {(t.get('question') or '').strip()}" for t in body.history if t.get("question"))
        try:
            qs = await svc.suggest(question=body.question, answer=body.answer, history=hist)
        except CassetteMiss as e:
            raise HTTPException(status_code=503, detail="No model available in replay mode.") from e
        except Exception as e:
            raise HTTPException(status_code=502, detail=f"provider error: {e}") from e
        return {"suggestions": qs}

    @app.post("/corpus/gap-plan")
    async def corpus_gap_plan(body: GapPlanIn) -> dict:
        """On-demand: what to ADD to the corpus so an under-evidenced question could be answered.
        LLM-proposed ingest jobs (over this deployment's connectors) + gold-source recommendations.
        Read-only — proposes; it does not queue or ingest anything."""
        if not gap_healing_enabled():
            raise HTTPException(status_code=404, detail="gap healing not enabled")
        if app.state.service is None:
            app.state.service = build_default_service()
        svc = app.state.service
        try:
            plan = await svc.plan_gaps(
                question=body.question, answer=body.answer, coverage_gaps=body.coverage_gaps)
        except CassetteMiss as e:
            raise HTTPException(status_code=503, detail="No model available in replay mode.") from e
        except Exception as e:
            raise HTTPException(status_code=502, detail=f"provider error: {e}") from e
        if plan is None:
            raise HTTPException(status_code=404, detail="gap healing not available for this vertical")
        return {
            "summary": plan.summary,
            "jobs": [j.model_dump() for j in plan.jobs],
            "recommendations": [r.model_dump() for r in plan.recommendations],
            "connectors": list(svc.connectors.keys()),
        }

    @app.post("/corpus/queue")
    async def corpus_queue_add(body: GapQueueIn) -> dict:
        """Queue user-approved gap-fill jobs. Validates every job against the real connector set
        and caps the limit (code owns structure) before persisting for the background processor."""
        if not gap_healing_enabled():
            raise HTTPException(status_code=404, detail="gap healing not enabled")
        q = _gap_queue()
        if q is None:
            raise HTTPException(status_code=404, detail="no corpus queue configured")
        if app.state.service is None:
            app.state.service = build_default_service()
        allowed = set(app.state.service.connectors.keys())
        clean = []
        for j in body.jobs or []:
            c = (j.get("connector") or "").strip()
            query = (j.get("query") or "").strip()
            if c not in allowed or not query:
                continue
            clean.append({
                "connector": c, "query": query,
                "limit": max(1, min(int(j.get("limit") or 200), 400)),
                "kind": (j.get("kind") or "")[:80],
                "rationale": (j.get("rationale") or "")[:400],
                "quality": (j.get("quality") or "")[:120],
            })
        if not clean:
            raise HTTPException(status_code=400, detail="no valid jobs (unknown connector or empty query)")
        try:
            ids = await q.enqueue(tenant_id=body.tenant_id, question=body.question, jobs=clean)
        except Exception as e:
            raise HTTPException(status_code=502, detail=f"queue error: {e}") from e
        return {"queued": len(ids), "ids": ids}

    @app.get("/corpus/queue")
    async def corpus_queue_status(limit: int = 50) -> dict:
        """Gap-fill queue status (pending/running/done/failed + blocks added) — self-healing progress."""
        q = _gap_queue()
        if q is None:
            return {"enabled": gap_healing_enabled(), "jobs": [], "summary": {}}
        try:
            return {"enabled": True, "jobs": await q.list(limit=min(limit, 200)),
                    "summary": await q.summary()}
        except Exception as e:
            raise HTTPException(status_code=502, detail=f"queue error: {e}") from e

    @app.post("/admin/corpus/ingest")
    async def admin_corpus_ingest(body: CorpusIngestIn, x_admin_token: str = Header(default="")) -> dict:
        """Bulk prod-direct ingest — replaces 'download locally + push to prod'. Expands conditions
        into clinicaltrials + europepmc jobs (and FAERS drugs into adverse-event jobs), validates
        against the real connector set, and enqueues them for the prod processor. Guarded by
        NOESIS_ADMIN_TOKEN when set (this endpoint spends credits + mutates the corpus)."""
        if not gap_healing_enabled():
            raise HTTPException(status_code=404, detail="corpus ingestion not enabled")
        want = os.environ.get("NOESIS_ADMIN_TOKEN", "")
        if want and x_admin_token != want:
            raise HTTPException(status_code=401, detail="admin token required")
        q = _gap_queue()
        if q is None:
            raise HTTPException(status_code=404, detail="no corpus queue configured")
        if app.state.service is None:
            app.state.service = build_default_service()
        allowed = set(app.state.service.connectors.keys())
        cap = lambda n, d: max(1, min(int(n or d), 400))
        jobs: list[dict] = []
        for cond in body.conditions:
            c = (cond or "").strip()
            if not c:
                continue
            if "clinicaltrials" in allowed:
                jobs.append({"connector": "clinicaltrials", "query": c, "limit": cap(body.trials, 300),
                             "kind": "trials", "quality": "batch"})
            if "europepmc" in allowed:
                jobs.append({"connector": "europepmc", "query": c, "limit": cap(body.papers, 150),
                             "kind": "literature", "quality": "batch"})
        for drug in body.faers_drugs:
            d = (drug or "").strip()
            if d and "faers" in allowed:
                jobs.append({"connector": "faers", "query": d, "limit": 200,
                             "kind": "adverse events", "quality": "batch"})
        for j in body.jobs or []:
            c = (j.get("connector") or "").strip()
            query = (j.get("query") or "").strip()
            if c in allowed and query:
                jobs.append({"connector": c, "query": query, "limit": cap(j.get("limit"), 200),
                             "kind": (j.get("kind") or "")[:80], "quality": (j.get("quality") or "")[:120]})
        if not jobs:
            raise HTTPException(status_code=400, detail="no valid jobs (unknown connector or empty inputs)")
        try:
            ids = await q.enqueue(tenant_id="demo", question="admin bulk ingest", jobs=jobs)
        except Exception as e:
            raise HTTPException(status_code=502, detail=f"queue error: {e}") from e
        return {"queued": len(ids), "jobs": len(jobs)}

    @app.get("/sessions")
    async def list_sessions(tenant_id: str = "demo", limit: int = 100, q: str = "") -> dict:
        """Recent saved Q&A for this vertical + tenant (history), optional search `q`."""
        store = _store()
        if store is None:
            return {"sessions": []}
        try:
            return {"sessions": await store.list(tenant_id=tenant_id, limit=min(limit, 300), q=q or None)}
        except Exception as e:
            raise HTTPException(status_code=502, detail=f"session store error: {e}") from e

    @app.get("/videos")
    async def list_videos(tenant_id: str = "demo", limit: int = 200) -> dict:
        """All briefing videos across sessions (for the video catalogue)."""
        store = _store()
        if store is None:
            return {"videos": []}
        try:
            vids = await store.list_videos(tenant_id=tenant_id, limit=min(limit, 300))
            # hide videos whose file is gone (local + R2 both missing)
            from api.video import video_exists
            vids = await asyncio.to_thread(
                lambda: [v for v in vids if video_exists(v["video_filename"])])
            return {"videos": vids}
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

    @app.delete("/sessions/{session_id}")
    async def delete_session(session_id: str) -> dict:
        """Soft-delete a session (hidden from list/get; row retained)."""
        store = _store()
        if store is None:
            raise HTTPException(status_code=404, detail="no session store")
        if not await store.soft_delete(session_id):
            raise HTTPException(status_code=404, detail="session not found")
        return {"deleted": True}

    @app.get("/admin/coverage")
    async def admin_coverage() -> dict:
        """Live corpus coverage: what's ingested (per source/kind + per-download runs) and
        the declared roadmap (covered vs remaining conditions) from the active vertical."""
        if app.state.service is None:
            app.state.service = build_default_service()
        svc = app.state.service
        ui = getattr(svc, "ui", None)
        plan = ui.coverage_plan() if ui and hasattr(ui, "coverage_plan") else {}
        live: dict = {"by_source": {}, "by_kind": {}, "total_blocks": 0,
                      "total_docs": 0, "runs": []}
        dsn = os.environ.get("NOESIS_CORPUS_DSN")
        if dsn:
            import json
            import asyncpg
            conn = await asyncpg.connect(dsn)
            try:
                for r in await conn.fetch(
                    "SELECT source_key, count(*) blocks, count(DISTINCT document_id) docs "
                    "FROM rs_block GROUP BY source_key"):
                    live["by_source"][r["source_key"] or "?"] = {"blocks": r["blocks"], "docs": r["docs"]}
                for r in await conn.fetch(
                    "SELECT facets->>'source_kind' kind, count(*) blocks FROM rs_block GROUP BY 1"):
                    if r["kind"]:
                        live["by_kind"][r["kind"]] = r["blocks"]
                live["total_blocks"] = await conn.fetchval("SELECT count(*) FROM rs_block") or 0
                live["total_docs"] = await conn.fetchval("SELECT count(DISTINCT document_id) FROM rs_block") or 0
                if await conn.fetchval("SELECT to_regclass('rs_ingest_run')"):
                    for r in await conn.fetch(
                        "SELECT condition, by_source, total_blocks, created_at FROM rs_ingest_run "
                        "ORDER BY created_at DESC LIMIT 200"):
                        bs = r["by_source"]
                        live["runs"].append({
                            "condition": r["condition"],
                            "by_source": json.loads(bs) if isinstance(bs, str) else (bs or {}),
                            "total_blocks": r["total_blocks"],
                            "created_at": r["created_at"].isoformat() if r["created_at"] else None,
                        })
            except Exception as e:  # noqa: BLE001
                live["error"] = str(e)
            finally:
                await conn.close()
        return {"vertical": getattr(svc, "vertical_name", ""), "plan": plan, "live": live}

    @app.get("/admin", response_class=HTMLResponse)
    def admin_page() -> str:
        page = _WEB_DIR / "admin.html"
        return page.read_text() if page.exists() else "<h1>Noesis admin</h1>"

    return app
