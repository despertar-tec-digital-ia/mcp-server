from datetime import datetime, timedelta, date
import pytz
from config import TIMEZONE

TZ = pytz.timezone(TIMEZONE)

WEEKDAYS_ES = {
    "lunes": 0,
    "martes": 1,
    "miércoles": 2,
    "miercoles": 2,
    "jueves": 3,
    "viernes": 4,
    "sábado": 5,
    "sabado": 5,
    "domingo": 6,
}

DAYS_ES = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"]

MONTHS_ES = [
    "", "enero", "febrero", "marzo", "abril", "mayo", "junio",
    "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre"
]

BUSINESS_START = 10
BUSINESS_END = 18


def _localize(d: date, hour: int, minute: int = 0) -> datetime:
    return TZ.localize(datetime(d.year, d.month, d.day, hour, minute))


def _next_business_days(from_date: date, count: int) -> list[date]:
    """Returns `count` business days starting the day after from_date."""
    result = []
    current = from_date + timedelta(days=1)
    while len(result) < count:
        if current.weekday() < 5:
            result.append(current)
        current += timedelta(days=1)
    return result


def _week_bounds(ref_date: date, offset_weeks: int = 0) -> tuple[date, date]:
    monday = ref_date - timedelta(days=ref_date.weekday())
    monday += timedelta(weeks=offset_weeks)
    friday = monday + timedelta(days=4)
    return monday, friday


def _description(start_date: date, end_date: date, hour_start: int, hour_end: int) -> str:
    mes_start = MONTHS_ES[start_date.month]
    mes_end = MONTHS_ES[end_date.month]
    if start_date == end_date:
        day_name = DAYS_ES[start_date.weekday()]
        return f"{day_name} {start_date.day} de {mes_start} entre {hour_start}:00 y {hour_end}:00"
    start_name = DAYS_ES[start_date.weekday()]
    end_name = DAYS_ES[end_date.weekday()]
    if mes_start == mes_end:
        return f"{start_name} {start_date.day} al {end_name} {end_date.day} de {mes_start}"
    return f"{start_name} {start_date.day} de {mes_start} al {end_name} {end_date.day} de {mes_end}"


def parse_natural_datetime(text: str) -> dict:
    """
    Converts natural Spanish text into a date range + time-of-day bounds.

    Returns:
    {
        "start": datetime,
        "end": datetime,
        "hour_start": int,
        "hour_end": int,
        "parsed_description": str,
        "no_slots_message": str | None,
    }
    """
    t = text.lower().strip()
    now = datetime.now(TZ)
    today = now.date()

    hour_start = BUSINESS_START
    hour_end = BUSINESS_END
    start_date = None
    end_date = None

    # --- Time-of-day detection (runs first so multi-day ranges respect it) ---
    if any(p in t for p in ["en la mañana", "por la mañana", "a media mañana",
                             "en la manana", "por la manana"]):
        hour_start = BUSINESS_START
        hour_end = 12

    elif any(p in t for p in ["en la tarde", "por la tarde", "a media tarde"]):
        hour_start = 14
        hour_end = BUSINESS_END

    elif any(p in t for p in ["a mediodía", "al mediodía", "a mediodia", "al mediodia",
                               "a medio día", "al medio dia"]):
        hour_start = 12
        hour_end = 14

    elif any(p in t for p in ["en la noche", "por la noche"]):
        hour_start = 18
        hour_end = 20

    # --- Weekend: no availability ---
    if any(p in t for p in ["el finde", "fin de semana", "el sábado", "el sabado",
                             "el domingo", "finde"]):
        message = (
            "Los fines de semana no tenemos citas disponibles. "
            "¿Prefieres algún día entre semana, como el lunes o el martes?"
        )
        days_to_sat = (5 - today.weekday()) % 7 or 7
        sat = today + timedelta(days=days_to_sat)
        return {
            "start": _localize(sat, hour_start),
            "end": _localize(sat, hour_end),
            "hour_start": hour_start,
            "hour_end": hour_end,
            "parsed_description": "Fin de semana",
            "no_slots_message": message,
        }

    # --- Multi-day ranges ---
    if any(p in t for p in ["la próxima semana", "la proxima semana",
                             "la próxima", "la proxima", "siguiente semana"]):
        monday, friday = _week_bounds(today, offset_weeks=1)
        start_date = monday
        end_date = friday

    elif any(p in t for p in ["esta semana", "esta sem"]):
        monday, friday = _week_bounds(today, offset_weeks=0)
        effective_start = max(monday, today)
        if effective_start.weekday() >= 5:
            monday, friday = _week_bounds(today, offset_weeks=1)
            effective_start = monday
        start_date = effective_start
        end_date = friday

    elif any(p in t for p in ["cuando puedas", "cuando tengas", "cuando sea",
                               "cuando quieras", "en cualquier momento"]):
        days = _next_business_days(today, 3)
        start_date = days[0]
        end_date = days[-1]

    # --- Single-day expressions ---
    elif any(p in t for p in ["ahorita", "ahora mismo", "hoy mismo"]):
        start_date = today
        end_date = today

    elif "hoy" in t:
        start_date = today
        end_date = today

    elif "pasado mañana" in t or "pasado manana" in t:
        start_date = today + timedelta(days=2)
        end_date = start_date

    elif "mañana" in t or "manana" in t:
        start_date = today + timedelta(days=1)
        end_date = start_date

    else:
        for day_name, weekday in WEEKDAYS_ES.items():
            if day_name in t:
                days_ahead = (weekday - today.weekday()) % 7
                if days_ahead == 0:
                    days_ahead = 7
                start_date = today + timedelta(days=days_ahead)
                end_date = start_date
                break

    # Default fallback: tomorrow
    if start_date is None:
        start_date = today + timedelta(days=1)
        end_date = start_date

    # Skip weekends on start_date
    while start_date.weekday() >= 5:
        start_date += timedelta(days=1)
    if end_date < start_date:
        end_date = start_date

    return {
        "start": _localize(start_date, hour_start),
        "end": _localize(end_date, hour_end),
        "hour_start": hour_start,
        "hour_end": hour_end,
        "parsed_description": _description(start_date, end_date, hour_start, hour_end),
        "no_slots_message": None,
    }
