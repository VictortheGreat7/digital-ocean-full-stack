"""
Time-related endpoints.
"""

from __future__ import annotations

from datetime import datetime
from time import monotonic
from zoneinfo import available_timezones

from flask import Blueprint, jsonify, request

from threading import Lock

from cache import build_cache_key, get_json, set_json

from config import CACHE_TTL_TIMEZONES, CACHE_TTL_WORLD_CLOCKS, MAJOR_CITIES
from helpers import format_time_response, validate_timezone
from telemetry import tracer


time_bp = Blueprint("time", __name__)
_world_clocks_cache = {"data": None, "expires_at": 0}
_world_clocks_lock = Lock()


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
        span.set_attribute("cache.ttl_seconds", CACHE_TTL_TIMEZONES)

    return jsonify(payload)


@time_bp.route("/world-clocks", methods=["GET"])
def get_world_clocks():
    """Return the current time for every city in ``MAJOR_CITIES``."""

    # Fast path: read without lock
    cached = _world_clocks_cache["data"]
    expires_at = _world_clocks_cache["expires_at"]

    ttl = CACHE_TTL_WORLD_CLOCKS
    now = monotonic()
    bucket = int(now // ttl)
    cache_key = "world-clocks:local"

    if cached is not None and now < expires_at:
        with tracer.start_as_current_span("cache.world_clocks") as span:
            span.set_attribute("cache.key", cache_key)
            span.set_attribute("cache.hit", True)
            span.set_attribute("cache.bucket", bucket)
            span.set_attribute("cache.backend", "in_memory")
        return jsonify(cached)

    with _world_clocks_lock:
        # Double-check: another thread may have refreshed while we waited
        if _world_clocks_cache["data"] is not None and now < _world_clocks_cache["expires_at"]:
            return jsonify(_world_clocks_cache["data"])

        cities_data: list[dict] = []

        for city, tz_name in MAJOR_CITIES.items():
            with tracer.start_as_current_span(
                f"city_time_fetch.{city.replace(' ', '_')}"
            ) as span:
                span.set_attribute("city.name", city)
                span.set_attribute("city.timezone", tz_name)

                try:
                    data = format_time_response(tz_name, city=city)
                    span.set_attribute("city.is_day", data["is_day"])
                    span.set_attribute("city.hour", int(data["time"][:2]))
                    cities_data.append(data)
                except Exception as exc:
                    span.set_attribute("error", True)
                    span.record_exception(exc)
                    cities_data.append({"city": city, "error": str(exc)})

        payload = {"cities": cities_data, "count": len(cities_data)}
        _world_clocks_cache["data"] = payload
        _world_clocks_cache["expires_at"] = now + ttl

    with tracer.start_as_current_span("cache.world_clocks") as span:
        span.set_attribute("cache.key", cache_key)
        span.set_attribute("cache.hit", False)
        span.set_attribute("cache.bucket", bucket)
        span.set_attribute("cache.ttl_seconds", ttl)
        span.set_attribute("cache.backend", "in_memory")

    return jsonify(payload)


@time_bp.route("/legacy/time", methods=["GET"])
def get_current_time():
    """Legacy endpoint — kept for backward compatibility."""
    current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    return jsonify({"current_time": current_time})
