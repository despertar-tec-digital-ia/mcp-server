"""
Sonora's — Conexión SQLite.

- DB_PATH apunta a /data/sonoras.db (volumen Docker, para que no se borre entre rebuilds).
- init_db() corre seed.sql al arrancar.
- get_conn() es un context manager con commit automático.
"""

import sqlite3
from contextlib import contextmanager
from pathlib import Path

# /app/projects/sonoras/db.py  ->  /app/data/sonoras.db
DB_PATH = Path(__file__).resolve().parent.parent.parent / "data" / "sonoras.db"
SEED_PATH = Path(__file__).resolve().parent / "seed.sql"


def init_db() -> None:
    """Crea la DB y aplica seed.sql si no existe la tabla."""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(DB_PATH) as conn:
        with open(SEED_PATH, "r", encoding="utf-8") as f:
            conn.executescript(f.read())


@contextmanager
def get_conn():
    """Conexión con row_factory para devolver dicts y commit automático."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()
