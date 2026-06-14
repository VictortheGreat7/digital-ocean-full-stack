"""
Time-related endpoints.
"""

from __future__ import annotations

from time import monotonic
from threading import Lock
from telemetry import tracer
from datetime import datetime
from zoneinfo import available_timezones
from json import dumps as json_dumps
from flask import Blueprint, jsonify, request, Response
from helpers import format_time_response, validate_timezone
from config import CACHE_TTL_TIMEZONES, CACHE_TTL_WORLD_CLOCKS, MAJOR_CITIES


time_bp = Blueprint("time", __name__)

# Setup cache and lock at the module level
_timezones_lock = Lock()
_timezones_cache = {"data": None, "expires_at": 0}
_world_clocks_cache = {"data": None, "expires_at": 0}
_world_clocks_lock = Lock()


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


@time_bp.route("/timezones", methods=["GET"])
def get_timezones():
    """List every IANA timezone grouped by region."""

    cached = _timezones_cache["data"]
    expires_at = _timezones_cache["expires_at"]

    ttl = CACHE_TTL_TIMEZONES
    now = monotonic()

    if cached is not None and now < expires_at:
        with tracer.start_as_current_span("cache.timezones") as span:
            span.set_attribute("cache.hit", True)
        return Response(cached, mimetype='application/json')

    with tracer.start_as_current_span("cache.timezones") as span:
        span.set_attribute("cache.hit", False)

    with _timezones_lock:
        if (
            _timezones_cache["data"] is not None
            and now < _timezones_cache["expires_at"]
        ):
            return Response(_timezones_cache["data"], mimetype='application/json')

        with tracer.start_as_current_span("all_tz__fetch") as span:
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

        payload = {
            "count": len(all_tz),
            "regions": regions,
        }

        _timezones_cache["data"] = json_dumps(payload)
        _timezones_cache["expires_at"] = now + ttl

    return jsonify(payload)


@time_bp.route("/world-clocks", methods=["GET"])
def get_world_clocks():
    """Return the current time for every city in ``MAJOR_CITIES``."""

    # Fast path: read without lock
    cached = _world_clocks_cache["data"]
    expires_at = _world_clocks_cache["expires_at"]

    ttl = CACHE_TTL_WORLD_CLOCKS
    now = monotonic()

    if cached is not None and now < expires_at:
        with tracer.start_as_current_span("cache.world_clocks") as span:
            span.set_attribute("cache.hit", True)
        return Response(cached, mimetype='application/json')

    with tracer.start_as_current_span("cache.world_clocks") as span:
        span.set_attribute("cache.hit", False)

    with _world_clocks_lock:
        # Double-check: another thread may have refreshed while we waited
        if (
            _world_clocks_cache["data"] is not None
            and now < _world_clocks_cache["expires_at"]
        ):
            return Response(_world_clocks_cache["data"], mimetype='application/json')

        cities_data: list[dict] = []

        with tracer.start_as_current_span("background_refresh.world_clocks") as span:
            span.set_attribute("cities_count", len(MAJOR_CITIES))
            for city, tz_obj in MAJOR_CITIES.items():
                try:
                    data = format_time_response(str(tz_obj), tz=tz_obj, city=city)
                    cities_data.append(data)
                except Exception as exc:
                    span.set_attribute("error", True)
                    span.record_exception(exc)
                    cities_data.append({"city": city, "error": str(exc)})

        payload = {"cities": cities_data, "count": len(cities_data)}
        _world_clocks_cache["data"] = json_dumps(payload)
        _world_clocks_cache["expires_at"] = now + ttl

    return jsonify(payload)


@time_bp.route("/legacy/time", methods=["GET"])
def get_current_time():
    """Legacy endpoint — kept for backward compatibility."""
    current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    return jsonify({"current_time": current_time})
