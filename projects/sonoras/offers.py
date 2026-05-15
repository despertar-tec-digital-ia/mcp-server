"""
Sonora's — Lógica de ofertas.

Funciones internas usadas por los MCP tools en mcp_server.py.
Endpoints REST usados por GHL Workflow (autenticados con x-api-key):
  POST  /sonoras/offers/create
  PATCH /sonoras/offers/deactivate/{id}
Endpoint público para el JS de la funnel page:
  GET   /sonoras/offers/list
"""

import os
from typing import Optional
from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel
from .db import get_conn

router = APIRouter(prefix="/sonoras/offers", tags=["sonoras"])


# ─── Auth ─────────────────────────────────────────────────────────────────────

def _require_api_key(x_api_key: str = Header(...)):
    if x_api_key != os.getenv("MCP_API_KEY", ""):
        raise HTTPException(status_code=401, detail="Invalid API key")


# ─── Schemas ──────────────────────────────────────────────────────────────────

class OfferCreate(BaseModel):
    title: str
    fb_post_id: Optional[str] = None
    description: Optional[str] = None
    image_url: Optional[str] = None
    expires_at: Optional[str] = None
    schedule_notes: Optional[str] = None


# ─── Internal logic (also used by MCP tools) ──────────────────────────────────

def _create(
    title: str,
    fb_post_id: Optional[str] = None,
    description: Optional[str] = None,
    image_url: Optional[str] = None,
    expires_at: Optional[str] = None,
    schedule_notes: Optional[str] = None,
) -> dict:
    expires_at = expires_at or None
    with get_conn() as conn:
        if fb_post_id:
            existing = conn.execute(
                "SELECT id FROM offers WHERE fb_post_id = ?", (fb_post_id,)
            ).fetchone()
            if existing:
                return {"id": existing["id"], "duplicate": True}

        cursor = conn.execute(
            """
            INSERT INTO offers (title, description, image_url, fb_post_id, expires_at, schedule_notes)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (title, description, image_url, fb_post_id, expires_at, schedule_notes),
        )
        return {"id": cursor.lastrowid, "duplicate": False}


def _list() -> list:
    with get_conn() as conn:
        rows = conn.execute(
            """
            SELECT id, title, description, image_url, expires_at, schedule_notes
            FROM offers
            WHERE is_active = 1
              AND (expires_at IS NULL OR expires_at > datetime('now'))
            ORDER BY created_at DESC
            """
        ).fetchall()
        return [dict(r) for r in rows]


def _deactivate(offer_id: int) -> bool:
    with get_conn() as conn:
        result = conn.execute(
            "UPDATE offers SET is_active = 0, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
            (offer_id,),
        )
        return result.rowcount > 0


# ─── Endpoints ────────────────────────────────────────────────────────────────

@router.post("/create", dependencies=[Depends(_require_api_key)])
def create_offer(body: OfferCreate):
    return _create(
        title=body.title,
        fb_post_id=body.fb_post_id,
        description=body.description,
        image_url=body.image_url,
        expires_at=body.expires_at,
        schedule_notes=body.schedule_notes,
    )


@router.get("/list")
def list_offers():
    """Endpoint público — consumido por el JS de la funnel page."""
    return _list()


@router.patch("/deactivate/{offer_id}", dependencies=[Depends(_require_api_key)])
def deactivate_offer(offer_id: int):
    if not _deactivate(offer_id):
        raise HTTPException(status_code=404, detail=f"Offer {offer_id} not found")
    return {"id": offer_id, "deactivated": True}
