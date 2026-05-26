import re
from pathlib import Path
from typing import Optional

import httpx
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.auth import require_api_key
from app.config import VAULT_PATH, HERMES_URL
from app.clients.panel.clients import list_clients, create_client

router = APIRouter(prefix="/panel", tags=["panel"], dependencies=[Depends(require_api_key)])

_SLUG_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")


class OnboardingRequest(BaseModel):
    name: str
    slug: str
    giro: Optional[str] = None


@router.get("/clients")
def get_clients():
    return list_clients(vault_path=Path(VAULT_PATH))


@router.get("/health")
async def get_health():
    results = {"mcp": "ok"}
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            r = await client.get(f"{HERMES_URL}/health")
            results["hermes"] = "ok" if r.status_code == 200 else "error"
    except Exception:
        results["hermes"] = "unreachable"
    return results


@router.post("/onboarding", status_code=201)
def start_onboarding(body: OnboardingRequest):
    if not body.name.strip():
        raise HTTPException(status_code=422, detail="name is required")
    slug = body.slug.strip().lower()
    if not _SLUG_RE.match(slug):
        raise HTTPException(status_code=422, detail="slug must be lowercase letters, numbers and hyphens")
    try:
        return create_client(name=body.name.strip(), slug=slug, giro=body.giro)
    except Exception:
        raise HTTPException(status_code=409, detail="Client slug already exists")
