import contextlib
import logging
import os
import sys
from fastapi import FastAPI
from starlette.applications import Starlette

from projects.sonoras.db import init_db

# ─── Logging ────────────────────────────────────────────────────────────────
LOG_FILE = os.getenv("LOG_FILE", "app.log")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(LOG_FILE),
    ]
)
log = logging.getLogger(__name__)

# ─── MCP Setup (before app, so session_manager exists at lifespan time) ─────
# Routes exposed:
#   POST /mcp   — Streamable HTTP (primary, configure this URL in GHL)
#   GET  /sse   — SSE stream (fallback)
#   POST /messages/ — SSE message endpoint
from mcp_server import mcp as _mcp

_http_app = _mcp.streamable_http_app()  # also creates _mcp.session_manager
_sse_app = _mcp.sse_app()


@contextlib.asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    async with _mcp.session_manager.run():
        log.info("MCP session manager started")
        yield
    log.info("MCP session manager stopped")


# ─── App ─────────────────────────────────────────────────────────────────────
app = FastAPI(
    title="GHL MCP - Calendario",
    description="Tools MCP para agendar citas desde AI Agent Studio",
    version="1.0.0",
    lifespan=lifespan,
)

# ─── Endpoints ───────────────────────────────────────────────────────────────

@app.get("/health")
async def health():
    return {"status": "ok", "service": "GHL MCP Calendar"}


# ─── MCP Mount ───────────────────────────────────────────────────────────────
# FastAPI routes above take precedence; this sub-app catches /mcp, /sse, /messages/
app.mount("/", Starlette(routes=list(_http_app.routes) + list(_sse_app.routes)))
