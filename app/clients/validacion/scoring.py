"""Scoring engine for the market-validation agent (ADR-0004).

Pure functions, no network — fully unit-testable. Each data source contributes a
sub-score in 0-10 with a fixed weight. The final score (1-10) is a weighted average
over the sources that were actually available, re-normalizing the weights so a missing
source (no API key, or a failed call) does not unfairly drag the result to zero.
"""
from __future__ import annotations

import math

# Source weights from the brief (sum = 1.0).
WEIGHTS = {
    "google_trends": 0.30,
    "reddit": 0.25,
    "youtube": 0.25,
    "hacker_news": 0.20,
}

# Score >= this triggers deliverable generation (brief: "Si Score >= 7").
DECISION_THRESHOLD = 7.0


def volume_to_score(n: int, low: int, high: int) -> float:
    """Map a raw count to 0-10 on a log scale between `low` and `high`.

    n <= low -> 0; n >= high -> 10; logarithmic in between (demand signals are
    heavily skewed, so log compresses the long tail).
    """
    if n <= low:
        return 0.0
    if n >= high:
        return 10.0
    return round(10 * math.log(n - low + 1) / math.log(high - low + 1), 2)


def aggregate(results: list[dict]) -> dict:
    """Combine per-source results into a final validation score and decision.

    Each result is a dict with: source, available (bool), sub_score (0-10 or None).
    Weights are taken from WEIGHTS and re-normalized over available sources.
    """
    available = [r for r in results if r.get("available") and r.get("sub_score") is not None]
    total_weight = sum(WEIGHTS.get(r["source"], 0) for r in available)

    if not available or total_weight == 0:
        return {
            "score": 0.0,
            "approved": False,
            "decision": "rechazado",
            "reason": "Ninguna fuente de datos disponible para evaluar el nicho.",
            "sources_used": 0,
            "sources": results,
        }

    weighted = sum(
        r["sub_score"] * WEIGHTS.get(r["source"], 0) for r in available
    )
    score = round(weighted / total_weight, 1)
    approved = score >= DECISION_THRESHOLD

    return {
        "score": score,
        "approved": approved,
        "decision": "aprobado" if approved else "rechazado",
        "reason": (
            "Señal de demanda suficiente para construir entregables."
            if approved
            else "Señal de demanda insuficiente; considerar pivote o nicho más específico."
        ),
        "sources_used": len(available),
        "sources_missing": [r["source"] for r in results if r not in available],
        "sources": results,
    }
