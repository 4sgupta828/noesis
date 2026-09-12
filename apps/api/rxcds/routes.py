"""FastAPI router for the Rx-CDS sub-app. Additive + isolated under /rx.

Flag: NOESIS_RXCDS (default ON — this is a standalone demo sub-app that never touches the
research path). Set NOESIS_RXCDS=0 to make it a no-op.
"""
from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Dict, List, Optional

from fastapi import APIRouter
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field

from . import data
from .engine import PatientContext, check_prescription

logger = logging.getLogger("noesis.rxcds")

_WEB_DIR = Path(__file__).resolve().parent / "web"


def rxcds_enabled() -> bool:
    return os.environ.get("NOESIS_RXCDS", "1") not in ("0", "false", "False", "")


class RxItem(BaseModel):
    text: str = Field(..., description="Prescription line as written (brand or molecule), e.g. 'Augmentin 625'.")
    dose_mg: Optional[float] = Field(None, description="mg per administration, if known.")
    frequency_per_day: Optional[float] = Field(None, description="administrations per day, if known.")


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


class CheckIn(BaseModel):
    prescription: List[RxItem] = Field(default_factory=list)
    patient: PatientIn = Field(default_factory=PatientIn)


def build_router() -> APIRouter:
    router = APIRouter(prefix="/rx", tags=["rx-cds"])

    @router.get("/health")
    def rx_health() -> Dict:
        return {"status": "ok", "app": "rx-cds", "brands_known": len(data.BRANDS)}

    @router.get("/formulary")
    def formulary() -> Dict:
        """Known brands + molecules — powers the demo's suggestions."""
        return {"brands": sorted(data.BRANDS.keys()), "molecules": data.all_molecules()}

    @router.post("/check")
    def check(body: CheckIn) -> Dict:
        p = body.patient
        ctx = PatientContext(
            age_years=p.age_years, weight_kg=p.weight_kg, sex=(p.sex or None),
            pregnant=p.pregnant, egfr=p.egfr,
            hepatic_impairment=(p.hepatic_impairment or None),
            allergies=[a.lower() for a in p.allergies],
            conditions=[c.lower() for c in p.conditions],
            current_meds=p.current_meds,
        )
        items_raw = [it.text for it in body.prescription]
        item_meta = [{"dose_mg": it.dose_mg, "frequency_per_day": it.frequency_per_day}
                     for it in body.prescription]
        return check_prescription(items_raw, ctx, item_meta=item_meta)

    @router.get("", response_class=HTMLResponse)
    @router.get("/", response_class=HTMLResponse)
    def demo() -> HTMLResponse:
        f = _WEB_DIR / "index.html"
        if not f.exists():
            return HTMLResponse("<h1>Rx-CDS</h1><p>Demo UI not found.</p>", status_code=200)
        return HTMLResponse(f.read_text(encoding="utf-8"))

    logger.info("rx-cds router mounted at /rx (brands=%d)", len(data.BRANDS))
    return router
