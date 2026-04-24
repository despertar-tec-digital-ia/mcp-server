import logging
import sys
from fastapi import FastAPI, HTTPException, Header, Depends
from pydantic import BaseModel
from typing import Optional
import httpx

from config import API_SECRET_KEY
from tools.slots import get_available_slots
from tools.booking import book_appointment
from utils.datetime_parser import parse_natural_datetime
from utils.lock import SlotAlreadyBookedError

# ─── Logging ────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("app.log"),
    ]
)
log = logging.getLogger(__name__)

# ─── App ─────────────────────────────────────────────────────────────────────
app = FastAPI(
    title="GHL MCP - Calendario",
    description="Tools MCP para agendar citas desde AI Agent Studio",
    version="1.0.0",
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

        slots = await get_available_slots(
            start_dt=parsed["start"],
            end_dt=parsed["end"],
            max_slots=body.max_slots
        )

        log.info(f"Slots encontrados: {len(slots)}")

        if not slots:
            return SlotsResponse(
                slots=[],
                parsed_description=parsed["parsed_description"],
                count=0
            )

        return SlotsResponse(
            slots=slots,
            parsed_description=parsed["parsed_description"],
            count=len(slots)
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
