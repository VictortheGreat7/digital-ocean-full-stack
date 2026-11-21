"""Tests for timezone formatting and validation helpers."""

from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import pytest
from helpers import format_time_response, validate_timezone


def test_format_time_response_uses_supplied_time():
    now = datetime(2024, 1, 15, 12, 34, 56, tzinfo=ZoneInfo("UTC"))

    data = format_time_response("UTC", now=now)

    assert data == {
        "timezone": "UTC",
        "datetime": "2024-01-15T12:34:56+00:00",
        "time": "12:34:56",
        "time_12h": "12:34:56 PM",
        "date": "2024-01-15",
        "day": "Monday",
        "offset": "+0000",
        "offset_hours": 0,
        "is_day": True,
        "is_dst": False,
    }


@pytest.mark.parametrize(
    ("hour", "expected_is_day"),
    [(0, False), (5, False), (6, True), (17, True), (18, False), (23, False)],
)
def test_format_time_response_daylight_window(hour, expected_is_day):
    now = datetime(2024, 1, 15, hour, 0, tzinfo=ZoneInfo("UTC"))

    data = format_time_response("UTC", now=now)

    assert data["is_day"] is expected_is_day


def test_format_time_response_converts_aware_time_to_target_timezone():
    # 12:00 UTC is 08:00 in New York during daylight saving time.
    now = datetime(2024, 7, 1, 12, 0, tzinfo=ZoneInfo("UTC"))

    data = format_time_response("America/New_York", now=now)

    assert data["time"] == "08:00:00"
    assert data["offset"] == "-0400"
    assert data["offset_hours"] == -4
    assert data["is_dst"] is True


def test_format_time_response_treats_naive_time_as_target_timezone():
    now = datetime(2024, 1, 15, 9, 30)

    data = format_time_response("Asia/Tokyo", now=now)

    assert data["time"] == "09:30:00"
    assert data["offset"] == "+0900"
    assert data["offset_hours"] == 9


def test_format_time_response_accepts_tz_and_city():
    now = datetime(2024, 1, 15, 12, 0, tzinfo=ZoneInfo("UTC"))

    data = format_time_response(
        "Europe/Paris", tz=ZoneInfo("Europe/Paris"), city="Paris", now=now
    )

    assert data["timezone"] == "Europe/Paris"
    assert data["city"] == "Paris"
    assert data["time"] == "13:00:00"


def test_format_time_response_accepts_string_tz():
    now = datetime(2024, 1, 15, 12, 0, tzinfo=ZoneInfo("UTC"))

    data = format_time_response("UTC", tz="UTC", now=now)

    assert data["timezone"] == "UTC"


def test_format_time_response_rejects_unknown_timezone():
    with pytest.raises(ZoneInfoNotFoundError):
        format_time_response("Mars/Olympus_Mons")


def test_validate_timezone_returns_zoneinfo():
    tz = validate_timezone("America/New_York")

    assert isinstance(tz, ZoneInfo)
    assert str(tz) == "America/New_York"


def test_validate_timezone_raises_value_error_for_unknown_zone():
    with pytest.raises(ValueError, match="Unknown timezone: Nope/Nope"):
        validate_timezone("Nope/Nope")
