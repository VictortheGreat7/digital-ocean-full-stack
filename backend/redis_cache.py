"""
Redis cache helpers (fail-open).

If Redis is unavailable, the API continues serving uncached responses.
"""

from __future__ import annotations

import logging

import redis
from config import (
    CACHE_ENABLED,
    CACHE_KEY_PREFIX,
    REDIS_DB,
    REDIS_MASTER_SET,
    REDIS_PASSWORD,
    REDIS_SENTINELS_RAW,
    REDIS_SOCKET_TIMEOUT,
)

logger = logging.getLogger(__name__)

_client: redis.Redis | None = None
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


def init_cache(app=None, *, enabled: bool | None = None, client=None) -> None:
    """Initialize Redis client once at startup.

    *enabled* overrides the module-level ``CACHE_ENABLED`` setting (the
    application factory passes the Flask config value). *client* lets tests
    inject a fake Redis implementation without touching Sentinel.
    """
    global _client, _ready

    if enabled is None:
        enabled = CACHE_ENABLED

    if not enabled:
        logger.info("Cache disabled via CACHE_ENABLED=false")
        _client = None
        _ready = False
        return

    if client is not None:
        _client = client
        try:
            _client.ping()
            _ready = True
            logger.info("Redis cache connected (injected client)")
        except redis.RedisError as exc:
            _client = None
            _ready = False
            logger.warning("Redis cache unavailable: %s", exc)
        return

    try:
        sentinel = redis.sentinel.Sentinel(
            REDIS_SENTINELS,
            socket_timeout=REDIS_SOCKET_TIMEOUT,
            sentinel_kwargs={"password": REDIS_PASSWORD} if REDIS_PASSWORD else {},
        )
        _client = sentinel.master_for(
            REDIS_MASTER_SET,
            password=REDIS_PASSWORD or None,
            db=REDIS_DB,
            decode_responses=False,
            socket_timeout=REDIS_SOCKET_TIMEOUT,
        )
        _client.ping()
        _ready = True
        logger.info("Redis cache connected")
    except redis.RedisError as exc:
        _client = None
        _ready = False
        logger.warning("Redis cache unavailable: %s", exc)


def is_cache_ready() -> bool:
    return _ready and _client is not None


def build_cache_key(*parts: str) -> str:
    suffix = ":".join(parts)
    return f"{CACHE_KEY_PREFIX}:{suffix}"


def get_raw_bytes(key: str) -> bytes | None:
    """Return raw bytes from Redis to skip JSON parsing on the web thread."""
    if not is_cache_ready():
        return None
    try:
        return _client.get(key)
    except redis.RedisError as exc:
        logger.warning("Redis GET failed for key=%s: %s", key, exc)
        return None


def try_acquire_lock(key: str, ttl_seconds: int) -> bool:
    """Try to acquire a short-lived Redis lock.

    Returns ``True`` when this process acquired the lock. Raises
    ``redis.RedisError`` if Redis is unavailable; callers decide how to fall
    back in that case.
    """
    if not is_cache_ready():
        return False
    return bool(_client.set(key, "locked", nx=True, ex=ttl_seconds))


def set_raw_bytes(key: str, raw_bytes: bytes | str, ttl_seconds: int) -> None:
    """Store pre-serialized strings/bytes directly."""
    if not is_cache_ready():
        return
    try:
        _client.setex(key, max(1, ttl_seconds), raw_bytes)
    except redis.RedisError as exc:
        logger.warning("Redis SETEX failed for key=%s: %s", key, exc)
