"""
Shared engine for periodic background cache refresh loops.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from time import sleep

from orjson import dumps as json_dumps
from redis import RedisError

import redis_cache
from telemetry import tracer

PayloadBuilder = Callable[[], dict[str, object]]
CacheWriter = Callable[[bytes], None]
ReadySetter = Callable[[], None]

logger = logging.getLogger(__name__)


def run_periodic_cache_refresh(
    *,
    cache_name: str,
    ttl_seconds: int,
    payload_builder: PayloadBuilder,
    write_local_cache: CacheWriter,
    mark_ready: ReadySetter,
    startup_delay_seconds: float = 2.0,
    lock_ttl_seconds: int = 2,
) -> None:
    """Continuously publish a cache payload using leader election on Redis."""
    sleep(startup_delay_seconds)

    while True:
        try:
            _run_refresh_cycle(
                cache_name=cache_name,
                ttl_seconds=ttl_seconds,
                payload_builder=payload_builder,
                write_local_cache=write_local_cache,
                mark_ready=mark_ready,
                lock_ttl_seconds=lock_ttl_seconds,
            )
        except Exception as exc:
            logger.error(
                "Critical failure in background %s refresh: %s", cache_name, exc
            )

        sleep(ttl_seconds)


def _run_refresh_cycle(
    *,
    cache_name: str,
    ttl_seconds: int,
    payload_builder: PayloadBuilder,
    write_local_cache: CacheWriter,
    mark_ready: ReadySetter,
    lock_ttl_seconds: int,
) -> None:
    is_leader = False
    redis_healthy = False

    if redis_cache.is_cache_ready():
        try:
            lock_key = redis_cache.build_cache_key(f"{cache_name}-lock")
            is_leader = bool(
                redis_cache._client.set(
                    lock_key, "locked", nx=True, ex=lock_ttl_seconds
                )
            )
            redis_healthy = True
        except RedisError as exc:
            logger.warning("Redis lock timed out, forcing local compute: %s", exc)
            is_leader = True
    else:
        is_leader = True

    if is_leader:
        with tracer.start_as_current_span(
            f"background_refresh.{cache_name}.calculate"
        ) as span:
            try:
                payload = payload_builder()
                span.set_attribute("payload.count", payload.get("count", 0))

                with tracer.start_as_current_span(
                    f"background_refresh.{cache_name}.serialize"
                ):
                    new_cache_bytes = json_dumps(payload)

                if redis_healthy:
                    try:
                        data_key = redis_cache.build_cache_key(cache_name, "latest")
                        redis_cache.set_raw_bytes(
                            data_key, new_cache_bytes, ttl_seconds + 5
                        )
                    except RedisError as exc:
                        logger.warning(
                            "Leader failed to write to Redis (falling back to memory only): %s",
                            exc,
                        )

                write_local_cache(new_cache_bytes)
                mark_ready()

            except Exception as exc:
                span.set_attribute("error", True)
                span.record_exception(exc)
                logger.error("Failed to calculate %s: %s", cache_name, exc)

    elif redis_healthy:
        with tracer.start_as_current_span(
            f"background_refresh.{cache_name}.follower_sync"
        ) as span:
            try:
                data_key = redis_cache.build_cache_key(cache_name, "latest")
                leader_bytes = redis_cache.get_raw_bytes(data_key)

                if leader_bytes:
                    write_local_cache(leader_bytes)
                    mark_ready()
                    span.set_attribute("sync.success", True)
                else:
                    span.set_attribute("sync.success", False)
                    logger.debug(
                        "Follower sync found empty Redis cache for %s, will retry next cycle.",
                        cache_name,
                    )
            except Exception as exc:
                span.set_attribute("error", True)
                span.record_exception(exc)
                logger.warning(
                    "Follower pod failed to read sync data from Redis: %s", exc
                )
