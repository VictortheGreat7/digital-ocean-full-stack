"""
Time-related endpoints.
"""

from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfoNotFoundError, available_timezones

from flask import Blueprint, jsonify, request

from config import MAJOR_CITIES
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
    all_tz = sorted(available_timezones())

    regions: dict[str, list[str]] = {}
    for tz in all_tz:
        if "/" in tz:
            region = tz.split("/")[0]
            regions.setdefault(region, []).append(tz)

    return jsonify({
        "count": len(all_tz),
        "regions": regions,
    })


@time_bp.route("/world-clocks", methods=["GET"])
def get_world_clocks():
    """Return the current time for every city in ``MAJOR_CITIES``."""
    cities_data: list[dict] = []

    for city, timezone in MAJOR_CITIES.items():
        with tracer.start_as_current_span(
            f"city_time_fetch.{city.replace(' ', '_')}"
        ) as span:
            span.set_attribute("city.name", city)
            span.set_attribute("city.timezone", timezone)

            try:
                data = format_time_response(timezone, city=city)
                span.set_attribute("city.is_day", data["is_day"])
                span.set_attribute("city.hour", int(data["time"][:2]))
                cities_data.append(data)
            except Exception as exc:
                span.set_attribute("error", True)
                span.record_exception(exc)
                cities_data.append({"city": city, "error": str(exc)})

    return jsonify({"cities": cities_data, "count": len(cities_data)})


@time_bp.route("/legacy/time", methods=["GET"])
def get_current_time():
    """Legacy endpoint — kept for backward compatibility."""
    current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    return jsonify({"current_time": current_time})
