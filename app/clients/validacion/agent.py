"""Market-validation orchestrator (Fase 1 of ADR-0004).

Runs every demand source in parallel, aggregates into a 1-10 score and a decision.
Deliverable generation (offer/PDF/proposal) is Fase 2 and not implemented here.
"""
from __future__ import annotations

import asyncio
import logging

import httpx

from app.clients.validacion.scoring import aggregate, DECISION_THRESHOLD
from app.clients.validacion.sources import ALL_SOURCES

log = logging.getLogger(__name__)


async def validate_niche(niche: str, geo: str | None = None, timeout: float = 20.0) -> dict:
    """Validate a niche/idea by scoring real demand signals across sources."""
    niche = (niche or "").strip()
    if not niche:
        return {"error": "Falta el nicho o idea a evaluar."}

    # geo is NOT appended to the query: HN/YouTube/Reddit are global demand signals and a
    # city term collapses them to zero. geo is reserved for Google Trends regional scoping (Fase 2).
    async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
        results = await asyncio.gather(
            *(src(niche, client) for src in ALL_SOURCES),
            return_exceptions=True,
        )

    clean: list[dict] = []
    for src, res in zip(ALL_SOURCES, results):
        if isinstance(res, Exception):
            log.warning(f"source {src.__name__} raised: {res}")
            clean.append({
                "source": src.__name__, "available": False,
                "sub_score": None, "note": f"Excepción: {res}",
            })
        else:
            clean.append(res)

    report = aggregate(clean)
    report["niche"] = niche
    report["geo"] = geo
    report["threshold"] = DECISION_THRESHOLD
    report["next_step"] = (
        "Generar entregables (oferta, propuesta, PDF) — Fase 2."
        if report["approved"]
        else "Entregar reporte de rechazo con recomendaciones de pivote."
    )
    return report
