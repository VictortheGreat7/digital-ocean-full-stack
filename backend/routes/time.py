"""
Time-related endpoints.
"""

from __future__ import annotations

from datetime import datetime, timezone
from zoneinfo import available_timezones

from flask import Blueprint, jsonify, request

from cache import build_cache_key, get_json, set_json

from config import CACHE_TTL_TIMEZONES, CACHE_TTL_WORLD_CLOCKS, MAJOR_CITIES
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
        span.set_attribute("cache.ttl_seconds", CACHE_TTL_TIMEZONES)

    return jsonify(payload)


@time_bp.route("/world-clocks", methods=["GET"])
def get_world_clocks():
    """Return the current time for every city in ``MAJOR_CITIES``."""
    ttl = max(1, CACHE_TTL_WORLD_CLOCKS)
    bucket = int(datetime.now(timezone.utc).timestamp()) // ttl
    cache_key = build_cache_key("world-clocks", "v1", str(bucket))

    cached = get_json(cache_key)
    if cached is not None:
        with tracer.start_as_current_span("cache.world_clocks") as span:
            span.set_attribute("cache.key", cache_key)
            span.set_attribute("cache.hit", True)
            span.set_attribute("cache.bucket", bucket)
        return jsonify(cached)

    cities_data: list[dict] = []

    for city, timezone_name in MAJOR_CITIES.items():
        with tracer.start_as_current_span(
            f"city_time_fetch.{city.replace(' ', '_')}"
        ) as span:
            span.set_attribute("city.name", city)
            span.set_attribute("city.timezone", timezone_name)

            try:
                data = format_time_response(timezone_name, city=city)
                span.set_attribute("city.is_day", data["is_day"])
                span.set_attribute("city.hour", int(data["time"][:2]))
                cities_data.append(data)
            except Exception as exc:
                span.set_attribute("error", True)
                span.record_exception(exc)
                cities_data.append({"city": city, "error": str(exc)})

    payload = {"cities": cities_data, "count": len(cities_data)}
    set_json(cache_key, payload, ttl + 1)

    with tracer.start_as_current_span("cache.world_clocks") as span:
        span.set_attribute("cache.key", cache_key)
        span.set_attribute("cache.hit", False)
        span.set_attribute("cache.bucket", bucket)
        span.set_attribute("cache.ttl_seconds", ttl)

    return jsonify(payload)


@time_bp.route("/legacy/time", methods=["GET"])
def get_current_time():
    """Legacy endpoint — kept for backward compatibility."""
    current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    return jsonify({"current_time": current_time})
