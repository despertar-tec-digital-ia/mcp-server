"""REST + GHL webhook for the market-validation agent (ADR-0004, Fase 1)."""
from typing import Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.auth import require_api_key
from app.clients.validacion.agent import validate_niche

router = APIRouter(prefix="/validacion", tags=["validacion"], dependencies=[Depends(require_api_key)])


class ValidacionRequest(BaseModel):
    niche: str
    geo: Optional[str] = None
    # GHL passes the contact so Fase 2 can write the score back to the CRM.
    contact_id: Optional[str] = None
    email: Optional[str] = None


@router.post("/run")
async def run_validacion(body: ValidacionRequest):
    report = await validate_niche(body.niche, geo=body.geo)
    if body.contact_id:
        report["contact_id"] = body.contact_id
    return report
