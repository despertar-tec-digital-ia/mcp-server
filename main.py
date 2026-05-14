import contextlib
import logging
import os
import sys
from fastapi import Depends, FastAPI, Header, HTTPException, Query, Request
from fastapi.responses import Response
from pydantic import BaseModel
import httpx
from starlette.applications import Starlette

from projects.sonoras.db import init_db
from projects.sonoras.offers import router as sonoras_router
from projects.sofia.slots import get_available_slots as _get_slots
from projects.sofia.booking import book_appointment as _book_appointment
from utils.datetime_parser import parse_natural_datetime
from utils.lock import SlotAlreadyBookedError

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

# ─── Auth ────────────────────────────────────────────────────────────────────

def _require_api_key(x_api_key: str = Header(...)):
    if x_api_key != os.getenv("MCP_API_KEY", ""):
        raise HTTPException(status_code=401, detail="Invalid API key")


# ─── Schemas ─────────────────────────────────────────────────────────────────

class SlotsRequest(BaseModel):
    natural_text: str
    max_slots: int = 3


class BookRequest(BaseModel):
    contact_id: str
    start_iso: str
    end_iso: str
    title: str = "Auditoria Gratuita - Restaurante"


# ─── Endpoints ───────────────────────────────────────────────────────────────

@app.get("/health")
async def health():
    return {"status": "ok", "service": "GHL MCP Calendar"}


@app.get("/webhooks/facebook/verify")
async def facebook_webhook_verify(
    hub_mode: str = Query(alias="hub.mode"),
    hub_verify_token: str = Query(alias="hub.verify_token"),
    hub_challenge: str = Query(alias="hub.challenge"),
):
    if hub_verify_token != "sonoras2026":
        raise HTTPException(status_code=403, detail="Forbidden")
    return Response(content=hub_challenge, media_type="text/plain")


@app.get("/webhooks/facebook")
async def facebook_webhook_verify_alt(
    hub_mode: str = Query(alias="hub.mode"),
    hub_verify_token: str = Query(alias="hub.verify_token"),
    hub_challenge: str = Query(alias="hub.challenge"),
):
    if hub_verify_token != "sonoras2026":
        raise HTTPException(status_code=403, detail="Forbidden")
    return Response(content=hub_challenge, media_type="text/plain")


@app.post("/webhooks/facebook")
async def facebook_webhook(request: Request):
    payload = await request.json()
    log.info(f"Facebook webhook received: {payload}")

    # Meta sends changes as a list of entries, each with changes
    # Flatten all change values into a list to inspect
    changes = []
    for entry in payload.get("entry", []):
        for change in entry.get("changes", []):
            changes.append(change.get("value", {}))

    # Extract contact fields from the first change that has them
    first_name = "Facebook"
    email = None
    phone = None
    post_text = ""

    for value in changes:
        # Lead-gen forms
        if "field_data" in value:
            for field in value["field_data"]:
                name = field.get("name", "").lower()
                val = (field.get("values") or [""])[0]
                if name in ("email", "correo"):
                    email = val
                elif name in ("phone_number", "phone", "telefono", "celular"):
                    phone = val
                elif name in ("first_name", "nombre"):
                    first_name = val
        # Page feed posts
        if "message" in value:
            post_text = value["message"]
        if "from" in value:
            first_name = value["from"].get("name", first_name)

    # Fallbacks so GHL always gets a valid contact identifier
    if not email:
        email = f"fb-{payload.get('entry', [{}])[0].get('id', 'unknown')}@facebook.noreply"
    if not phone:
        phone = ""

    ghl_url = os.getenv("GHL_INBOUND_WEBHOOK_URL", "")
    if not ghl_url:
        log.error("GHL_INBOUND_WEBHOOK_URL not set")
        raise HTTPException(status_code=500, detail="GHL webhook URL not configured")

    ghl_payload = {
        "email": email,
        "phone": phone,
        "firstName": first_name,
        "facebook_post_text": post_text,
    }

    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.post(ghl_url, json=ghl_payload)
        log.info(f"GHL response: {resp.status_code} {resp.text}")
        resp.raise_for_status()

    return {"success": True}


@app.post("/tools/get_available_slots", dependencies=[Depends(_require_api_key)])
async def rest_get_available_slots(body: SlotsRequest):
    parsed = parse_natural_datetime(body.natural_text)

    if parsed.get("no_slots_message"):
        return {
            "slots": [],
            "parsed_description": parsed["parsed_description"],
            "count": 0,
            "confirmation_prompt": parsed["no_slots_message"],
        }

    slots = await _get_slots(
        start_dt=parsed["start"],
        end_dt=parsed["end"],
        hour_start=parsed["hour_start"],
        hour_end=parsed["hour_end"],
        max_slots=body.max_slots,
    )

    if not slots:
        return {
            "slots": [],
            "parsed_description": parsed["parsed_description"],
            "count": 0,
            "confirmation_prompt": (
                "No encontre disponibilidad para esa fecha. "
                "¿Tienes otra preferencia de dia u horario?"
            ),
        }

    return {
        "slots": slots,
        "parsed_description": parsed["parsed_description"],
        "count": len(slots),
        "confirmation_prompt": (
            "¿Te funciona alguno de estos horarios? "
            "Dime cual y te confirmo la cita."
        ),
    }


@app.post("/tools/book_appointment", dependencies=[Depends(_require_api_key)])
async def rest_book_appointment(body: BookRequest):
    try:
        return await _book_appointment(
            contact_id=body.contact_id,
            start_iso=body.start_iso,
            end_iso=body.end_iso,
            title=body.title,
        )
    except SlotAlreadyBookedError:
        return {
            "success": False,
            "message": "Ese horario acaba de ser reservado. ¿Quieres ver otros disponibles?",
        }
    except Exception as e:
        log.error(f"Error en REST book_appointment: {e}", exc_info=True)
        return {"success": False, "message": f"Error al crear la cita: {str(e)}"}


# Routers
app.include_router(sonoras_router)

# ─── MCP Mount ───────────────────────────────────────────────────────────────
# FastAPI routes above take precedence; this sub-app catches /mcp, /sse, /messages/
app.mount("/", Starlette(routes=list(_http_app.routes) + list(_sse_app.routes)))
