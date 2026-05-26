import sqlite3
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

import app.clients.panel.clients as clients_module
import app.clients.panel.db as db_module
from app.clients.panel.clients import _parse_context, list_clients, create_client
from app.clients.panel.db import init_db

SEED_SQL = (Path(__file__).parent.parent / "app" / "clients" / "panel" / "seed.sql").read_text()


# ─── Helpers ──────────────────────────────────────────────────────────────────

def make_mem_db() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:", check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.executescript(SEED_SQL)
    return conn


def mem_conn_factory(conn: sqlite3.Connection):
    from contextlib import contextmanager

    @contextmanager
    def _get_conn(db_path=None):
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise

    return _get_conn


# ─── _parse_context ───────────────────────────────────────────────────────────

def test_parse_context_full():
    md = "**Cliente:** Sonoras Carbón y Sal\n**Estado:** Activo\n"
    result = _parse_context(md)
    assert result["name"] == "Sonoras Carbón y Sal"
    assert result["status"] == "Activo"


def test_parse_context_missing_fields():
    result = _parse_context("# Sin campos")
    assert result["name"] is None
    assert result["status"] == "unknown"


def test_parse_context_inline_notes():
    md = "**Estado:** Activo (bloqueado parcialmente)"
    result = _parse_context(md)
    assert result["status"] == "Activo (bloqueado parcialmente)"


# ─── list_clients ─────────────────────────────────────────────────────────────

def test_list_clients_from_vault(tmp_path):
    clientes_dir = tmp_path / "clientes" / "sonoras"
    clientes_dir.mkdir(parents=True)
    (clientes_dir / "CONTEXT.md").write_text(
        "**Cliente:** Sonoras\n**Estado:** Activo\n", encoding="utf-8"
    )
    db = make_mem_db()
    with patch.object(clients_module, "get_conn", mem_conn_factory(db)):
        result = list_clients(vault_path=tmp_path)
    assert len(result) == 1
    assert result[0]["slug"] == "sonoras"
    assert result[0]["status"] == "Activo"
    assert result[0]["source"] == "vault"


def test_list_clients_from_db_only(tmp_path):
    db = make_mem_db()
    db.execute("INSERT INTO panel_clients (name, slug, giro) VALUES ('Nuevo', 'nuevo', 'restaurante')")
    db.commit()
    with patch.object(clients_module, "get_conn", mem_conn_factory(db)):
        result = list_clients(vault_path=tmp_path)
    assert any(c["slug"] == "nuevo" and c["source"] == "panel" for c in result)


def test_list_clients_vault_takes_precedence(tmp_path):
    clientes_dir = tmp_path / "clientes" / "sonoras"
    clientes_dir.mkdir(parents=True)
    (clientes_dir / "CONTEXT.md").write_text("**Cliente:** Sonoras\n**Estado:** Activo\n")
    db = make_mem_db()
    db.execute("INSERT INTO panel_clients (name, slug) VALUES ('Sonoras DB', 'sonoras')")
    db.commit()
    with patch.object(clients_module, "get_conn", mem_conn_factory(db)):
        result = list_clients(vault_path=tmp_path)
    sonoras = next(c for c in result if c["slug"] == "sonoras")
    assert sonoras["source"] == "vault"


# ─── create_client ────────────────────────────────────────────────────────────

def test_create_client(tmp_path):
    db = make_mem_db()
    with patch.object(clients_module, "get_conn", mem_conn_factory(db)):
        result = create_client(name="Nuevo Cliente", slug="nuevo-cliente", giro="cafetería")
    assert result["slug"] == "nuevo-cliente"
    assert result["status"] == "setup"


def test_create_client_duplicate_raises(tmp_path):
    db = make_mem_db()
    db.execute("INSERT INTO panel_clients (name, slug) VALUES ('X', 'duplicado')")
    db.commit()
    with patch.object(clients_module, "get_conn", mem_conn_factory(db)):
        with pytest.raises(Exception):
            create_client(name="Y", slug="duplicado")


# ─── /panel/* endpoints via TestClient ────────────────────────────────────────

@pytest.fixture
def client():
    from unittest.mock import patch as _patch
    with _patch.dict("os.environ", {"MCP_API_KEY": "test-key"}):
        from app.main import app
        yield TestClient(app, raise_server_exceptions=True)


def test_get_clients_requires_auth(client):
    r = client.get("/panel/clients")
    assert r.status_code == 422  # missing header


def test_get_clients_wrong_key(client):
    r = client.get("/panel/clients", headers={"x-api-key": "wrong"})
    assert r.status_code == 401


def test_get_clients_ok(client, tmp_path):
    db = make_mem_db()
    with (
        patch.object(clients_module, "get_conn", mem_conn_factory(db)),
        patch("app.routes.panel.VAULT_PATH", str(tmp_path)),
    ):
        r = client.get("/panel/clients", headers={"x-api-key": "test-key"})
    assert r.status_code == 200
    assert isinstance(r.json(), list)


def test_post_onboarding_ok(client):
    db = make_mem_db()
    with patch.object(clients_module, "get_conn", mem_conn_factory(db)):
        r = client.post(
            "/panel/onboarding",
            json={"name": "Mi Cliente", "slug": "mi-cliente", "giro": "hotel"},
            headers={"x-api-key": "test-key"},
        )
    assert r.status_code == 201
    assert r.json()["slug"] == "mi-cliente"


def test_post_onboarding_invalid_slug(client):
    r = client.post(
        "/panel/onboarding",
        json={"name": "Cliente", "slug": "Invalid Slug!"},
        headers={"x-api-key": "test-key"},
    )
    assert r.status_code == 422


def test_get_health_ok(client):
    mock_response = AsyncMock()
    mock_response.status_code = 200
    with patch("app.routes.panel.httpx.AsyncClient") as mock_cls:
        mock_http = AsyncMock()
        mock_http.get.return_value = mock_response
        mock_cls.return_value.__aenter__.return_value = mock_http
        r = client.get("/panel/health", headers={"x-api-key": "test-key"})
    assert r.status_code == 200
    data = r.json()
    assert data["mcp"] == "ok"
    assert data["hermes"] == "ok"


def test_get_health_hermes_unreachable(client):
    with patch("app.routes.panel.httpx.AsyncClient") as mock_cls:
        mock_http = AsyncMock()
        mock_http.get.side_effect = Exception("connection refused")
        mock_cls.return_value.__aenter__.return_value = mock_http
        r = client.get("/panel/health", headers={"x-api-key": "test-key"})
    assert r.status_code == 200
    assert r.json()["hermes"] == "unreachable"


def test_get_health_hermes_no_http(client):
    mock_response = AsyncMock()
    mock_response.status_code = 404
    with patch("app.routes.panel.httpx.AsyncClient") as mock_cls:
        mock_http = AsyncMock()
        mock_http.get.return_value = mock_response
        mock_cls.return_value.__aenter__.return_value = mock_http
        r = client.get("/panel/health", headers={"x-api-key": "test-key"})
    assert r.status_code == 200
    assert r.json()["hermes"] == "no_http"
