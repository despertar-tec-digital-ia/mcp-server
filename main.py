import contextlib
import logging
import os
import sys
from fastapi import FastAPI, HTTPException, Header, Depends
from pydantic import BaseModel
from typing import Optional
from starlette.applications import Starlette
import httpx

from config import API_SECRET_KEY
from projects.sofia.slots import get_available_slots
from projects.sofia.booking import book_appointment
from projects.sonoras.offers import router as sonoras_router
from projects.sonoras.db import init_db
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
def verify_api_key(x_api_key: str = Header(...)):
    if x_api_key != API_SECRET_KEY:
        log.warning("Intento de acceso con API key inválida")
        raise HTTPException(status_code=401, detail="API key inválida")
    return True

# ─── Schemas ─────────────────────────────────────────────────────────────────

class SlotsRequest(BaseModel):
    natural_text: str          # "mañana en la tarde"
    max_slots: Optional[int] = 3

class SlotsResponse(BaseModel):
    slots: list[dict]
    parsed_description: str
    count: int
    confirmation_prompt: Optional[str] = None

class BookRequest(BaseModel):
    contact_id: str            # ID del contacto en GHL
    start_iso: str             #10:00:00-06:00"
    end_iso: str               #10:30:00-06:00"
    title: Optional[str] = "Auditoría Gratuita - Restaurante"

class BookResponse(BaseModel):
    success: bool
    appointment_id: Optional[str] = None
    label: Optional[str] = None
    message: str

# ─── Endpoints ───────────────────────────────────────────────────────────────

@app.get("/health")
async def health():
    return {"status": "ok", "service": "GHL MCP Calendar"}


@app.post("/tools/get_available_slots", response_model=SlotsResponse)
async def tool_get_slots(
    body: SlotsRequest,
    _: bool = Depends(verify_api_key)
):
    """
    TOOL: get_available_slots

    Recibe texto natural como "mañana en la tarde" y devuelve
    2-3 horarios disponibles reales del calendario de GHL.

    El AI Agent llama este endpoint cuando el usuario expresa
    interés en agendar.
    """
    log.info(f"get_available_slots | input: '{body.natural_text}'")

    try:
        parsed = parse_natural_datetime(body.natural_text)
        log.info(f"Fecha parseada: {parsed['parsed_description']}")

        # Weekend or other no-availability cases: skip GHL call entirely
        if parsed.get("no_slots_message"):
            return SlotsResponse(
                slots=[],
                parsed_description=parsed["parsed_description"],
                count=0,
                confirmation_prompt=parsed["no_slots_message"],
            )

        slots = await get_available_slots(
            start_dt=parsed["start"],
            end_dt=parsed["end"],
            hour_start=parsed["hour_start"],
            hour_end=parsed["hour_end"],
            max_slots=body.max_slots,
        )

        log.info(f"Slots encontrados: {len(slots)}")

        if not slots:
            return SlotsResponse(
                slots=[],
                parsed_description=parsed["parsed_description"],
                count=0,
                confirmation_prompt=(
                    "No encontre disponibilidad para esa fecha. "
                    "¿Tienes otra preferencia de dia u horario?"
                ),
            )

        return SlotsResponse(
            slots=slots,
            parsed_description=parsed["parsed_description"],
            count=len(slots),
            confirmation_prompt=(
                "¿Te funciona alguno de estos horarios? "
                "Dime cual y te confirmo la cita."
            ),
        )

    except Exception as e:
        log.error(f"Error en get_available_slots: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/tools/book_appointment", response_model=BookResponse)
async def tool_book_appointment(
    body: BookRequest,
    _: bool = Depends(verify_api_key)
):
    """
    TOOL: book_appointment

    Crea la cita en GHL una vez que el usuario eligió un horario.
    Usa lock para evitar doble reserva.

    El AI Agent llama este endpoint cuando el usuario confirma
    un horario específico.
    """
    log.info(f"book_appointment | contact: {body.contact_id} | slot: {body.start_iso}")

    try:
        result = await book_appointment(
            contact_id=body.contact_id,
            start_iso=body.start_iso,
            end_iso=body.end_iso,
            title=body.title,
        )

        if result["success"]:
            log.info(f"Cita creada: {result['appointment_id']} para {body.contact_id}")
            return BookResponse(
                success=True,
                appointment_id=result["appointment_id"],
                label=result["label"],
                message=result["message"]
            )
        else:
            log.warning(f"Fallo al crear cita: {result.get('error')}")
            return BookResponse(
                success=False,
                message=result.get("error", "No se pudo crear la cita. Intenta con otro horario.")
            )

    except SlotAlreadyBookedError as e:
        log.warning(f"Race condition detectada: {e}")
        return BookResponse(
            success=False,
            message="Ese horario acaba de ser reservado por otra persona. ¿Quieres ver otros disponibles?"
        )
    except Exception as e:
        log.error(f"Error en book_appointment: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


# ─── Routers ─────────────────────────────────────────────────────────────────
app.include_router(sonoras_router)

# ─── MCP Mount ───────────────────────────────────────────────────────────────
# FastAPI routes above take precedence; this sub-app catches /mcp, /sse, /messages/
app.mount("/", Starlette(routes=list(_http_app.routes) + list(_sse_app.routes)))
