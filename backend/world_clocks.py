"""
World clock assembly for the GET /world-clocks route.
"""

from __future__ import annotations

import logging
from collections.abc import Iterable
from zoneinfo import ZoneInfoNotFoundError, available_timezones

from config import MAJOR_CITIES
from helpers import format_time_response, validate_timezone

logger = logging.getLogger(__name__)

SEARCH_LIMIT = 15


def normalize_search_query(search_query: str | None) -> str:
    """Return the normalized search query used by the world clock module."""
    return (search_query or "").strip().lower()


def _build_major_city_records() -> list[dict]:
    cities_data: list[dict] = []
    for city, timezone in MAJOR_CITIES.items():
        tz_obj = validate_timezone(timezone)
        cities_data.append(format_time_response(timezone, tz=tz_obj, city=city))
    return cities_data


def _build_searched_city_records(
    search_query: str,
    all_timezones: Iterable[str] | None = None,
) -> list[dict]:
    normalized_query = normalize_search_query(search_query)
    if not normalized_query:
        return []

    timezones = sorted(all_timezones or available_timezones())
    matched_timezones = [
        timezone
        for timezone in timezones
        if normalized_query in timezone.split("/")[-1].replace("_", " ").lower()
    ]

    matched_timezones = matched_timezones[:SEARCH_LIMIT]

    cities_data: list[dict] = []
    for timezone in matched_timezones:
        city_name = timezone.split("/")[-1].replace("_", " ")
        try:
            tz_obj = validate_timezone(timezone)
            cities_data.append(
                format_time_response(timezone, tz=tz_obj, city=city_name)
            )
        except (ValueError, ZoneInfoNotFoundError, KeyError):
            logger.warning("Failed to load timezone data for %s", timezone)
            continue

    return cities_data


def build_world_clocks_payload(
    search_query: str | None = None,
    *,
    all_timezones: Iterable[str] | None = None,
) -> dict[str, object]:
    """Return structured world-clock records and a count for the route."""
    normalized_query = normalize_search_query(search_query)
    if normalized_query:
        cities_data = _build_searched_city_records(normalized_query, all_timezones)
    else:
        cities_data = _build_major_city_records()

    return {"cities": cities_data, "count": len(cities_data)}
