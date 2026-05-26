import re
from pathlib import Path
from typing import Optional
from .db import get_conn

_STATUS_RE = re.compile(r"\*\*Estado:\*\*\s*(.+)", re.IGNORECASE)
_NAME_RE = re.compile(r"\*\*Cliente:\*\*\s*(.+)", re.IGNORECASE)


def _parse_context(md_text: str) -> dict:
    status_match = _STATUS_RE.search(md_text)
    name_match = _NAME_RE.search(md_text)
    return {
        "status": status_match.group(1).strip() if status_match else "unknown",
        "name": name_match.group(1).strip() if name_match else None,
    }


def list_clients(vault_path: Path, db_path: Optional[Path] = None) -> list[dict]:
    clients: dict[str, dict] = {}

    clientes_dir = vault_path / "clientes"
    if clientes_dir.exists():
        for client_dir in sorted(clientes_dir.iterdir()):
            if not client_dir.is_dir():
                continue
            context_file = client_dir / "CONTEXT.md"
            if not context_file.exists():
                continue
            parsed = _parse_context(context_file.read_text(encoding="utf-8"))
            slug = client_dir.name
            clients[slug] = {
                "slug": slug,
                "name": parsed["name"] or slug,
                "status": parsed["status"],
                "source": "vault",
            }

    with get_conn(db_path) as conn:
        rows = conn.execute(
            "SELECT slug, name, giro, status FROM panel_clients ORDER BY created_at DESC"
        ).fetchall()
        for row in rows:
            slug = row["slug"]
            if slug not in clients:
                clients[slug] = {
                    "slug": slug,
                    "name": row["name"],
                    "giro": row["giro"],
                    "status": row["status"],
                    "source": "panel",
                }

    return list(clients.values())


def create_client(name: str, slug: str, giro: Optional[str] = None, db_path: Optional[Path] = None) -> dict:
    with get_conn(db_path) as conn:
        conn.execute(
            "INSERT INTO panel_clients (name, slug, giro, status) VALUES (?, ?, ?, 'setup')",
            (name, slug, giro),
        )
    return {"slug": slug, "name": name, "giro": giro, "status": "setup"}
