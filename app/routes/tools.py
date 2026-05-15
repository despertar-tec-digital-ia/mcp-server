import logging
from fastapi import APIRouter, Depends
from app.auth import require_api_key
from app.schemas.requests import SlotsRequest, BookRequest
from app.utils.datetime_parser import parse_natural_datetime
from app.clients.sofia.slots import get_available_slots as _get_slots
from app.clients.sofia.booking import book_appointment as _book_appointment
from app.utils.lock import SlotAlreadyBookedError

log = logging.getLogger(__name__)
router = APIRouter()


@router.post("/tools/get_available_slots", dependencies=[Depends(require_api_key)])
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


@router.post("/tools/book_appointment", dependencies=[Depends(require_api_key)])
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
