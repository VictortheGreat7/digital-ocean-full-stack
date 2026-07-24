"""
Shared helpers — timezone formatting, validation, etc.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError


def format_time_response(
    timezone: str,
    *,
    tz: ZoneInfo | None = None,
    city: str | None = None,
) -> dict[str, Any]:
    """Return a consistent time-data dict for *timezone*.

    Raises ``ZoneInfoNotFoundError`` if the timezone is invalid.
    """
    if isinstance(tz, str):
        tz = ZoneInfo(tz)
    elif tz is None:
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
