from datetime import datetime, timedelta
import pytz
from config import TIMEZONE

TZ = pytz.timezone(TIMEZONE)

# Mapeo de lenguaje natural en español
RELATIVE_DAYS = {
    "hoy": 0,
    "mañana": 1,
    "pasado mañana": 2,
    "pasado": 2,
}

TIME_RANGES = {
    "en la mañana": (9, 0),
    "a media mañana": (10, 30),
    "al mediodía": (13, 0),
    "al mediodia": (13, 0),
    "en la tarde": (15, 0),
    "a media tarde": (16, 0),
    "en la noche": (18, 0),
    "por la mañana": (9, 0),
    "por la tarde": (15, 0),
    "por la noche": (18, 0),
}

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

def parse_natural_datetime(text: str) -> dict:
    """
    Convierte texto como "mañana en la tarde" en un rango de búsqueda.
    Devuelve: { start: datetime, end: datetime, parsed: str }
    """
    text_lower = text.lower().strip()
    now = datetime.now(TZ)
    target_date = None
    hour_start, hour_end = 9, 18  # defaults: todo el día laboral

    # Detectar día relativo
    for phrase, delta in RELATIVE_DAYS.items():
        if phrase in text_lower:
            target_date = now.date() + timedelta(days=delta)
            break

    # Detectar día de semana
    if not target_date:
        for day_name, weekday in WEEKDAYS_ES.items():
            if day_name in text_lower:
                days_ahead = (weekday - now.weekday()) % 7
                if days_ahead == 0:
                    days_ahead = 7  # si es hoy mismo, siguiente semana
                target_date = (now + timedelta(days=days_ahead)).date()
                break

    # Si no detectó nada, usar mañana por defecto
    if not target_date:
        target_date = (now + timedelta(days=1)).date()

    # Detectar rango horario
    for phrase, (h, m) in TIME_RANGES.items():
        if phrase in text_lower:
            if "mañana" in phrase or "mediodía" in phrase or "mediodia" in phrase:
                hour_start = h
                hour_end = 13
            elif "tarde" in phrase:
                hour_start = 14
                hour_end = 18
            elif "noche" in phrase:
                hour_start = 18
                hour_end = 21
            break

    start_dt = TZ.localize(datetime(target_date.year, target_date.month, target_date.day, hour_start, 0))
    end_dt   = TZ.localize(datetime(target_date.year, target_date.month, target_date.day, hour_end, 0))

    return {
        "start": start_dt,
        "end": end_dt,
        "parsed_description": f"{target_date.strftime('%A %d de %B')} entre {hour_start}:00 y {hour_end}:00"
    }
