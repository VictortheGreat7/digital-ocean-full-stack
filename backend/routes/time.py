"""
Time-related endpoints.
"""

from __future__ import annotations

from datetime import datetime, timezone
from zoneinfo import available_timezones

from flask import Blueprint, Response, jsonify, request
from orjson import dumps as json_dumps

from helpers import format_time_response, validate_timezone
from redis_cache import build_cache_key, get_raw_bytes, is_cache_ready
from refresh_loops import (
    _sorted_tz,
    _timezones_ready,
    _world_clocks_ready,
    get_timezones_cache_json,
    get_world_clocks_cache_json,
)
from telemetry import tracer
from world_clocks import build_world_clocks_payload

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
        if _timezones_ready.is_set():
            span.set_attribute("cache.hit", True)
            span.set_attribute("cache.type", "memory")
            return Response(get_timezones_cache_json(), mimetype="application/json")

        span.set_attribute("cache.hit", False)

    return jsonify({"error": "Service warming up or cache unavailable."}), 503


@time_bp.route("/world-clocks", methods=["GET"])
def get_world_clocks():
    """Return the current time for every city in ``MAJOR_CITIES``, or searched cities."""

    search_query = request.args.get("search", "")

    if search_query:
        with tracer.start_as_current_span("search.world_clocks") as span:
            normalized_search = search_query.strip().lower()
            span.set_attribute("search_query", normalized_search)
            payload = json_dumps(
                build_world_clocks_payload(
                    normalized_search,
                    all_timezones=_sorted_tz or available_timezones(),
                )
            )
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
        if _world_clocks_ready.is_set():
            span.set_attribute("cache.hit", True)
            span.set_attribute("cache.type", "memory")
            return Response(get_world_clocks_cache_json(), mimetype="application/json")

        span.set_attribute("cache.hit", False)
        
    return jsonify({"error": "Service warming up or cache unavailable."}), 503


@time_bp.route("/legacy/time", methods=["GET"])
def get_current_time():
    """Legacy endpoint — kept for backward compatibility."""
    current_time = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
    return jsonify({"current_time": current_time})
