"""Lightweight site health + TLS certificate checks for client sites."""
from __future__ import annotations

import asyncio
import socket
import ssl
import time
from datetime import datetime, timezone
from urllib.parse import urlparse

import httpx


def _normalize(url: str) -> str:
    url = (url or "").strip()
    if not url:
        return ""
    if not url.startswith(("http://", "https://")):
        url = "https://" + url
    return url


def cert_days_left(host: str, port: int = 443, timeout: float = 5.0) -> int | None:
    """Days until the TLS cert expires, or None if it can't be read. Blocking."""
    try:
        ctx = ssl.create_default_context()
        with socket.create_connection((host, port), timeout=timeout) as sock:
            with ctx.wrap_socket(sock, server_hostname=host) as ssock:
                cert = ssock.getpeercert()
        not_after = cert.get("notAfter")
        if not not_after:
            return None
        expires = datetime.strptime(not_after, "%b %d %H:%M:%S %Y %Z").replace(tzinfo=timezone.utc)
        return (expires - datetime.now(timezone.utc)).days
    except Exception:
        return None


async def check_site(url: str, timeout: float = 10.0) -> dict:
    """Return up/down, status, latency, redirects and TLS cert state for a URL."""
    target = _normalize(url)
    if not target:
        return {"url": url, "up": False, "error": "URL vacia"}

    host = urlparse(target).hostname or ""
    result: dict = {"url": target, "host": host}

    start = time.perf_counter()
    try:
        async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
            r = await client.get(target, headers={"User-Agent": "DDTIA-HealthCheck/1.0"})
        result.update(
            up=r.status_code < 400,
            status_code=r.status_code,
            response_ms=round((time.perf_counter() - start) * 1000),
            final_url=str(r.url),
            redirected=str(r.url) != target,
        )
    except Exception as e:
        result.update(up=False, error=str(e),
                      response_ms=round((time.perf_counter() - start) * 1000))

    if target.startswith("https://") and host:
        days = await asyncio.to_thread(cert_days_left, host)
        result["cert_days_left"] = days
        if days is None:
            result["cert_status"] = "unknown"
        elif days < 0:
            result["cert_status"] = "expired"
        elif days <= 14:
            result["cert_status"] = "expiring_soon"
        else:
            result["cert_status"] = "ok"

    return result
