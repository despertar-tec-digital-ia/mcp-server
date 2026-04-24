import httpx
from datetime import datetime, timedelta
import pytz
from config import GHL_BASE_URL, GHL_CALENDAR_ID, TIMEZONE, SLOT_DURATION_MIN, GHL_ASSIGNED_USER
from auth import get_headers

TZ = pytz.timezone(TIMEZONE)

async def get_available_slots(
    start_dt: datetime,
    end_dt: datetime,
    max_slots: int = 3
) -> list[dict]:

    # Rango mínimo de 30 días para que GHL devuelva resultados
    end_dt_extended = start_dt + timedelta(days=30)

    start_ms = int(start_dt.timestamp() * 1000)
    end_ms   = int(end_dt_extended.timestamp() * 1000)

    url = f"{GHL_BASE_URL}/calendars/{GHL_CALENDAR_ID}/free-slots"
    params = {
        "startDate": start_ms,
        "endDate":   end_ms,
        "timezone":  TIMEZONE,
    }

    print("GHL REQUEST URL:", url)
    print("GHL REQUEST PARAMS:", params)

    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.get(url, headers=get_headers(), params=params)
        resp.raise_for_status()
        data = resp.json()

    print("GHL RESPONSE STATUS:", resp.status_code)
    print("GHL RESPONSE BODY:", str(data)[:300])

    # Formato: {"2026-04-27": {"slots": ["2026-04-27T10:00:00-06:00", ]}, }
    available = []

    for date_str, day_data in data.items():
        if date_str == "traceId":
            continue

        slots_list = day_data.get("slots", [])

        for slot_iso in slots_list:
            slot_dt = datetime.fromisoformat(slot_iso).astimezone(TZ)

            # filtrar x rango horario que pidió el usuario
            if slot_dt < start_dt or slot_dt > end_dt:
                continue

            slot_end = slot_dt + timedelta(minutes=SLOT_DURATION_MIN)

            dias = ["Lunes","Martes","Miércoles","Jueves","Viernes","Sábado","Domingo"]
            dia  = dias[slot_dt.weekday()]
            hora = slot_dt.strftime("%I:%M %p").lstrip("0").lower()
            label = f"{dia} {slot_dt.day} de {slot_dt.strftime('%B')} a las {hora}"

            available.append({
                "label":     label,
                "start_iso": slot_dt.isoformat(),
                "end_iso":   slot_end.isoformat(),
            })

            if len(available) >= max_slots:
                return available

    return available