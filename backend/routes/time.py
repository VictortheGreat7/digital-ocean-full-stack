"""
Time-related endpoints.
"""

from __future__ import annotations

import logging
import redis_cache
from time import sleep
from threading import Thread, Event
from telemetry import tracer
from datetime import datetime
from zoneinfo import available_timezones
from orjson import dumps as json_dumps
from flask import Blueprint, jsonify, request, Response
from helpers import format_time_response, validate_timezone
from config import CACHE_TTL_TIMEZONES, CACHE_TTL_WORLD_CLOCKS, MAJOR_CITIES


time_bp = Blueprint("time", __name__)
logger = logging.getLogger(__name__)


@time_bp.route("/time", methods=["GET"])
def get_time():
    """Return the current time for a given timezone (default: UTC)."""
    timezone = request.args.get("timezone", "UTC")

    try:
        tz = validate_timezone(timezone)
        data = format_time_response(timezone, tz=tz)
        return jsonify(data)
    except ValueError:
        return jsonify({"error": f"Unknown timezone: {timezone}"}), 400


# Store the pre-serialized JSON string instead of a dictionary
_timezones_cache_json: str | None = None
_world_clocks_cache_json: str | None = None

# An event flag to ensure the API doesn't return empty data on startup
_timezones_ready = Event()
_world_clocks_ready = Event()

_all_timezones_sorted: list[str] | None = None


def _refresh_timezones_loop():
    """Background worker that continuously regenerates the timezones payload."""
    global _timezones_cache_json, _all_timezones_sorted

    # Brief pause on startup to allow Redis connections to settle
    sleep(2)

    while True:
        try:
            is_leader = False

            # 1. Determine if this worker should do the calculation
            if redis_cache.is_cache_ready():
                # REDIS MODE: Leader Election (2-second lock)
                lock_key = redis_cache.build_cache_key("timezones-lock")
                is_leader = redis_cache._client.set(lock_key, "locked", nx=True, ex=2)
            else:
                # LOCAL MODE: Every worker calculates its own cache
                is_leader = True

            # 2. Only the leader (or local workers) spend CPU calculating
            if is_leader:
                with tracer.start_as_current_span(
                    "background_refresh.timezones.calculate"
                ) as span:
                    try:
                        all_tz = sorted(available_timezones())
                        regions: dict[str, list[str]] = {}
                        for tz in all_tz:
                            if "/" in tz:
                                region = tz.split("/")[0]
                                regions.setdefault(region, []).append(tz)
                    except Exception as exc:
                        span.set_attribute("error", True)
                        span.record_exception(exc)
                        logger.error("Failed to calculate timezones: %s", exc)
                        sleep(5)
                        continue

            _all_timezones_sorted = all_tz

            payload = {
                "count": len(all_tz),
                "regions": regions,
            }

            with tracer.start_as_current_span("background_refresh.timezones.serialize"):
                # Serialize the dictionary to a JSON string exactly once per TTL cycle
                new_cache_bytes = json_dumps(payload)
            
            # 3. Save to the appropriate storage
            if redis_cache.is_cache_ready():
                data_key = redis_cache.build_cache_key("timezones", "latest")
                redis_cache.set_raw_bytes(data_key, new_cache_bytes, CACHE_TTL_TIMEZONES + 5)
            else:
                _timezones_cache_json = new_cache_bytes
                # Signal that the cache is successfully populated
                _timezones_ready.set()

        except Exception as exc:
            # If ANYTHING fails (serialization, memory issue, etc.), the thread catches it,
            # logs the error, and survives to try again on the next TTL cycle.
            logger.error("Critical failure in background timezone refresh: %s", exc)

        # Sleep for the TTL. (If Redis is active, the followers sleep too, 
        # waking up exactly when the cache expires to elect a new leader).
        sleep(CACHE_TTL_TIMEZONES)


# Start the background thread immediately upon module import
_timezone_refresh_thread = Thread(target=_refresh_timezones_loop, daemon=True)
_timezone_refresh_thread.start()


@time_bp.route("/timezones", methods=["GET"])
def get_timezones():
    """List every IANA timezone grouped by region."""

    with tracer.start_as_current_span("cache.timezones") as span:
        
        # 1. Try Redis Fast Path
        if redis_cache.is_cache_ready():
            data_key = redis_cache.build_cache_key("timezones", "latest")
            cached_bytes = redis_cache.get_raw_bytes(data_key)
            if cached_bytes:
                span.set_attribute("cache.hit", True)
                span.set_attribute("cache.type", "redis")
                return Response(cached_bytes, mimetype="application/json")
        
        # 2. Fallback to Local Memory Path
        elif _timezones_ready.wait(timeout=5.0):
            span.set_attribute("cache.hit", True)
            span.set_attribute("cache.type", "memory")
            return Response(_timezones_cache_json, mimetype="application/json")

        span.set_attribute("cache.hit", False)

    return jsonify({"error": "Service warming up or cache unavailable."}), 503


