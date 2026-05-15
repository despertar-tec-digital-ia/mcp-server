import sqlite3
from contextlib import contextmanager
from pathlib import Path
from unittest.mock import patch
import pytest
import app.clients.sonoras.offers as offers_module

SEED_SQL = (Path(__file__).parent.parent / "app" / "clients" / "sonoras" / "seed.sql").read_text()


def make_mem_db():
    """Creates a fresh in-memory SQLite connection with the schema applied."""
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript(SEED_SQL)
    return conn


def mem_conn_factory(conn):
    """Returns a get_conn context manager that reuses a single in-memory connection."""
    @contextmanager
    def _get_conn():
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
    return _get_conn


@pytest.fixture
def db():
    conn = make_mem_db()
    yield conn
    conn.close()


def test_create_offer(db):
    with patch.object(offers_module, "get_conn", mem_conn_factory(db)):
        result = offers_module._create(title="2x1 en alitas", fb_post_id="post_001")
    assert result["duplicate"] is False
    assert isinstance(result["id"], int)


def test_create_offer_sin_fb_post_id(db):
    with patch.object(offers_module, "get_conn", mem_conn_factory(db)):
        result = offers_module._create(title="Promo sin ID")
    assert result["duplicate"] is False
    assert "id" in result


def test_duplicado_por_fb_post_id(db):
    with patch.object(offers_module, "get_conn", mem_conn_factory(db)):
        first = offers_module._create(title="Oferta original", fb_post_id="post_dup")
        second = offers_module._create(title="Oferta duplicada", fb_post_id="post_dup")
    assert first["duplicate"] is False
    assert second["duplicate"] is True
    assert second["id"] == first["id"]


def test_list_activas(db):
    with patch.object(offers_module, "get_conn", mem_conn_factory(db)):
        offers_module._create(title="Oferta A", fb_post_id="post_a")
        offers_module._create(title="Oferta B", fb_post_id="post_b")
        offers = offers_module._list()
    assert len(offers) == 2
    titles = {o["title"] for o in offers}
    assert "Oferta A" in titles
    assert "Oferta B" in titles


def test_list_vacia(db):
    with patch.object(offers_module, "get_conn", mem_conn_factory(db)):
        offers = offers_module._list()
    assert offers == []


def test_deactivate(db):
    with patch.object(offers_module, "get_conn", mem_conn_factory(db)):
        created = offers_module._create(title="Oferta temporal", fb_post_id="post_temp")
        offer_id = created["id"]
        result = offers_module._deactivate(offer_id)
        offers = offers_module._list()
    assert result is True
    assert all(o["id"] != offer_id for o in offers)


def test_deactivate_inexistente(db):
    with patch.object(offers_module, "get_conn", mem_conn_factory(db)):
        result = offers_module._deactivate(99999)
    assert result is False


def test_list_excluye_desactivadas(db):
    with patch.object(offers_module, "get_conn", mem_conn_factory(db)):
        created = offers_module._create(title="Para desactivar", fb_post_id="post_x")
        offers_module._deactivate(created["id"])
        offers_module._create(title="Activa", fb_post_id="post_y")
        offers = offers_module._list()
    assert len(offers) == 1
    assert offers[0]["title"] == "Activa"
