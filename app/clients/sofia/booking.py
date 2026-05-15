import httpx
from datetime import datetime
import pytz
from app.config import GHL_BASE_URL, GHL_CALENDAR_ID, GHL_LOCATION_ID, GHL_ASSIGNED_USER, TIMEZONE
from app.auth import get_headers
from app.utils.lock import acquire_slot, SlotAlreadyBookedError

DIAS = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"]
MONTHS_ES = [
    "", "enero", "febrero", "marzo", "abril", "mayo", "junio",
    "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre"
]


async def book_appointment(
    contact_id: str,
    start_iso: str,
    end_iso: str,
    title: str = "Auditoría Gratuita - Restaurante",
) -> dict:
    try:
        lock = acquire_slot(start_iso)
    except SlotAlreadyBookedError as e:
        return {"success": False, "error": str(e)}

    try:
        payload = {
            "calendarId":  GHL_CALENDAR_ID,
            "locationId":  GHL_LOCATION_ID,
            "contactId":   contact_id,
            "startTime":   start_iso,
            "endTime":     end_iso,
            "title":       title,
            "appointmentStatus": "confirmed",
            "assignedUserId": GHL_ASSIGNED_USER,
            "ignoreDateRange": False,
            "toNotify": True,
        }

        url = f"{GHL_BASE_URL}/calendars/events/appointments"

        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(url, headers=get_headers(), json=payload)
            resp.raise_for_status()
            data = resp.json()

        appointment_id = data.get("id", "")

        TZ = pytz.timezone(TIMEZONE)
        dt = datetime.fromisoformat(start_iso).astimezone(TZ)
        dia = DIAS[dt.weekday()]
        mes = MONTHS_ES[dt.month]
        hora = dt.strftime("%I:%M %p").lstrip("0").lower()
        label = f"{dia} {dt.day} de {mes} a las {hora}"

        return {
            "success": True,
            "appointment_id": appointment_id,
            "label": label,
            "message": f"Listo, tu auditoria quedo confirmada para el {label}. En breve recibes la confirmacion.",
        }

    except httpx.HTTPStatusError as e:
        return {
            "success": False,
            "error": f"Error al crear cita: {e.response.status_code} - {e.response.text}"
        }
    finally:
        lock.release()
