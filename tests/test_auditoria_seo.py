from app.clients.auditoria.seo import analyze_html
from app.clients.auditoria.health import _normalize


# ─── analyze_html (pure, no network) ───────────────────────────────────────────

GOOD_HTML = """
<html lang="es">
<head>
  <title>Tacos al pastor en Chapalita | El Buen Taco</title>
  <meta name="description" content="Los mejores tacos al pastor de Chapalita, Zapopan. Pedidos a domicilio, abierto todos los dias hasta medianoche.">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <link rel="canonical" href="https://elbuentaco.mx/">
  <meta property="og:title" content="El Buen Taco">
  <meta property="og:description" content="Tacos al pastor">
  <meta property="og:image" content="https://elbuentaco.mx/og.jpg">
  <script type="application/ld+json">{"@type":"Restaurant"}</script>
</head>
<body>
  <h1>El Buen Taco</h1>
  <img src="a.jpg" alt="Tacos al pastor">
</body>
</html>
"""


def test_good_page_scores_high():
    r = analyze_html(GOOD_HTML, url="https://elbuentaco.mx/")
    assert r["score"] >= 90
    assert r["title"].startswith("Tacos al pastor")
    assert r["h1_count"] == 1
    statuses = {c["id"]: c["status"] for c in r["checks"]}
    assert statuses["title"] == "ok"
    assert statuses["meta_description"] == "ok"
    assert statuses["structured_data"] == "ok"
    assert statuses["open_graph"] == "ok"


def test_empty_page_fails_core_checks():
    r = analyze_html("<html><head></head><body></body></html>")
    assert r["score"] < 40
    statuses = {c["id"]: c["status"] for c in r["checks"]}
    assert statuses["title"] == "fail"
    assert statuses["meta_description"] == "fail"
    assert statuses["h1"] == "fail"


def test_noindex_flagged():
    html = '<html><head><title>x</title><meta name="robots" content="noindex, follow"></head><body><h1>x</h1></body></html>'
    r = analyze_html(html)
    statuses = {c["id"]: c["status"] for c in r["checks"]}
    assert statuses["indexable"] == "fail"
    assert any(i["id"] == "indexable" for i in r["issues"])


def test_multiple_h1_warns():
    html = "<html><body><h1>a</h1><h1>b</h1></body></html>"
    r = analyze_html(html)
    h1 = next(c for c in r["checks"] if c["id"] == "h1")
    assert h1["status"] == "warn"
    assert r["h1_count"] == 2


def test_title_length_warn_when_too_long():
    long_title = "x" * 90
    html = f"<html><head><title>{long_title}</title></head><body><h1>h</h1></body></html>"
    r = analyze_html(html)
    title = next(c for c in r["checks"] if c["id"] == "title")
    assert title["status"] == "warn"


def test_image_alt_coverage():
    html = (
        "<html><body><h1>h</h1>"
        '<img src="1.jpg" alt="ok"><img src="2.jpg"><img src="3.jpg"></body></html>'
    )
    r = analyze_html(html)
    img = next(c for c in r["checks"] if c["id"] == "img_alt")
    assert img["status"] == "fail"  # only 1/3 have alt
    assert "1/3" in img["detail"]


def test_issues_exclude_ok_checks():
    r = analyze_html(GOOD_HTML)
    assert all(i["status"] != "ok" for i in r["issues"])
    assert r["issue_count"] == len(r["issues"])


# ─── _normalize ────────────────────────────────────────────────────────────────

def test_normalize_adds_https():
    assert _normalize("example.com") == "https://example.com"


def test_normalize_keeps_scheme():
    assert _normalize("http://example.com") == "http://example.com"


def test_normalize_empty():
    assert _normalize("  ") == ""
