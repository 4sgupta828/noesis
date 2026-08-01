"""Answer-video add-on — a COMPLETELY SEPARATE, flag-gated router.

It turns a delivered {question, answer} into a short narrated explainer mp4 by shelling
out to the standalone NovelFusion bridge (`bin/answer-video.ts`). It does NOT import or
touch the kernel research core, retrieval, or providers — the research path runs
identically whether this add-on is present or not.

Default OFF (Rule 20): enable with NOESIS_VIDEO_ENABLED=true. Generation spends OpenAI/
Anthropic credits (storyboard LLM + TTS), so it is opt-in and never on the answer path.

Config (env):
  NOESIS_VIDEO_ENABLED   "true" to mount the router (default off).
  NOESIS_VIDEO_NF_DIR    NovelFusion repo dir (default ~/novelfusion).
  NOESIS_VIDEO_TSX       tsx binary (default <nf>/node_modules/.bin/tsx).

Generation is async (a job runs in the background ~2 min); the UI polls status then
streams the file.
"""
from __future__ import annotations

import asyncio
import json
import os
import uuid
from dataclasses import dataclass, field
from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel


def video_enabled() -> bool:
    return os.environ.get("NOESIS_VIDEO_ENABLED", "").lower() in ("1", "true", "yes")


def _nf_dir() -> Path:
    return Path(os.environ.get("NOESIS_VIDEO_NF_DIR", str(Path.home() / "novelfusion")))


def _tsx() -> str:
    return os.environ.get("NOESIS_VIDEO_TSX", str(_nf_dir() / "node_modules" / ".bin" / "tsx"))


class VideoIn(BaseModel):
    question: str
    answer: str
    title: str | None = None


@dataclass
class _Job:
    status: str = "running"      # running | done | error
    filename: str = ""
    title: str = ""
    duration_sec: float = 0.0
    error: str = ""


# In-process job registry. Fine for a single-node add-on; a multi-node deployment would
# back this with a table, but the add-on is deliberately lightweight and node-local.
_JOBS: dict[str, _Job] = {}


async def _run_bridge(job_id: str, payload: dict) -> None:
    job = _JOBS[job_id]
    nf, tsx = _nf_dir(), _tsx()
    if not (nf / "bin" / "answer-video.ts").exists():
        job.status, job.error = "error", f"bridge not found at {nf}/bin/answer-video.ts"
        return
    try:
        proc = await asyncio.create_subprocess_exec(
            tsx, "bin/answer-video.ts",
            cwd=str(nf),
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        out, err = await proc.communicate(json.dumps(payload).encode())
        if proc.returncode != 0:
            job.status = "error"
            job.error = (err.decode(errors="replace") or "bridge failed").strip()[-800:]
            return
        # Result is the LAST non-empty stdout line (JSON).
        lines = [ln for ln in out.decode(errors="replace").splitlines() if ln.strip()]
        result = json.loads(lines[-1])
        job.status = "done"
        job.filename = os.path.basename(result["filename"])   # basename only — no path traversal
        job.title = result.get("title", "")
        job.duration_sec = float(result.get("durationSec", 0) or 0)
    except Exception as e:   # noqa: BLE001 — surface any failure to the poller
        job.status, job.error = "error", str(e)[-800:]


def build_video_router() -> APIRouter:
    router = APIRouter(prefix="/video", tags=["video"])

    @router.post("/generate")
    async def generate(body: VideoIn) -> dict:
        job_id = uuid.uuid4().hex
        _JOBS[job_id] = _Job(title=body.title or body.question[:80])
        payload = {"question": body.question, "answer": body.answer,
                   "title": body.title or body.question[:80]}
        asyncio.create_task(_run_bridge(job_id, payload))
        return {"job_id": job_id, "status": "running"}

    @router.get("/status/{job_id}")
    def status(job_id: str) -> dict:
        job = _JOBS.get(job_id)
        if job is None:
            raise HTTPException(status_code=404, detail="unknown job")
        return {"status": job.status, "filename": job.filename, "title": job.title,
                "duration_sec": job.duration_sec, "error": job.error}

    @router.get("/file/{filename}")
    def file(filename: str) -> FileResponse:
        # Basename-only + fixed dir → no traversal; must be an .mp4 we produced.
        name = os.path.basename(filename)
        if not name.endswith(".mp4"):
            raise HTTPException(status_code=400, detail="bad filename")
        path = _nf_dir() / "data" / "fusion" / name
        if not path.exists():
            raise HTTPException(status_code=404, detail="video not found")
        return FileResponse(str(path), media_type="video/mp4", filename=name)

    return router
