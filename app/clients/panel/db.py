import sqlite3
from contextlib import contextmanager
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent.parent.parent.parent / "data" / "panel.db"
SEED_PATH = Path(__file__).resolve().parent / "seed.sql"


def init_db(db_path: Path | None = None) -> None:
    path = db_path if db_path is not None else DB_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(path) as conn:
        with open(SEED_PATH, "r", encoding="utf-8") as f:
            conn.executescript(f.read())


@contextmanager
def get_conn(db_path: Path | None = None):
    path = db_path if db_path is not None else DB_PATH
    conn = sqlite3.connect(path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()