def _refresh_world_clocks_loop():
    """Background worker that continuously regenerates the world clocks payload."""
    global _world_clocks_cache_json
    sleep(2)

    while True:
        try:
            is_leader = False

            if redis_cache.is_cache_ready():
                lock_key = redis_cache.build_cache_key("world-clocks-lock")
                is_leader = redis_cache._client.set(lock_key, "locked", nx=True, ex=2)
            else:
                is_leader = True

            if is_leader:
                with tracer.start_as_current_span(
                    "background_refresh.world_clocks.calculate"
                ) as span:
                    span.set_attribute("cities_count", len(MAJOR_CITIES))
                    cities_data: list[dict] = []

                    for city, tz_obj in MAJOR_CITIES.items():
                        try:
                            data = format_time_response(str(tz_obj), tz=tz_obj, city=city)
                            cities_data.append(data)
                        except Exception as exc:
                            span.set_attribute("error", True)
                            span.record_exception(exc)
                            cities_data.append({"city": city, "error": str(exc)})

                payload = {"cities": cities_data, "count": len(cities_data)}

                with tracer.start_as_current_span(
                    "background_refresh.world_clocks.serialize"
                ):
                    new_cache_bytes = json_dumps(payload)

                if redis_cache.is_cache_ready():
                    data_key = redis_cache.build_cache_key("world-clocks", "latest")
                    redis_cache.set_raw_bytes(data_key, new_cache_bytes, CACHE_TTL_WORLD_CLOCKS + 5)
                else:
                    _world_clocks_cache_json = new_cache_bytes
                    _world_clocks_ready.set()

        except Exception as exc:
            logger.error("Critical failure in background clock refresh: %s", exc)

        sleep(CACHE_TTL_WORLD_CLOCKS)


_world_clocks_refresh_thread = Thread(target=_refresh_world_clocks_loop, daemon=True)
_world_clocks_refresh_thread.start()


@time_bp.route("/world-clocks", methods=["GET"])
def get_world_clocks():
    """Return the current time for every city in ``MAJOR_CITIES``, or searched cities."""

    search_query = request.args.get("search", "").strip().lower()

    if search_query:
        with tracer.start_as_current_span("search.world_clocks") as span:
            span.set_attribute("search_query", search_query)

            all_tzs = _all_timezones_sorted or available_timezones()
            # Filter timezones (e.g., "Lagos" matches "Africa/Lagos")
            matched_tzs = [
                tz for tz in all_tzs
                if search_query in tz.split("/")[-1].replace("_", " ").lower()
            ]

            # Limit results to prevent expensive dynamic formatting if query is too broad
            # (e.g., typing "a" would match almost all timezones)
            matched_tzs = matched_tzs[:15]

            cities_data: list[dict] = []
            for tz_name in matched_tzs:
                # Extract a readable city from the IANA string
                # e.g., "America/Port-au-Prince" -> "Port-au-Prince"
                city_name = tz_name.split("/")[-1].replace("_", " ")

                try:
                    tz_obj = validate_timezone(tz_name)
                    data = format_time_response(tz_name, tz=tz_obj, city=city_name)
                    cities_data.append(data)
                except Exception as exc:
                    span.record_exception(exc)
                    continue

            # Return dynamic JSON
            payload = json_dumps({"cities": cities_data, "count": len(cities_data)})
            return Response(payload, mimetype="application/json")

    with tracer.start_as_current_span("cache.world_clocks") as span:
        # 1. Try Redis Fast Path
        if redis_cache.is_cache_ready():
            data_key = redis_cache.build_cache_key("world-clocks", "latest")
            cached_bytes = redis_cache.get_raw_bytes(data_key)
            if cached_bytes:
                span.set_attribute("cache.hit", True)
                span.set_attribute("cache.type", "redis")
                return Response(cached_bytes, mimetype="application/json")
        
        # 2. Fallback to Local Memory Path
        elif _world_clocks_ready.wait(timeout=5.0):
            span.set_attribute("cache.hit", True)
            span.set_attribute("cache.type", "memory")
            return Response(_world_clocks_cache_json, mimetype="application/json")

        span.set_attribute("cache.hit", False)

    return jsonify({"error": "Service warming up or cache unavailable."}), 503


@time_bp.route("/legacy/time", methods=["GET"])
def get_current_time():
    """Legacy endpoint — kept for backward compatibility."""
    current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    return jsonify({"current_time": current_time})
