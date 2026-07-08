"""
Background Cache Loops
"""

import logging
import redis_cache
from time import sleep
from telemetry import tracer
from threading import Thread, Event
from orjson import dumps as json_dumps
from helpers import format_time_response
from zoneinfo import available_timezones
from config import CACHE_TTL_TIMEZONES, CACHE_TTL_WORLD_CLOCKS, MAJOR_CITIES

logger = logging.getLogger(__name__)

# Store the pre-serialized JSON string instead of a dictionary
_timezones_cache_json: str | None = None
_world_clocks_cache_json: str | None = None

# An event flag to ensure the API doesn't return empty data on startup
_timezones_ready = Event()
_world_clocks_ready = Event()

_sorted_tz: list[str] | None = None


def _refresh_timezones_loop():
    """Background worker that continuously regenerates the timezones payload."""
    global _timezones_cache_json, _sorted_tz

    # Brief pause on startup to allow Redis connections to settle
    sleep(2)

    while True:
        try:
            if not _sorted_tz:
                _sorted_tz = sorted(available_timezones())

            is_leader = False
            redis_healthy = False

            if redis_cache.is_cache_ready():
                try:
                    lock_key = redis_cache.build_cache_key("timezones-lock")
                    is_leader = redis_cache._client.set(
                        lock_key, "locked", nx=True, ex=2
                    )
                    redis_healthy = True
                except Exception as exc:
                    logger.warning(
                        "Redis lock timed out, forcing local compute: %s", exc
                    )
                    is_leader = True
            else:
                # LOCAL MODE: Every worker calculates its own cache
                is_leader = True

            # 2. Only the leader (or local workers) spend CPU calculating
            if is_leader:
                with tracer.start_as_current_span(
                    "background_refresh.timezones.calculate"
                ) as span:
                    try:
                        regions: dict[str, list[str]] = {}
                        for tz in _sorted_tz:
                            if "/" in tz:
                                region = tz.split("/")[0]
                                regions.setdefault(region, []).append(tz)

                        payload = {
                            "count": len(_sorted_tz),
                            "regions": regions,
                        }

                        with tracer.start_as_current_span(
                            "background_refresh.timezones.serialize"
                        ):
                            # Serialize the dictionary to a JSON string exactly once per TTL cycle
                            new_cache_bytes = json_dumps(payload)

                        if redis_healthy:
                            try:
                                data_key = redis_cache.build_cache_key(
                                    "timezones", "latest"
                                )
                                redis_cache.set_raw_bytes(
                                    data_key, new_cache_bytes, CACHE_TTL_TIMEZONES + 5
                                )
                            except Exception as exc:
                                logger.warning(
                                    "Leader failed to write to Redis (falling back to memory only): %s",
                                    exc,
                                )

                        _timezones_cache_json = new_cache_bytes
                        _timezones_ready.set()

                    except Exception as exc:
                        span.set_attribute("error", True)
                        span.record_exception(exc)
                        logger.error("Failed to calculate timezones: %s", exc)

            elif redis_healthy:
                with tracer.start_as_current_span(
                    "background_refresh.timezones.follower_sync"
                ) as span:
                    try:
                        data_key = redis_cache.build_cache_key("timezones", "latest")
                        leader_bytes = redis_cache.get_raw_bytes(data_key)
                        if leader_bytes:
                            _timezones_cache_json = leader_bytes
                            _timezones_ready.set()
                            span.set_attribute("sync.success", True)
                        else:
                            span.set_attribute("sync.success", False)
                            # Use debug here because an empty cache just means the leader might not have written it yet
                            logger.debug(
                                "Follower sync found empty Redis cache, will retry next cycle."
                            )
                    except Exception as exc:
                        span.set_attribute("error", True)
                        span.record_exception(exc)
                        logger.warning(
                            "Follower pod failed to read sync data from Redis: %s", exc
                        )

        except Exception as exc:
            # If ANYTHING fails (serialization, memory issue, etc.), the thread catches it,
            # logs the error, and survives to try again on the next TTL cycle.
            logger.error("Critical failure in background timezone refresh: %s", exc)

        # Sleep for the TTL. (If Redis is active, the followers sleep too,
        # waking up exactly when the cache expires to elect a new leader).
        sleep(CACHE_TTL_TIMEZONES)


# Start the background thread immediately upon module import
_timezone_refresh_thread = Thread(target=_refresh_timezones_loop, daemon=True)
_timezone_refresh_thread.start()


def _refresh_world_clocks_loop():
    """Background worker that continuously regenerates the world clocks payload."""
    global _world_clocks_cache_json
    sleep(2)

    while True:
        try:
            is_leader = False
            redis_healthy = False

            if redis_cache.is_cache_ready():
                try:
                    lock_key = redis_cache.build_cache_key("world-clocks-lock")
                    is_leader = redis_cache._client.set(
                        lock_key, "locked", nx=True, ex=2
                    )
                    redis_healthy = True
                except Exception as exc:
                    logger.warning(
                        "Redis lock timed out, forcing local compute: %s", exc
                    )
                    is_leader = True
            else:
                is_leader = True

            if is_leader:
                with tracer.start_as_current_span(
                    "background_refresh.world_clocks.calculate"
                ) as span:
                    span.set_attribute("cities_count", len(MAJOR_CITIES))
                    cities_data: list[dict] = []

                    for city, tz_obj in MAJOR_CITIES.items():
                        try:
                            data = format_time_response(
                                str(tz_obj), tz=tz_obj, city=city
                            )
                            cities_data.append(data)
                        except Exception as exc:
                            span.set_attribute("error", True)
                            span.record_exception(exc)
                            cities_data.append({"city": city, "error": str(exc)})

                payload = {"cities": cities_data, "count": len(cities_data)}

                with tracer.start_as_current_span(
                    "background_refresh.world_clocks.serialize"
                ):
                    new_cache_bytes = json_dumps(payload)

                if redis_healthy:
                    try:
                        data_key = redis_cache.build_cache_key("world-clocks", "latest")
                        redis_cache.set_raw_bytes(
                            data_key, new_cache_bytes, CACHE_TTL_WORLD_CLOCKS + 5
                        )
                    except Exception as exc:
                        logger.warning(
                            "Leader failed to write to Redis (falling back to memory only): %s",
                            exc,
                        )

                _world_clocks_cache_json = new_cache_bytes
                _world_clocks_ready.set()

            elif redis_healthy:
                with tracer.start_as_current_span(
                    "background_refresh.world_clocks.follower_sync"
                ) as span:
                    try:
                        data_key = redis_cache.build_cache_key("world-clocks", "latest")
                        leader_bytes = redis_cache.get_raw_bytes(data_key)

                        if leader_bytes:
                            _world_clocks_cache_json = leader_bytes
                            _world_clocks_ready.set()
                            span.set_attribute("sync.success", True)
                        else:
                            span.set_attribute("sync.success", False)
                            logger.debug(
                                "Follower sync found empty Redis cache, will retry next cycle."
                            )
                    except Exception as exc:
                        span.set_attribute("error", True)
                        span.record_exception(exc)
                        logger.warning(
                            "Follower pod failed to read sync data from Redis: %s", exc
                        )

        except Exception as exc:
            logger.error("Critical failure in background clock refresh: %s", exc)

        sleep(CACHE_TTL_WORLD_CLOCKS)


_world_clocks_refresh_thread = Thread(target=_refresh_world_clocks_loop, daemon=True)
_world_clocks_refresh_thread.start()
