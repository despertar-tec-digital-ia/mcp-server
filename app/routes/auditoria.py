"""REST endpoints for the site audit tools (consumed by the panel "audit" button)."""
from fastapi import APIRouter, Depends, Query

from app.auth import require_api_key
from app.clients.auditoria.seo import audit_seo
from app.clients.auditoria.health import check_site

router = APIRouter(prefix="/auditoria", tags=["auditoria"], dependencies=[Depends(require_api_key)])


@router.get("/seo")
async def get_seo(url: str = Query(..., description="URL del sitio a auditar")):
    return await audit_seo(url)


@router.get("/health")
async def get_health(url: str = Query(..., description="URL del sitio a verificar")):
    return await check_site(url)
