"""
Time-related endpoints.
"""

from __future__ import annotations

from datetime import datetime
from zoneinfo import available_timezones

from flask import Blueprint, jsonify, request

from cache import build_cache_key, get_json, set_json

from config import CACHE_TTL_TIMEZONES
from helpers import format_time_response, validate_timezone
from telemetry import tracer


time_bp = Blueprint("time", __name__)


@time_bp.route("/time", methods=["GET"])
def get_time():
    """Return the current time for a given timezone (default: UTC)."""
    timezone = request.args.get("timezone", "UTC")

    try:
        validate_timezone(timezone)
        data = format_time_response(timezone)
        return jsonify(data)
    except ValueError:
        return jsonify({"error": f"Unknown timezone: {timezone}"}), 400


@time_bp.route("/timezones", methods=["GET"])
def get_timezones():
    """List every IANA timezone grouped by region."""
    cache_key = build_cache_key("timezones", "v1")
    cached = get_json(cache_key)

    if cached is not None:
        with tracer.start_as_current_span("cache.timezones") as span:
            span.set_attribute("cache.key", cache_key)
            span.set_attribute("cache.hit", True)
        return jsonify(cached)

    all_tz = sorted(available_timezones())
    regions: dict[str, list[str]] = {}
    for tz in all_tz:
        if "/" in tz:
            region = tz.split("/")[0]
            regions.setdefault(region, []).append(tz)

    payload = {
        "count": len(all_tz),
        "regions": regions,
    }
    set_json(cache_key, payload, CACHE_TTL_TIMEZONES)

    with tracer.start_as_current_span("cache.timezones") as span:
        span.set_attribute("cache.key", cache_key)
        span.set_attribute("cache.hit", False)

    return jsonify(payload)


@time_bp.route("/world-clocks", methods=["GET"])
def get_world_clocks():
    """Return the pre-computed world clocks from Redis."""
    cache_key = build_cache_key("world-clocks", "latest")
    cached = get_json(cache_key)

    if cached is not None:
        with tracer.start_as_current_span("cache.world_clocks") as span:
            span.set_attribute("cache.key", cache_key)
            span.set_attribute("cache.hit", True)
        return jsonify(cached)

    # Fallback for the very first second of a fresh deployment 
    # before the background thread completes its first run
    with tracer.start_as_current_span("cache.world_clocks") as span:
        span.set_attribute("cache.key", cache_key)
        span.set_attribute("cache.hit", False)
        
    return jsonify({"error": "Service warming up, please retry in 1 second"}), 503


@time_bp.route("/legacy/time", methods=["GET"])
def get_current_time():
    """Legacy endpoint — kept for backward compatibility."""
    current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    return jsonify({"current_time": current_time})
