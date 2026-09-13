"""FastAPI router for the Ambient CDS sub-app. Additive + isolated under /ambient.

Flag: NOESIS_AMBIENT (default ON). NOESIS_AMBIENT=0 is a true no-op.
"""
from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Dict, List, Optional

from fastapi import APIRouter
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field

from api.rxcds.engine import PatientContext

from .engine import analyze_encounter
from .modes import MODES

logger = logging.getLogger("noesis.ambient")
_WEB_DIR = Path(__file__).resolve().parent / "web"


def ambient_enabled() -> bool:
    return os.environ.get("NOESIS_AMBIENT", "1") not in ("0", "false", "False", "")


class PatientIn(BaseModel):
    age_years: Optional[float] = None
    weight_kg: Optional[float] = None
    sex: Optional[str] = None
    pregnant: Optional[bool] = None
    egfr: Optional[float] = None
    hepatic_impairment: Optional[str] = None
    allergies: List[str] = Field(default_factory=list)
    conditions: List[str] = Field(default_factory=list)
    current_meds: List[str] = Field(default_factory=list)


class AnalyzeIn(BaseModel):
    transcript: str = Field("", description="The encounter transcript (what was said in the visit).")
    patient: PatientIn = Field(default_factory=PatientIn)
    mode: str = Field("US", description="US or IN (India).")
    recent_hospitalization: bool = Field(False, description="Patient recently discharged (transitions of care).")


def build_router() -> APIRouter:
    router = APIRouter(prefix="/ambient", tags=["ambient-cds"])

    @router.get("/health")
    def health() -> Dict:
        return {"status": "ok", "app": "ambient-cds", "modes": list(MODES.keys())}

    @router.post("/analyze")
    def analyze(body: AnalyzeIn) -> Dict:
        p = body.patient
        ctx = PatientContext(
            age_years=p.age_years, weight_kg=p.weight_kg, sex=(p.sex or None),
            pregnant=p.pregnant, egfr=p.egfr, hepatic_impairment=(p.hepatic_impairment or None),
            allergies=[a.lower() for a in p.allergies],
            conditions=[c.lower() for c in p.conditions], current_meds=p.current_meds,
        )
        return analyze_encounter(body.transcript, ctx, mode=body.mode,
                                 recent_hospitalization=body.recent_hospitalization)

    @router.get("", response_class=HTMLResponse)
    @router.get("/", response_class=HTMLResponse)
    def demo() -> HTMLResponse:
        f = _WEB_DIR / "index.html"
        if not f.exists():
            return HTMLResponse("<h1>Ambient CDS</h1><p>Demo UI not found.</p>", status_code=200)
        return HTMLResponse(f.read_text(encoding="utf-8"))

    logger.info("ambient-cds router mounted at /ambient (modes=%s)", list(MODES.keys()))
    return router
