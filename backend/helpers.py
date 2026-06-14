"""
Shared helpers — timezone formatting, validation, etc.
"""

from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError, available_timezones
from typing import Any


def format_time_response(
    timezone: str,
    *,
    tz: ZoneInfo | None = None,
    city: str | None = None,
) -> dict[str, Any]:
    """Return a consistent time-data dict for *timezone*.

    Raises ``ZoneInfoNotFoundError`` if the timezone is invalid.
    """
    if tz is None:
        tz = ZoneInfo(timezone)
    now = datetime.now(tz)

    hour = now.hour
    is_day = 6 <= hour < 18

    data: dict[str, Any] = {
        "timezone": timezone,
        "datetime": now.isoformat(),
        "time": now.strftime("%H:%M:%S"),
        "time_12h": now.strftime("%I:%M:%S %p"),
        "date": now.strftime("%Y-%m-%d"),
        "day": now.strftime("%A"),
        "offset": now.strftime("%z"),
        "offset_hours": int(now.strftime("%z")[:3]),
        "is_day": is_day,
        "is_dst": bool(now.dst()),
    }
    if city is not None:
        data["city"] = city
    return data


def validate_timezone(timezone: str) -> ZoneInfo:
    """Return a ``ZoneInfo`` instance or raise ``ValueError``."""
    try:
        return ZoneInfo(timezone)
    except (ZoneInfoNotFoundError, KeyError) as exc:
        raise ValueError(f"Unknown timezone: {timezone}") from exc

# --- Major Cities (Dynamically Generated) ---
def _generate_all_cities() -> dict[str, str]:
    cities = {}
    for tz in available_timezones():
        # Optional: Filter out generic, legacy, or non-geographic timezones
        if tz.startswith(("Etc/", "SystemV/", "US/", "posix/", "right/", "Factory")):
            continue
            
        # Extract the final part of the string and replace underscores with spaces
        # e.g., "America/Argentina/Buenos_Aires" -> "Buenos Aires"
        # e.g., "Europe/London" -> "London"
        city_name = tz.split("/")[-1].replace("_", " ")
        cities[city_name] = ZoneInfo(tz)
        
    return cities
