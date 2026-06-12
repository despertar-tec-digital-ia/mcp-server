from unittest.mock import patch

import httpx
import pytest

from app.clients.validacion.scoring import aggregate, volume_to_score, DECISION_THRESHOLD
from app.clients.validacion.sources import hacker_news, reddit, youtube, google_trends
from app.clients.validacion.agent import validate_niche


# ─── volume_to_score ───────────────────────────────────────────────────────────

def test_volume_to_score_bounds():
    assert volume_to_score(0, 2, 500) == 0.0
    assert volume_to_score(2, 2, 500) == 0.0
    assert volume_to_score(500, 2, 500) == 10.0
    assert volume_to_score(10000, 2, 500) == 10.0


def test_volume_to_score_monotonic():
    a = volume_to_score(10, 2, 500)
    b = volume_to_score(100, 2, 500)
    assert 0 < a < b < 10


# ─── aggregate ─────────────────────────────────────────────────────────────────

def test_aggregate_renormalizes_over_available():
    # Only HN available with a perfect 10 -> score should be 10, not dragged down.
    results = [
        {"source": "google_trends", "available": False, "sub_score": None},
        {"source": "reddit", "available": False, "sub_score": None},
        {"source": "youtube", "available": False, "sub_score": None},
        {"source": "hacker_news", "available": True, "sub_score": 10.0},
    ]
    out = aggregate(results)
    assert out["score"] == 10.0
    assert out["approved"] is True
    assert out["sources_used"] == 1


def test_aggregate_weighted_average():
    results = [
        {"source": "youtube", "available": True, "sub_score": 8.0},   # w 0.25
        {"source": "hacker_news", "available": True, "sub_score": 4.0},  # w 0.20
    ]
    out = aggregate(results)
    # (8*0.25 + 4*0.20) / (0.45) = 3.8/0.45 = 6.22 -> 6.2
    assert out["score"] == 6.2
    assert out["approved"] is False


def test_aggregate_no_sources():
    out = aggregate([{"source": "reddit", "available": False, "sub_score": None}])
    assert out["score"] == 0.0
    assert out["decision"] == "rechazado"
    assert out["sources_used"] == 0


def test_threshold_boundary():
    results = [{"source": "hacker_news", "available": True, "sub_score": DECISION_THRESHOLD}]
    assert aggregate(results)["approved"] is True


# ─── sources: graceful unavailability without credentials ──────────────────────

@pytest.mark.asyncio
async def test_reddit_unavailable_without_keys():
    with patch.dict("os.environ", {}, clear=True):
        async with httpx.AsyncClient() as c:
            r = await reddit("meal prep", c)
    assert r["available"] is False
    assert r["sub_score"] is None


@pytest.mark.asyncio
async def test_youtube_unavailable_without_key():
    with patch.dict("os.environ", {}, clear=True):
        async with httpx.AsyncClient() as c:
            r = await youtube("meal prep", c)
    assert r["available"] is False


@pytest.mark.asyncio
async def test_google_trends_reserved():
    async with httpx.AsyncClient() as c:
        r = await google_trends("meal prep", c)
    assert r["available"] is False
    assert "pytrends" in r["note"]


# ─── hacker_news with mocked transport ─────────────────────────────────────────

@pytest.mark.asyncio
async def test_hacker_news_scores_from_signals():
    def handler(request):
        return httpx.Response(200, json={
            "nbHits": 500,
            "hits": [{"points": 200, "num_comments": 100} for _ in range(10)],
        })

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as c:
        r = await hacker_news("ai agents", c)
    assert r["available"] is True
    assert r["sub_score"] > 8  # high volume + high engagement
    assert r["signals"]["stories"] == 500


@pytest.mark.asyncio
async def test_hacker_news_handles_error():
    def handler(request):
        return httpx.Response(500)

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as c:
        r = await hacker_news("x", c)
    assert r["available"] is False


# ─── agent.validate_niche end-to-end (mocked transport) ────────────────────────

@pytest.mark.asyncio
async def test_validate_niche_empty():
    out = await validate_niche("")
    assert "error" in out


@pytest.mark.asyncio
async def test_validate_niche_with_only_hn(monkeypatch):
    # No external keys -> only HN contributes. Mock HN to a strong signal.
    def handler(request):
        if "algolia" in str(request.url):
            return httpx.Response(200, json={
                "nbHits": 500,
                "hits": [{"points": 300, "num_comments": 200} for _ in range(10)],
            })
        return httpx.Response(404)

    transport = httpx.MockTransport(handler)
    real_client = httpx.AsyncClient

    def client_factory(*args, **kwargs):
        kwargs.pop("timeout", None)
        kwargs.pop("follow_redirects", None)
        return real_client(transport=transport)

    with patch.dict("os.environ", {}, clear=True), \
         patch("app.clients.validacion.agent.httpx.AsyncClient", client_factory):
        out = await validate_niche("ai agents", geo="Guadalajara")

    assert out["niche"] == "ai agents"
    assert out["sources_used"] == 1
    assert out["score"] > 8
    assert out["approved"] is True
