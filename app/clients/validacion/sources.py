"""Demand-signal sources for the market-validation agent.

Each source is an async function `(niche, client) -> result dict` shaped as:
    {source, weight, available, sub_score (0-10 | None), signals, note}

Design rule (ADR-0004): a source that lacks credentials or fails returns
`available: False` instead of raising, so the scoring engine can re-normalize over
whatever ran. Only Hacker News (Algolia, keyless) is guaranteed to work out of the box.
"""
from __future__ import annotations

import base64
import logging
import os

import httpx

from app.clients.validacion.scoring import WEIGHTS, volume_to_score

log = logging.getLogger(__name__)

_UA = "DDTIA-MarketValidation/1.0"


def _result(source: str, available: bool, sub_score: float | None = None,
            signals: dict | None = None, note: str = "") -> dict:
    return {
        "source": source,
        "weight": WEIGHTS.get(source, 0),
        "available": available,
        "sub_score": sub_score,
        "signals": signals or {},
        "note": note,
    }


async def hacker_news(niche: str, client: httpx.AsyncClient) -> dict:
    """Algolia HN Search API — keyless. Volume of stories + engagement."""
    try:
        r = await client.get(
            "https://hn.algolia.com/api/v1/search",
            params={"query": niche, "tags": "story", "hitsPerPage": 50},
            headers={"User-Agent": _UA},
        )
        r.raise_for_status()
        data = r.json()
    except Exception as e:
        log.warning(f"hacker_news source failed: {e}")
        return _result("hacker_news", False, note=f"Error consultando HN: {e}")

    hits = data.get("hits", [])
    n_hits = data.get("nbHits", len(hits))
    engagement = [
        (h.get("points") or 0) + (h.get("num_comments") or 0) for h in hits
    ]
    avg_eng = (sum(engagement) / len(engagement)) if engagement else 0

    volume_score = volume_to_score(n_hits, low=2, high=500)
    eng_score = volume_to_score(int(avg_eng), low=5, high=300)
    sub = round(0.6 * volume_score + 0.4 * eng_score, 2)

    return _result(
        "hacker_news", True, sub_score=sub,
        signals={"stories": n_hits, "avg_engagement": round(avg_eng, 1)},
        note=f"{n_hits} historias en HN, engagement promedio {round(avg_eng, 1)}.",
    )


async def reddit(niche: str, client: httpx.AsyncClient) -> dict:
    """Reddit search via OAuth2 client-credentials. Needs REDDIT_CLIENT_ID/SECRET."""
    cid = os.getenv("REDDIT_CLIENT_ID")
    secret = os.getenv("REDDIT_CLIENT_SECRET")
    if not (cid and secret):
        return _result("reddit", False, note="Sin REDDIT_CLIENT_ID/SECRET configurados.")
    try:
        auth = base64.b64encode(f"{cid}:{secret}".encode()).decode()
        tok = await client.post(
            "https://www.reddit.com/api/v1/access_token",
            data={"grant_type": "client_credentials"},
            headers={"Authorization": f"Basic {auth}", "User-Agent": _UA},
        )
        tok.raise_for_status()
        token = tok.json()["access_token"]

        r = await client.get(
            "https://oauth.reddit.com/search",
            params={"q": niche, "limit": 50, "sort": "relevance", "t": "year"},
            headers={"Authorization": f"Bearer {token}", "User-Agent": _UA},
        )
        r.raise_for_status()
        children = r.json().get("data", {}).get("children", [])
    except Exception as e:
        log.warning(f"reddit source failed: {e}")
        return _result("reddit", False, note=f"Error consultando Reddit: {e}")

    n = len(children)
    eng = [
        (c["data"].get("ups") or 0) + (c["data"].get("num_comments") or 0)
        for c in children
    ]
    avg_eng = (sum(eng) / len(eng)) if eng else 0
    volume_score = volume_to_score(n, low=1, high=50)
    eng_score = volume_to_score(int(avg_eng), low=5, high=500)
    sub = round(0.5 * volume_score + 0.5 * eng_score, 2)

    return _result(
        "reddit", True, sub_score=sub,
        signals={"posts": n, "avg_engagement": round(avg_eng, 1)},
        note=f"{n} posts relevantes en Reddit, engagement promedio {round(avg_eng, 1)}.",
    )


async def youtube(niche: str, client: httpx.AsyncClient) -> dict:
    """YouTube Data API v3 search. Needs YOUTUBE_API_KEY (Google Cloud)."""
    key = os.getenv("YOUTUBE_API_KEY")
    if not key:
        return _result("youtube", False, note="Sin YOUTUBE_API_KEY configurada.")
    try:
        r = await client.get(
            "https://www.googleapis.com/youtube/v3/search",
            params={"part": "snippet", "q": niche, "type": "video",
                    "maxResults": 25, "key": key},
            headers={"User-Agent": _UA},
        )
        r.raise_for_status()
        data = r.json()
    except Exception as e:
        log.warning(f"youtube source failed: {e}")
        return _result("youtube", False, note=f"Error consultando YouTube: {e}")

    total = data.get("pageInfo", {}).get("totalResults", 0)
    sub = volume_to_score(int(total), low=50, high=100000)
    return _result(
        "youtube", True, sub_score=sub,
        signals={"total_results": total},
        note=f"{total} videos relacionados en YouTube.",
    )


async def google_trends(niche: str, client: httpx.AsyncClient) -> dict:
    """Google Trends. Reserved — requires the `pytrends` dependency (not installed).

    Kept as an explicit unavailable source so its weight is re-normalized away until
    we decide to add the dependency (see ADR-0004, riesgos).
    """
    return _result("google_trends", False, note="Pendiente: requiere pytrends (no instalado).")


ALL_SOURCES = (google_trends, reddit, youtube, hacker_news)
