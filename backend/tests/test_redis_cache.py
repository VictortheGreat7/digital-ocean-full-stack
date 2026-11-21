"""Tests for the fail-open Redis cache helpers."""

from __future__ import annotations

import pytest
import redis
import redis_cache


def test_parse_sentinels_ignores_blanks_and_strips_whitespace():
    parsed = redis_cache._parse_sentinels(
        "redis-0:26379, redis-1:26380 , ,redis-2:26381"
    )

    assert parsed == [
        ("redis-0", 26379),
        ("redis-1", 26380),
        ("redis-2", 26381),
    ]


def test_parse_sentinels_rejects_missing_port():
    with pytest.raises(ValueError):
        redis_cache._parse_sentinels("redis-0")


def test_build_cache_key_uses_prefix():
    key = redis_cache.build_cache_key("world-clocks", "latest")

    assert key == f"{redis_cache.CACHE_KEY_PREFIX}:world-clocks:latest"


def test_is_cache_ready_false_by_default():
    assert redis_cache.is_cache_ready() is False


def test_get_raw_bytes_is_none_when_cache_not_ready():
    assert redis_cache.get_raw_bytes("missing") is None


def test_set_raw_bytes_is_noop_when_cache_not_ready():
    # Should not raise even though there is no client.
    redis_cache.set_raw_bytes("key", b"value", 10)


def test_get_raw_bytes_returns_value_from_client(monkeypatch, make_fake_redis):
    client = make_fake_redis(values={"key": b"value"})
    monkeypatch.setattr(redis_cache, "_client", client)
    monkeypatch.setattr(redis_cache, "_ready", True)

    assert redis_cache.get_raw_bytes("key") == b"value"
    assert client.get_calls == ["key"]


def test_get_raw_bytes_swallows_redis_errors(monkeypatch, make_fake_redis):
    client = make_fake_redis(get_error=redis.RedisError("down"))
    monkeypatch.setattr(redis_cache, "_client", client)
    monkeypatch.setattr(redis_cache, "_ready", True)

    assert redis_cache.get_raw_bytes("key") is None


def test_set_raw_bytes_uses_setex_and_minimum_ttl(monkeypatch, make_fake_redis):
    client = make_fake_redis()
    monkeypatch.setattr(redis_cache, "_client", client)
    monkeypatch.setattr(redis_cache, "_ready", True)

    redis_cache.set_raw_bytes("key", b"value", 0)

    assert client.setex_calls == [("key", 1, b"value")]


def test_set_raw_bytes_swallows_redis_errors(monkeypatch, make_fake_redis):
    client = make_fake_redis(set_error=redis.RedisError("down"))
    monkeypatch.setattr(redis_cache, "_client", client)
    monkeypatch.setattr(redis_cache, "_ready", True)

    redis_cache.set_raw_bytes("key", b"value", 10)


def test_try_acquire_lock_returns_false_when_cache_not_ready():
    assert redis_cache.try_acquire_lock("lock", 2) is False


def test_try_acquire_lock_returns_client_result(monkeypatch, make_fake_redis):
    client = make_fake_redis(set_result=True)
    monkeypatch.setattr(redis_cache, "_client", client)
    monkeypatch.setattr(redis_cache, "_ready", True)

    assert redis_cache.try_acquire_lock("lock", 2) is True
    assert client.set_calls == [("lock", "locked", True, 2)]


def test_try_acquire_lock_propagates_redis_errors(monkeypatch, make_fake_redis):
    client = make_fake_redis(set_error=redis.RedisError("down"))
    monkeypatch.setattr(redis_cache, "_client", client)
    monkeypatch.setattr(redis_cache, "_ready", True)

    with pytest.raises(redis.RedisError):
        redis_cache.try_acquire_lock("lock", 2)


def test_init_cache_disabled_clears_client(monkeypatch, make_fake_redis):
    monkeypatch.setattr(redis_cache, "_client", make_fake_redis())
    monkeypatch.setattr(redis_cache, "_ready", True)

    redis_cache.init_cache(enabled=False)

    assert redis_cache.is_cache_ready() is False


def test_init_cache_accepts_injected_client(make_fake_redis):
    client = make_fake_redis()

    redis_cache.init_cache(enabled=True, client=client)

    assert redis_cache.is_cache_ready() is True
    assert redis_cache._client is client


def test_init_cache_rejects_unhealthy_injected_client(make_fake_redis):
    client = make_fake_redis(ping_error=redis.RedisError("down"))

    redis_cache.init_cache(enabled=True, client=client)

    assert redis_cache.is_cache_ready() is False


def test_init_cache_connects_through_sentinel(monkeypatch, make_fake_redis):
    client = make_fake_redis()
    created = {}

    class FakeSentinel:
        def __init__(self, sentinels, socket_timeout, sentinel_kwargs):
            created["sentinels"] = sentinels
            created["socket_timeout"] = socket_timeout
            created["sentinel_kwargs"] = sentinel_kwargs

        def master_for(self, master_set, **kwargs):
            created["master_set"] = master_set
            created["master_kwargs"] = kwargs
            return client

    monkeypatch.setattr(redis_cache.redis.sentinel, "Sentinel", FakeSentinel)
    monkeypatch.setattr(redis_cache, "CACHE_ENABLED", True)

    redis_cache.init_cache()

    assert redis_cache.is_cache_ready() is True
    assert created["sentinels"] == redis_cache.REDIS_SENTINELS
    assert created["master_set"] == redis_cache.REDIS_MASTER_SET
    assert created["master_kwargs"]["decode_responses"] is False


def test_init_cache_handles_sentinel_failure(monkeypatch):
    class BrokenSentinel:
        def __init__(self, *args, **kwargs):
            raise redis.RedisError("sentinel down")

    monkeypatch.setattr(redis_cache.redis.sentinel, "Sentinel", BrokenSentinel)

    redis_cache.init_cache(enabled=True)

    assert redis_cache.is_cache_ready() is False
