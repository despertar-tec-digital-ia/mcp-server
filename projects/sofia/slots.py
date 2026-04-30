import httpx
import logging
from datetime import datetime, timedelta
import pytz
from config import GHL_BASE_URL, GHL_CALENDAR_ID, TIMEZONE, SLOT_DURATION_MIN
from auth import get_headers

log = logging.getLogger(__name__)
TZ = pytz.timezone(TIMEZONE)

DIAS = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"]
MONTHS_ES = [
    "", "enero", "febrero", "marzo", "abril", "mayo", "junio",
    "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre"
]


def _format_slot(slot_dt: datetime) -> dict:
    slot_end = slot_dt + timedelta(minutes=SLOT_DURATION_MIN)
    dia = DIAS[slot_dt.weekday()]
    mes = MONTHS_ES[slot_dt.month]
    hora = slot_dt.strftime("%I:%M %p").lstrip("0").lower()
    return {
        "label": f"{dia} {slot_dt.day} de {mes} a las {hora}",
        "start_iso": slot_dt.isoformat(),
        "end_iso": slot_end.isoformat(),
    }


def _pick_spread(slots_by_day: dict[str, list[datetime]], max_slots: int) -> list[dict]:
    """
    Selects slots spread across as many different days as possible.
    Within each day, samples from early, middle, and late positions
    so the options look varied rather than all being the first slot.
    """
    days = sorted(slots_by_day.keys())
    if not days:
        return []

    picked: list[tuple[str, int]] = []
    # Three passes: early (0%), mid (50%), late (99%) within each day
    for frac in (0.0, 0.5, 0.99):
        for day in days:
            if len(picked) >= max_slots:
                break
            day_slots = slots_by_day[day]
            idx = min(int(frac * len(day_slots)), len(day_slots) - 1)
            if (day, idx) not in picked:
                picked.append((day, idx))
        if len(picked) >= max_slots:
            break

    return [_format_slot(slots_by_day[day][idx]) for day, idx in picked[:max_slots]]


async def get_available_slots(
    start_dt: datetime,
    end_dt: datetime,
    hour_start: int = 10,
    hour_end: int = 18,
    max_slots: int = 3,
) -> list[dict]:
    # GHL requires a minimum ~30-day window to return results reliably
    end_dt_extended = start_dt + timedelta(days=30)

    start_ms = int(start_dt.timestamp() * 1000)
    end_ms = int(end_dt_extended.timestamp() * 1000)

    url = f"{GHL_BASE_URL}/calendars/{GHL_CALENDAR_ID}/free-slots"
    params = {
        "startDate": start_ms,
        "endDate": end_ms,
        "timezone": TIMEZONE,
    }

    log.info(
        f"GHL free-slots | range: {start_dt.date()} -> {end_dt.date()} "
        f"| hours: {hour_start}:00-{hour_end}:00"
    )

    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.get(url, headers=get_headers(), params=params)
        resp.raise_for_status()
        data = resp.json()

    days_returned = len([k for k in data if k != "traceId"])
    log.info(f"GHL response: {resp.status_code} | days in payload: {days_returned}")

    start_date = start_dt.date()
    end_date = end_dt.date()
    slots_by_day: dict[str, list[datetime]] = {}

    for date_str, day_data in data.items():
        if date_str == "traceId":
            continue

        for slot_iso in day_data.get("slots", []):
            slot_dt = datetime.fromisoformat(slot_iso).astimezone(TZ)
            slot_date = slot_dt.date()

            if slot_date < start_date or slot_date > end_date:
                continue

            if slot_dt.hour < hour_start or slot_dt.hour >= hour_end:
                continue

            slots_by_day.setdefault(slot_date.isoformat(), []).append(slot_dt)

    total = sum(len(v) for v in slots_by_day.values())
    log.info(f"Matching slots: {total} across {len(slots_by_day)} day(s)")

    return _pick_spread(slots_by_day, max_slots)
