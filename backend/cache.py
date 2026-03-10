"""
Redis cache helpers (fail-open).

If Redis is unavailable, the API continues serving uncached responses.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from redis.sentinel import Sentinel

from config import (
    CACHE_ENABLED,
    CACHE_KEY_PREFIX,
    REDIS_SOCKET_TIMEOUT,
    REDIS_SENTINELS_RAW,
    REDIS_MASTER_SET,
    REDIS_PASSWORD,
    REDIS_DB,
)

logger = logging.getLogger(__name__)

_client: Sentinel | None = None
_ready = False

def _parse_sentinels(raw: str) -> list[tuple[str, int]]:
    sentinels: list[tuple[str, int]] = []
    for item in raw.split(","):
        item = item.strip()
        if not item:
            continue
        host, port = item.rsplit(":", 1)
        sentinels.append((host.strip(), int(port)))
    return sentinels

REDIS_SENTINELS: list[tuple[str, int]] = _parse_sentinels(REDIS_SENTINELS_RAW)


def init_cache(app=None) -> None:
    """Initialize Redis client once at startup."""
    global _client, _ready

    if not CACHE_ENABLED:
        logger.info("Cache disabled via CACHE_ENABLED=false")
        _client = None
        _ready = False
        return

    try:
        sentinel = Sentinel(
            REDIS_SENTINELS,
            socket_timeout=REDIS_SOCKET_TIMEOUT,
            sentinel_kwargs={"password": REDIS_PASSWORD} if REDIS_PASSWORD else {},
        )
        _client = sentinel.master_for(
            REDIS_MASTER_SET,
            password=REDIS_PASSWORD or None,
            db=REDIS_DB,
            decode_responses=True,
            socket_timeout=REDIS_SOCKET_TIMEOUT,
        )
        _client.ping()
        _ready = True
        logger.info("Redis cache connected")
    except Exception as exc:
        _client = None
        _ready = False
        logger.warning("Redis cache unavailable: %s", exc)


def is_cache_ready() -> bool:
    return _ready and _client is not None


def build_cache_key(*parts: str) -> str:
    suffix = ":".join(parts)
    return f"{CACHE_KEY_PREFIX}:{suffix}"


def get_json(key: str) -> Any | None:
    """Return parsed JSON payload or None on miss/error."""
    if not is_cache_ready():
        return None
    try:
        raw = _client.get(key)
        if raw:
            return json.loads(raw)
        else:
            return None
    except Exception as exc:
        logger.warning("Redis GET failed for key=%s: %s", key, exc)
        return None


def set_json(key: str, value: Any, ttl_seconds: int) -> None:
    """Set JSON payload with TTL. Fail-open on error."""
    if not is_cache_ready():
        return
    try:
        _client.setex(key, max(1, ttl_seconds), json.dumps(value))
    except Exception as exc:
        logger.warning("Redis SETEX failed for key=%s: %s", key, exc)