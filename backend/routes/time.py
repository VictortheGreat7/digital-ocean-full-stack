"""
Time-related endpoints.
"""

from __future__ import annotations

from time import sleep
from threading import Thread, Event
from telemetry import tracer
from datetime import datetime
from zoneinfo import available_timezones
from json import dumps as json_dumps
from flask import Blueprint, jsonify, request, Response
from helpers import format_time_response, validate_timezone
from config import CACHE_TTL_TIMEZONES, CACHE_TTL_WORLD_CLOCKS, MAJOR_CITIES


time_bp = Blueprint("time", __name__)


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


def _refresh_timezones_loop():
    """Background worker that continuously regenerates the timezones payload."""
    global _timezones_cache_json

    while True:
        with tracer.start_as_current_span("background_refresh.timezones") as span:
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
                return jsonify({"error": "Failed to fetch timezones"}), 500

            payload = json_dumps(
                {
                    "count": len(all_tz),
                    "regions": regions,
                }
            )

            # Serialize the dictionary to a JSON string exactly once per TTL cycle
            _timezones_cache_json = json_dumps(payload)

            # Signal that the cache is successfully populated
            _timezones_ready.set()

        # Sleep for the configured TTL before refreshing again
        sleep(CACHE_TTL_TIMEZONES)


# Start the background thread immediately upon module import
_timezone_refresh_thread = Thread(target=_refresh_timezones_loop, daemon=True)
_timezone_refresh_thread.start()


@time_bp.route("/timezones", methods=["GET"])
def get_timezones():
    """List every IANA timezone grouped by region."""

    # Wait up to 5 seconds for the background thread to populate the cache on initial startup
    if not _timezones_ready.wait(timeout=5.0):
        return jsonify({"error": "Service warming up, please try again."}), 503

    with tracer.start_as_current_span("cache.timezones") as span:
        # Since the background thread handles all misses, the API always hits
        span.set_attribute("cache.hit", True)

    # Return the raw, pre-calculated JSON string directly to the WSGI server
    return Response(_timezones_cache_json, mimetype="application/json")


def _refresh_world_clocks_loop():
    """Background worker that continuously regenerates the world clocks payload."""
    global _world_clocks_cache_json

    while True:
        with tracer.start_as_current_span("background_refresh.world_clocks") as span:
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
            _world_clocks_cache_json = json_dumps(payload)
            _world_clocks_ready.set()

        sleep(CACHE_TTL_WORLD_CLOCKS)


_world_clocks_refresh_thread = Thread(target=_refresh_world_clocks_loop, daemon=True)
_world_clocks_refresh_thread.start()


@time_bp.route("/world-clocks", methods=["GET"])
def get_world_clocks():
    """Return the current time for every city in ``MAJOR_CITIES``."""

    if not _world_clocks_ready.wait(timeout=5.0):
        return jsonify({"error": "Service warming up, please try again."}), 503

    with tracer.start_as_current_span("cache.world_clocks") as span:
        span.set_attribute("cache.hit", True)

    return Response(_world_clocks_cache_json, mimetype="application/json")


@time_bp.route("/legacy/time", methods=["GET"])
def get_current_time():
    """Legacy endpoint — kept for backward compatibility."""
    current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    return jsonify({"current_time": current_time})
