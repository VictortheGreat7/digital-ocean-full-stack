"""
Background Cache Loops
"""

from __future__ import annotations

import logging
from threading import Event, Thread
from zoneinfo import available_timezones

from config import CACHE_TTL_TIMEZONES, CACHE_TTL_WORLD_CLOCKS
from refresh_loop_engine import run_periodic_cache_refresh
from world_clocks import build_world_clocks_payload

logger = logging.getLogger(__name__)

# Store the pre-serialized JSON string instead of a dictionary
_timezones_cache_json: str | None = None
_world_clocks_cache_json: str | None = None

# An event flag to ensure the API doesn't return empty data on startup
_timezones_ready = Event()
_world_clocks_ready = Event()

_sorted_tz: list[str] | None = None


def _build_timezones_payload() -> dict[str, object]:
    global _sorted_tz

    if not _sorted_tz:
        _sorted_tz = sorted(available_timezones())

    regions: dict[str, list[str]] = {}
    for tz in _sorted_tz:
        if "/" in tz:
            region = tz.split("/")[0]
            regions.setdefault(region, []).append(tz)

    return {
        "count": len(_sorted_tz),
        "regions": regions,
    }


def _set_timezones_cache(cache_bytes: bytes) -> None:
    global _timezones_cache_json
    _timezones_cache_json = cache_bytes


def _set_world_clocks_cache(cache_bytes: bytes) -> None:
    global _world_clocks_cache_json
    _world_clocks_cache_json = cache_bytes


def get_timezones_cache_json() -> bytes | None:
    return _timezones_cache_json


def get_world_clocks_cache_json() -> bytes | None:
    return _world_clocks_cache_json


def _start_timezones_refresh() -> None:
    run_periodic_cache_refresh(
        cache_name="timezones",
        ttl_seconds=CACHE_TTL_TIMEZONES,
        payload_builder=_build_timezones_payload,
        write_local_cache=_set_timezones_cache,
        mark_ready=_timezones_ready.set,
    )


def _start_world_clocks_refresh() -> None:
    run_periodic_cache_refresh(
        cache_name="world-clocks",
        ttl_seconds=CACHE_TTL_WORLD_CLOCKS,
        payload_builder=build_world_clocks_payload,
        write_local_cache=_set_world_clocks_cache,
        mark_ready=_world_clocks_ready.set,
    )


_timezone_refresh_thread = Thread(target=_start_timezones_refresh, daemon=True)
_timezone_refresh_thread.start()

_world_clocks_refresh_thread = Thread(target=_start_world_clocks_refresh, daemon=True)
_world_clocks_refresh_thread.start()
