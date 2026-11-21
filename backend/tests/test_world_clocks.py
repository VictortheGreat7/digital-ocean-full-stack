"""Tests for world-clock payload assembly."""

from __future__ import annotations

import pytest
import world_clocks
from config import MAJOR_CITIES
from world_clocks import (
    SEARCH_LIMIT,
    _build_searched_city_records,
    build_world_clocks_payload,
    normalize_search_query,
)


@pytest.mark.parametrize(
    ("raw", "expected"),
    [(None, ""), ("", ""), ("  Tokyo ", "tokyo"), ("NEW_YORK", "new_york")],
)
def test_normalize_search_query(raw, expected):
    assert normalize_search_query(raw) == expected


def test_build_searched_city_records_returns_empty_for_blank_query():
    assert _build_searched_city_records("   ", ["Europe/Paris"]) == []


def test_build_world_clocks_payload_returns_major_cities():
    payload = build_world_clocks_payload()

    assert payload["count"] == len(MAJOR_CITIES)
    assert len(payload["cities"]) == len(MAJOR_CITIES)
    assert {city["city"] for city in payload["cities"]} == set(MAJOR_CITIES)
    assert {city["timezone"] for city in payload["cities"]} == set(
        MAJOR_CITIES.values()
    )
    assert all("time" in city and "datetime" in city for city in payload["cities"])


def test_build_world_clocks_payload_matches_city_name_suffix():
    payload = build_world_clocks_payload(
        "york",
        all_timezones=[
            "America/New_York",
            "Europe/London",
            "Asia/Tokyo",
        ],
    )

    assert payload["count"] == 1
    assert payload["cities"][0]["city"] == "New York"
    assert payload["cities"][0]["timezone"] == "America/New_York"


def test_build_world_clocks_payload_replaces_underscores_in_city_name():
    payload = build_world_clocks_payload(
        "los angeles", all_timezones=["America/Los_Angeles"]
    )

    assert payload["cities"][0]["city"] == "Los Angeles"


def test_build_world_clocks_payload_does_not_match_region_names():
    payload = build_world_clocks_payload(
        "america", all_timezones=["America/New_York", "Europe/London"]
    )

    assert payload["count"] == 0
    assert payload["cities"] == []


def test_build_world_clocks_payload_limits_search_results(monkeypatch):
    timezones = [f"Test/Zone_{index:02d}" for index in range(SEARCH_LIMIT + 5)]
    monkeypatch.setattr(world_clocks, "validate_timezone", lambda tz: object())
    monkeypatch.setattr(
        world_clocks,
        "format_time_response",
        lambda timezone, *, tz=None, city=None: {
            "timezone": timezone,
            "city": city,
        },
    )

    payload = build_world_clocks_payload("zone", all_timezones=timezones)

    assert payload["count"] == SEARCH_LIMIT
    assert len(payload["cities"]) == SEARCH_LIMIT


def test_build_world_clocks_payload_skips_invalid_timezones():
    payload = build_world_clocks_payload(
        "invalid", all_timezones=["Nowhere/Invalid", "Europe/Paris"]
    )

    assert payload["count"] == 0


def test_build_world_clocks_payload_ignores_whitespace_only_search():
    payload = build_world_clocks_payload("   ", all_timezones=["Europe/Paris"])

    assert payload["count"] == len(MAJOR_CITIES)
