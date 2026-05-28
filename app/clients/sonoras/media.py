"""
Sonora's — Media storage desde GHL (type=file).
"""

import httpx
import unicodedata
from typing import Optional
from app.config import GHL_BASE_URL
from app.auth import get_headers
import os

_SONORAS_LOCATION_ID = os.getenv("GHL_SONORAS_LOCATION_ID", "")
_SONORAS_MEDIA_API_KEY = os.getenv("GHL_SONORAS_MEDIA_API_KEY", "")


def _headers() -> dict:
    return {
        "Authorization": f"Bearer {_SONORAS_MEDIA_API_KEY}",
        "Content-Type": "application/json",
        "Version": "2021-07-28",
    }


def _normalize(text: str) -> str:
    return unicodedata.normalize("NFD", text.lower()).encode("ascii", "ignore").decode()


async def list_media(query: Optional[str] = None, limit: int = 100) -> list[dict]:
    url = f"{GHL_BASE_URL}/medias/files"
    params = {
        "locationId": _SONORAS_LOCATION_ID,
        "type": "file",
        "limit": limit,
        "sortBy": "name",
        "sortOrder": "asc",
    }

    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.get(url, headers=_headers(), params=params)
        resp.raise_for_status()
        data = resp.json()

    # filtrar solo imágenes (excluir videos)
    files = [
        f for f in data.get("files", [])
        if not f.get("name", "").lower().endswith((".mp4", ".mov", ".avi", ".webm"))
    ]

    results = [
        {"name": f.get("name", ""), "url": f.get("url", "")}
        for f in files
        if f.get("name") and f.get("url")
    ]

    if not query:
        return results

    q_norm = _normalize(query)
    keywords = q_norm.split()
    matched = [
        r for r in results
        if any(kw in _normalize(r["name"]) for kw in keywords)
    ]
    return matched
