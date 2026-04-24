import httpx
from config import GHL_BASE_URL, GHL_CALENDAR_ID, GHL_LOCATION_ID, GHL_ASSIGNED_USER
from auth import get_headers
from utils.lock import acquire_slot, SlotAlreadyBookedError

async def book_appointment(
    contact_id: str,
    start_iso: str,
    end_iso: str,
    title: str = "Auditoría Gratuita - Restaurante",
) -> dict:
    """
    Crea una cita en GHL para el contacto dado.
    Usa lock para evitar doble reserva del mismo horario.
    
    Returns:
    {
      "success": True,
      "appointment_id": "abc123",
      "label": "Martes 20 de mayo a las 10:00 am",
      "message": "Tu cita quedó confirmada para el Martes 20 de mayo..."
    }
    """

    # Anti race condition: lockea este slot mientras se procesa
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

        # Formatear mensaje de confirmación
        from datetime import datetime
        import pytz
        from config import TIMEZONE
        TZ = pytz.timezone(TIMEZONE)
        dt = datetime.fromisoformat(start_iso).astimezone(TZ)
        dias = ["Lunes","Martes","Miércoles","Jueves","Viernes","Sábado","Domingo"]
        dia = dias[dt.weekday()]
        label = f"{dia} {dt.day} de {dt.strftime('%B')} a las {dt.strftime('%I:%M %p').lower()}"

        return {
            "success": True,
            "appointment_id": appointment_id,
            "label": label,
            "message": f"¡Listo! Tu auditoría quedó confirmada para el {label}. En breve recibes la confirmación. 🎯"
        }

    except httpx.HTTPStatusError as e:
        return {
            "success": False,
            "error": f"Error al crear cita: {e.response.status_code} - {e.response.text}"
        }
    finally:
        lock.release()
