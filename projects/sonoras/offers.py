"""
Sonora's — Endpoints de ofertas.

Tres rutas:
  POST   /sonoras/offers/create          [auth]    → llamado desde GHL Workflow
  GET    /sonoras/offers/list            [público] → consumido por funnel page
  PATCH  /sonoras/offers/deactivate/{id} [auth]    → llamado desde GHL Workflow

Auth: header `x-api-key` (misma var de entorno MCP_API_KEY que usa Sofía).
GET /list es público a propósito porque lo consume JS de la página web.
"""

import os
from datetime import datetime
from typing import Optional
from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel

from .db import get_conn

router = APIRouter(prefix="/sonoras/offers", tags=["sonoras"])

API_KEY = os.getenv("MCP_API_KEY")


def verify_api_key(x_api_key: Optional[str] = Header(None)) -> None:
    if not API_KEY or x_api_key != API_KEY:
        raise HTTPException(status_code=401, detail="Invalid API key")


# Schemas 
class OfferCreate(BaseModel):
    title: str
    description: Optional[str] = None
    image_url: Optional[str] = None
    fb_post_id: Optional[str] = None
    expires_at: Optional[datetime] = None


# Endpoints

@router.post("/create", dependencies=[Depends(verify_api_key)])
def create_offer(offer: OfferCreate):
    """Crea una oferta. Si fb_post_id ya existe, no duplica."""
    with get_conn() as conn:
        if offer.fb_post_id:
            existing = conn.execute(
                "SELECT id FROM offers WHERE fb_post_id = ?",
                (offer.fb_post_id,),
            ).fetchone()
            if existing:
                return {"id": existing["id"], "duplicate": True}

        cursor = conn.execute(
            """
            INSERT INTO offers (title, description, image_url, fb_post_id, expires_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                offer.title,
                offer.description,
                offer.image_url,
                offer.fb_post_id,
                offer.expires_at.isoformat() if offer.expires_at else None,
            ),
        )
        return {"id": cursor.lastrowid, "duplicate": False}


@router.get("/list")
def list_offers():
    """
    Endpoint público — consumido por el JS de la funnel page.
    Filtra activas y no expiradas.
    """
    with get_conn() as conn:
        rows = conn.execute(
            """
            SELECT id, title, description, image_url, expires_at
            FROM offers
            WHERE is_active = 1
              AND (expires_at IS NULL OR expires_at > datetime('now'))
            ORDER BY created_at DESC
            """
        ).fetchall()
        return [dict(r) for r in rows]


@router.patch("/deactivate/{offer_id}", dependencies=[Depends(verify_api_key)])
def deactivate_offer(offer_id: int):
    """Marca la oferta como inactiva. La llama el Workflow tras el Wait."""
    with get_conn() as conn:
        result = conn.execute(
            """
            UPDATE offers
               SET is_active = 0,
                   updated_at = CURRENT_TIMESTAMP
             WHERE id = ?
            """,
            (offer_id,),
        )
        if result.rowcount == 0:
            raise HTTPException(status_code=404, detail="Offer not found")
        return {"id": offer_id, "deactivated": True}
