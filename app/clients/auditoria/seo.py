"""On-page SEO audit for client sites.

`analyze_html` is a pure function (no network) so it can be unit-tested in full.
`audit_seo` wraps it: fetches the page, robots.txt and sitemap.xml, inspects the
TLS certificate, and merges those network checks into the report.

Deliberately dependency-light: stdlib HTML parsing + httpx (already a dependency),
no BeautifulSoup. The score is a weighted 0-100 over a list of named checks.
"""
from __future__ import annotations

import asyncio
from html.parser import HTMLParser
from urllib.parse import urljoin, urlparse

import httpx

from app.clients.auditoria.health import _normalize, cert_days_left

# status -> numeric weight contribution
_STATUS_VALUE = {"ok": 1.0, "warn": 0.5, "fail": 0.0}


class _SeoHTMLParser(HTMLParser):
    """Collects the on-page signals we score, from the first <head>/<body>."""

    def __init__(self) -> None:
        super().__init__()
        self.title_parts: list[str] = []
        self._in_title = False
        self.html_lang: str | None = None
        self.metas: dict[str, str] = {}      # name/property (lower) -> content
        self.canonical: str | None = None
        self.h1_count = 0
        self._in_h1 = False
        self.img_total = 0
        self.img_with_alt = 0
        self.jsonld_count = 0
        self._in_jsonld = False

    def handle_starttag(self, tag, attrs):
        a = {k.lower(): (v or "") for k, v in attrs}
        if tag == "html" and "lang" in a:
            self.html_lang = a["lang"].strip() or None
        elif tag == "title":
            self._in_title = True
        elif tag == "h1":
            self.h1_count += 1
            self._in_h1 = True
        elif tag == "meta":
            key = (a.get("name") or a.get("property") or "").lower().strip()
            if key and "content" in a:
                self.metas[key] = a["content"].strip()
        elif tag == "link":
            rels = a.get("rel", "").lower().split()
            if "canonical" in rels and a.get("href"):
                self.canonical = a["href"].strip()
        elif tag == "img":
            self.img_total += 1
            if a.get("alt", "").strip():
                self.img_with_alt += 1
        elif tag == "script" and a.get("type", "").lower() == "application/ld+json":
            self._in_jsonld = True

    def handle_endtag(self, tag):
        if tag == "title":
            self._in_title = False
        elif tag == "h1":
            self._in_h1 = False
        elif tag == "script" and self._in_jsonld:
            self._in_jsonld = False

    def handle_data(self, data):
        if self._in_title:
            self.title_parts.append(data)
        if self._in_jsonld and data.strip():
            self.jsonld_count += 1

    @property
    def title(self) -> str:
        return "".join(self.title_parts).strip()


def _check(checks: list[dict], cid: str, label: str, status: str, weight: int, detail: str):
    checks.append({"id": cid, "label": label, "status": status, "weight": weight, "detail": detail})


def _score(checks: list[dict]) -> int:
    total = sum(c["weight"] for c in checks)
    if not total:
        return 0
    got = sum(_STATUS_VALUE[c["status"]] * c["weight"] for c in checks)
    return round(got / total * 100)


