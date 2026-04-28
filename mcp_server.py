import logging
from mcp.server.fastmcp import FastMCP
from mcp.server.fastmcp.server import TransportSecuritySettings

from tools.slots import get_available_slots as _get_slots
from tools.booking import book_appointment as _book_appointment
from utils.datetime_parser import parse_natural_datetime
from utils.lock import SlotAlreadyBookedError
import os
os.makedirs("/tmp/ghl_locks", exist_ok=True)
os.chmod("/tmp/ghl_locks", 0o777)
log = logging.getLogger(__name__)

mcp = FastMCP(
    "GHL Calendar",
    stateless_http=True,
    transport_security=TransportSecuritySettings(enable_dns_rebinding_protection=False),
)


@mcp.tool(name="get_available_slots", description=(
    "Consulta disponibilidad real del calendario de GHL y devuelve hasta 3 horarios "
    "disponibles distribuidos en diferentes dias, basado en texto natural en espanol. "
    "Usar cuando el lead exprese intencion de agendar."
))
async def mcp_get_available_slots(natural_text: str, max_slots: int = 3) -> dict:
    log.info(f"MCP get_available_slots | input: '{natural_text}'")

    parsed = parse_natural_datetime(natural_text)

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
        max_slots=max_slots,
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


@mcp.tool(name="book_appointment", description=(
    "Crea una cita en el calendario de GHL para el contacto dado. "
    "Llamar solo despues de que el lead haya confirmado el horario especifico."
))
async def mcp_book_appointment(
    contact_id: str,
    start_iso: str,
    end_iso: str,
    title: str = "Auditoria Gratuita - Restaurante",
) -> dict:
    log.info(f"MCP book_appointment | contact: {contact_id} | slot: {start_iso}")

    try:
        return await _book_appointment(
            contact_id=contact_id,
            start_iso=start_iso,
            end_iso=end_iso,
            title=title,
        )
    except SlotAlreadyBookedError:
        return {
            "success": False,
            "message": "Ese horario acaba de ser reservado. ¿Quieres ver otros disponibles?",
        }
    except Exception as e:
        log.error(f"Error en MCP book_appointment: {e}", exc_info=True)
        return {
            "success": False,
            "message": f"Error al crear la cita: {str(e)}",
        }
