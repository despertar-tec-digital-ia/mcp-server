from datetime import datetime, timedelta
import pytz
import pytest
from app.clients.sofia.slots import _format_slot, _pick_spread

TZ = pytz.timezone("America/Mexico_City")


def _dt(year, month, day, hour, minute=0):
    return TZ.localize(datetime(year, month, day, hour, minute))


def test_format_slot_label():
    dt = _dt(2025, 5, 20, 10, 0)  # Tuesday
    result = _format_slot(dt)
    assert result["label"] == "Martes 20 de mayo a las 10:00 am"


def test_format_slot_has_iso_fields():
    dt = _dt(2025, 5, 20, 10, 0)
    result = _format_slot(dt)
    assert "start_iso" in result
    assert "end_iso" in result


def test_format_slot_end_is_after_start():
    dt = _dt(2025, 5, 20, 10, 0)
    result = _format_slot(dt)
    start = datetime.fromisoformat(result["start_iso"])
    end = datetime.fromisoformat(result["end_iso"])
    assert end > start


def test_pick_spread_empty():
    result = _pick_spread({}, 3)
    assert result == []


def test_pick_spread_single_day_respects_max():
    slots = [_dt(2025, 5, 20, h) for h in range(10, 18)]
    result = _pick_spread({"2025-05-20": slots}, 3)
    assert len(result) == 3


def test_pick_spread_spreads_across_days():
    slots_by_day = {
        "2025-05-20": [_dt(2025, 5, 20, 10)],
        "2025-05-21": [_dt(2025, 5, 21, 10)],
        "2025-05-22": [_dt(2025, 5, 22, 10)],
    }
    result = _pick_spread(slots_by_day, 3)
    assert len(result) == 3
    dates = {r["start_iso"][:10] for r in result}
    assert len(dates) == 3  # one per day


def test_pick_spread_less_than_max():
    slots_by_day = {
        "2025-05-20": [_dt(2025, 5, 20, 10)],
    }
    result = _pick_spread(slots_by_day, 3)
    assert len(result) == 1


def test_pick_spread_sorted_by_day():
    slots_by_day = {
        "2025-05-22": [_dt(2025, 5, 22, 10)],
        "2025-05-20": [_dt(2025, 5, 20, 10)],
        "2025-05-21": [_dt(2025, 5, 21, 10)],
    }
    result = _pick_spread(slots_by_day, 3)
    dates = [r["start_iso"][:10] for r in result]
    assert dates == sorted(dates)