def analyze_html(html: str, url: str = "") -> dict:
    """Parse on-page SEO signals from raw HTML and produce scored checks.

    Pure function — no network. `url` is only used for context in the result.
    """
    p = _SeoHTMLParser()
    p.feed(html or "")
    checks: list[dict] = []

    # Title
    title = p.title
    if not title:
        _check(checks, "title", "Title tag", "fail", 3, "Falta el <title>.")
    elif 30 <= len(title) <= 60:
        _check(checks, "title", "Title tag", "ok", 3, f"{len(title)} caracteres.")
    else:
        _check(checks, "title", "Title tag", "warn", 3,
               f"{len(title)} caracteres (ideal 30-60).")

    # Meta description
    desc = p.metas.get("description", "")
    if not desc:
        _check(checks, "meta_description", "Meta description", "fail", 3, "Falta la meta description.")
    elif 70 <= len(desc) <= 160:
        _check(checks, "meta_description", "Meta description", "ok", 3, f"{len(desc)} caracteres.")
    else:
        _check(checks, "meta_description", "Meta description", "warn", 3,
               f"{len(desc)} caracteres (ideal 70-160).")

    # H1
    if p.h1_count == 1:
        _check(checks, "h1", "Encabezado H1", "ok", 2, "Un solo H1.")
    elif p.h1_count == 0:
        _check(checks, "h1", "Encabezado H1", "fail", 2, "No hay H1.")
    else:
        _check(checks, "h1", "Encabezado H1", "warn", 2, f"{p.h1_count} H1 (ideal 1).")

    # Indexability (meta robots)
    robots = p.metas.get("robots", "").lower()
    if "noindex" in robots:
        _check(checks, "indexable", "Indexable", "fail", 3, "meta robots=noindex bloquea indexacion.")
    else:
        _check(checks, "indexable", "Indexable", "ok", 3, "Sin noindex en meta robots.")

    # Lang
    if p.html_lang:
        _check(checks, "lang", "Atributo lang", "ok", 1, f'lang="{p.html_lang}".')
    else:
        _check(checks, "lang", "Atributo lang", "warn", 1, "Falta <html lang>.")

    # Canonical
    if p.canonical:
        _check(checks, "canonical", "Canonical", "ok", 1, p.canonical)
    else:
        _check(checks, "canonical", "Canonical", "warn", 1, "Sin <link rel=canonical>.")

    # Viewport (mobile)
    if p.metas.get("viewport"):
        _check(checks, "viewport", "Viewport mobile", "ok", 1, p.metas["viewport"])
    else:
        _check(checks, "viewport", "Viewport mobile", "warn", 1, "Falta meta viewport.")

    # Open Graph (social sharing)
    og = [k for k in ("og:title", "og:description", "og:image") if p.metas.get(k)]
    if len(og) == 3:
        _check(checks, "open_graph", "Open Graph", "ok", 1, "og:title, og:description, og:image.")
    elif og:
        _check(checks, "open_graph", "Open Graph", "warn", 1, f"Solo {', '.join(og)}.")
    else:
        _check(checks, "open_graph", "Open Graph", "warn", 1, "Sin Open Graph.")

    # Structured data
    if p.jsonld_count:
        _check(checks, "structured_data", "Datos estructurados", "ok", 2,
               f"{p.jsonld_count} bloque(s) JSON-LD.")
    else:
        _check(checks, "structured_data", "Datos estructurados", "warn", 2, "Sin JSON-LD.")

    # Image alt coverage
    if p.img_total == 0:
        _check(checks, "img_alt", "Alt en imagenes", "ok", 1, "Sin imagenes.")
    else:
        ratio = p.img_with_alt / p.img_total
        status = "ok" if ratio >= 0.9 else ("warn" if ratio >= 0.5 else "fail")
        _check(checks, "img_alt", "Alt en imagenes", status, 1,
               f"{p.img_with_alt}/{p.img_total} con alt.")

    issues = [c for c in checks if c["status"] != "ok"]
    return {
        "url": url,
        "score": _score(checks),
        "title": title,
        "meta_description": desc,
        "h1_count": p.h1_count,
        "checks": checks,
        "issues": issues,
        "issue_count": len(issues),
    }


async def _exists(client: httpx.AsyncClient, url: str) -> bool:
    try:
        r = await client.get(url, headers={"User-Agent": "DDTIA-SEO/1.0"})
        return r.status_code == 200
    except Exception:
        return False


async def audit_seo(url: str, timeout: float = 15.0) -> dict:
    """Full on-page SEO audit: fetch the page + robots.txt + sitemap + TLS, then score.

    Network wrapper around `analyze_html`. Adds technical-SEO checks (HTTPS, robots.txt,
    sitemap.xml, certificate) on top of the on-page signals and re-computes the score.
    """
    target = _normalize(url)
    if not target:
        return {"url": url, "error": "URL vacia"}

    parsed = urlparse(target)
    host = parsed.hostname or ""
    root = f"{parsed.scheme}://{parsed.netloc}"

    try:
        async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
            page = await client.get(target, headers={"User-Agent": "DDTIA-SEO/1.0"})
            html = page.text
            has_robots = await _exists(client, urljoin(root + "/", "robots.txt"))
            has_sitemap = await _exists(client, urljoin(root + "/", "sitemap.xml"))
    except Exception as e:
        return {"url": target, "error": f"No se pudo cargar la pagina: {e}"}

    report = analyze_html(html, url=target)
    checks = report["checks"]

    # ── Technical-SEO checks (network) ────────────────────────────────────────
    if target.startswith("https://"):
        _check(checks, "https", "HTTPS", "ok", 2, "Sirve sobre HTTPS.")
    else:
        _check(checks, "https", "HTTPS", "fail", 2, "No usa HTTPS.")

    _check(checks, "robots_txt", "robots.txt", "ok" if has_robots else "warn", 1,
           "Presente." if has_robots else "No se encontro /robots.txt.")
    _check(checks, "sitemap", "sitemap.xml", "ok" if has_sitemap else "warn", 1,
           "Presente." if has_sitemap else "No se encontro /sitemap.xml.")

    if host and target.startswith("https://"):
        days = await asyncio.to_thread(cert_days_left, host)
        if days is None:
            _check(checks, "cert", "Certificado TLS", "warn", 1, "No se pudo leer el certificado.")
        elif days < 0:
            _check(checks, "cert", "Certificado TLS", "fail", 1, "Certificado expirado.")
        elif days <= 14:
            _check(checks, "cert", "Certificado TLS", "warn", 1, f"Expira en {days} dias.")
        else:
            _check(checks, "cert", "Certificado TLS", "ok", 1, f"Vigente, {days} dias restantes.")

    report["status_code"] = page.status_code
    report["score"] = _score(checks)
    report["issues"] = [c for c in checks if c["status"] != "ok"]
    report["issue_count"] = len(report["issues"])
    return report
