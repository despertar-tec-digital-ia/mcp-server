from datetime import datetime, timedelta
import pytz
import pytest
from app.utils.datetime_parser import parse_natural_datetime, TZ


def _today():
    return datetime.now(TZ).date()


def test_hoy():
    result = parse_natural_datetime("hoy")
    assert result["no_slots_message"] is None
    assert result["start"].date() == _today()
    assert result["end"].date() == _today()


def test_manana():
    result = parse_natural_datetime("mañana")
    assert result["no_slots_message"] is None
    expected = _today() + timedelta(days=1)
    # Skip weekends
    while expected.weekday() >= 5:
        expected += timedelta(days=1)
    assert result["start"].date() == expected


def test_el_martes():
    result = parse_natural_datetime("el martes")
    assert result["no_slots_message"] is None
    assert result["start"].weekday() == 1  # Tuesday
    assert result["start"].date() > _today()


def test_proxima_semana():
    result = parse_natural_datetime("la próxima semana")
    assert result["no_slots_message"] is None
    # start should be Monday
    assert result["start"].weekday() == 0
    # end should be Friday of the same week
    assert result["end"].weekday() == 4
    assert result["end"].date() > _today()


def test_manana_en_la_tarde():
    result = parse_natural_datetime("mañana en la tarde")
    assert result["no_slots_message"] is None
    assert result["hour_start"] == 14
    assert result["hour_end"] == 18


def test_fin_de_semana_retorna_no_slots_message():
    result = parse_natural_datetime("el fin de semana")
    assert result["no_slots_message"] is not None
    assert len(result["no_slots_message"]) > 0


def test_el_sabado_retorna_no_slots_message():
    result = parse_natural_datetime("el sábado")
    assert result["no_slots_message"] is not None


def test_hora_manana():
    result = parse_natural_datetime("mañana en la mañana")
    assert result["hour_start"] == 10
    assert result["hour_end"] == 12


def test_default_horas_negocio():
    result = parse_natural_datetime("mañana")
    assert result["hour_start"] == 10
    assert result["hour_end"] == 18


def test_parsed_description_presente():
    result = parse_natural_datetime("el lunes")
    assert "parsed_description" in result
    assert len(result["parsed_description"]) > 0
