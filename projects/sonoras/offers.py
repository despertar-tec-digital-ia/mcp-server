"""
Sonora's — Lógica de ofertas.

Funciones usadas por los MCP tools en mcp_server.py.
El agente es el único que interactúa con las ofertas.
"""

from typing import Optional
from .db import get_conn


def _create(
    title: str,
    fb_post_id: Optional[str] = None,
    description: Optional[str] = None,
    image_url: Optional[str] = None,
    expires_at: Optional[str] = None,
    schedule_notes: Optional[str] = None,
) -> dict:
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
