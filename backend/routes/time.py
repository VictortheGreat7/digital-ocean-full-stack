"""
Time-related endpoints.
"""

from __future__ import annotations

from telemetry import tracer
from datetime import datetime
from zoneinfo import available_timezones
from orjson import dumps as json_dumps
from flask import Blueprint, jsonify, request, Response
from helpers import format_time_response, validate_timezone
from redis_cache import is_cache_ready, build_cache_key, get_raw_bytes
from refresh_loops import (
    _timezones_ready,
    _timezones_cache_json,
    _sorted_tz,
    _world_clocks_ready,
    _world_clocks_cache_json,
)

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


@time_bp.route("/timezones", methods=["GET"])
def get_timezones():
    """List every IANA timezone grouped by region."""

    with tracer.start_as_current_span("cache.timezones") as span:
        # 1. Try Redis Fast Path
        if is_cache_ready():
            data_key = build_cache_key("timezones", "latest")
            cached_bytes = get_raw_bytes(data_key)
            if cached_bytes:
                span.set_attribute("cache.hit", True)
                span.set_attribute("cache.type", "redis")
                return Response(cached_bytes, mimetype="application/json")

        # 2. Fallback to Local Memory Path
        if _timezones_ready.wait(timeout=5.0):
            span.set_attribute("cache.hit", True)
            span.set_attribute("cache.type", "memory")
            return Response(_timezones_cache_json, mimetype="application/json")

        span.set_attribute("cache.hit", False)

    return jsonify({"error": "Service warming up or cache unavailable."}), 503


@time_bp.route("/world-clocks", methods=["GET"])
def get_world_clocks():
    """Return the current time for every city in ``MAJOR_CITIES``, or searched cities."""

    search_query = request.args.get("search", "").strip().lower()

    if search_query:
        with tracer.start_as_current_span("search.world_clocks") as span:
            span.set_attribute("search_query", search_query)

            all_tzs = _sorted_tz or available_timezones()
            # Filter timezones (e.g., "Lagos" matches "Africa/Lagos")
            matched_tzs = [
                tz
                for tz in all_tzs
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
        if is_cache_ready():
            data_key = build_cache_key("world-clocks", "latest")
            cached_bytes = get_raw_bytes(data_key)
            if cached_bytes:
                span.set_attribute("cache.hit", True)
                span.set_attribute("cache.type", "redis")
                return Response(cached_bytes, mimetype="application/json")

        # 2. Fallback to Local Memory Path
        if _world_clocks_ready.wait(timeout=5.0):
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
