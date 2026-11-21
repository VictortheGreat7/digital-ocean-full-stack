"""Tests for the leader-elected background cache refresh engine."""

from __future__ import annotations

import orjson
import pytest
import redis_cache
import refresh_loop_engine
from redis import RedisError


def _run_cycle(**overrides):
    calls = {
        "built": 0,
        "local": [],
        "ready": 0,
        "redis_writes": [],
    }

    def payload_builder():
        calls["built"] += 1
        return {"count": 2, "value": "fresh"}

    def write_local_cache(payload: bytes) -> None:
        calls["local"].append(payload)

    def mark_ready() -> None:
        calls["ready"] += 1

    kwargs = {
        "cache_name": "test-cache",
        "ttl_seconds": 60,
        "payload_builder": payload_builder,
        "write_local_cache": write_local_cache,
        "mark_ready": mark_ready,
        "lock_ttl_seconds": 2,
    }
    kwargs.update(overrides)

    refresh_loop_engine._run_refresh_cycle(**kwargs)
    return calls


def test_cycle_computes_locally_when_cache_is_not_ready(monkeypatch):
    monkeypatch.setattr(redis_cache, "is_cache_ready", lambda: False)

    def unexpected_lock(*args, **kwargs):
        raise AssertionError("lock must not be attempted when cache is down")

    monkeypatch.setattr(redis_cache, "try_acquire_lock", unexpected_lock)

    calls = _run_cycle()

    assert calls["built"] == 1
    assert calls["ready"] == 1
    assert orjson.loads(calls["local"][0]) == {"count": 2, "value": "fresh"}


def test_cycle_as_leader_writes_redis_and_local_cache(monkeypatch):
    monkeypatch.setattr(redis_cache, "is_cache_ready", lambda: True)
    monkeypatch.setattr(redis_cache, "try_acquire_lock", lambda key, ttl: True)

    writes = []
    monkeypatch.setattr(
        redis_cache,
        "set_raw_bytes",
        lambda key, payload, ttl: writes.append((key, payload, ttl)),
    )

    calls = _run_cycle()

    assert calls["built"] == 1
    assert calls["ready"] == 1
    assert len(writes) == 1
    key, payload, ttl = writes[0]
    assert key == redis_cache.build_cache_key("test-cache", "latest")
    assert orjson.loads(payload) == {"count": 2, "value": "fresh"}
    assert ttl == 65
    assert calls["local"] == [payload]


def test_cycle_as_follower_syncs_leader_payload(monkeypatch):
    monkeypatch.setattr(redis_cache, "is_cache_ready", lambda: True)
    monkeypatch.setattr(redis_cache, "try_acquire_lock", lambda key, ttl: False)
    monkeypatch.setattr(
        redis_cache, "get_raw_bytes", lambda key: b'{"count": 9, "value": "leader"}'
    )

    calls = _run_cycle()

    assert calls["built"] == 0
    assert calls["ready"] == 1
    assert calls["local"] == [b'{"count": 9, "value": "leader"}']


def test_cycle_as_follower_waits_when_redis_cache_is_empty(monkeypatch):
    monkeypatch.setattr(redis_cache, "is_cache_ready", lambda: True)
    monkeypatch.setattr(redis_cache, "try_acquire_lock", lambda key, ttl: False)
    monkeypatch.setattr(redis_cache, "get_raw_bytes", lambda key: None)

    calls = _run_cycle()

    assert calls["built"] == 0
    assert calls["ready"] == 0
    assert calls["local"] == []


def test_cycle_as_follower_swallows_sync_errors(monkeypatch):
    monkeypatch.setattr(redis_cache, "is_cache_ready", lambda: True)
    monkeypatch.setattr(redis_cache, "try_acquire_lock", lambda key, ttl: False)

    def broken_get(key):
        raise RedisError("read timeout")

    monkeypatch.setattr(redis_cache, "get_raw_bytes", broken_get)

    calls = _run_cycle()

    assert calls["built"] == 0
    assert calls["ready"] == 0
    assert calls["local"] == []


def test_cycle_falls_back_to_local_compute_when_lock_fails(monkeypatch):
    monkeypatch.setattr(redis_cache, "is_cache_ready", lambda: True)

    def broken_lock(*args, **kwargs):
        raise RedisError("lock timeout")

    monkeypatch.setattr(redis_cache, "try_acquire_lock", broken_lock)

    writes = []
    monkeypatch.setattr(
        redis_cache,
        "set_raw_bytes",
        lambda *args: writes.append(args),
    )

    calls = _run_cycle()

    assert calls["built"] == 1
    assert calls["ready"] == 1
    assert writes == []


def test_cycle_keeps_local_cache_when_redis_write_fails(monkeypatch):
    monkeypatch.setattr(redis_cache, "is_cache_ready", lambda: True)
    monkeypatch.setattr(redis_cache, "try_acquire_lock", lambda key, ttl: True)

    def broken_write(*args):
        raise RedisError("write timeout")

    monkeypatch.setattr(redis_cache, "set_raw_bytes", broken_write)

    calls = _run_cycle()

    assert calls["local"]
    assert calls["ready"] == 1


def test_cycle_swallows_payload_builder_errors(monkeypatch):
    monkeypatch.setattr(redis_cache, "is_cache_ready", lambda: False)

    def broken_builder():
        raise RuntimeError("boom")

    calls = _run_cycle(payload_builder=broken_builder)

    assert calls["local"] == []
    assert calls["ready"] == 0


def test_cycle_swallows_local_cache_errors(monkeypatch):
    monkeypatch.setattr(redis_cache, "is_cache_ready", lambda: False)

    def broken_write(payload):
        raise RuntimeError("disk full")

    calls = _run_cycle(write_local_cache=broken_write)

    assert calls["built"] == 1
    assert calls["ready"] == 0


def test_run_periodic_cache_refresh_runs_cycle_then_sleeps(monkeypatch):
    cycles = []
    sleeps = []

    monkeypatch.setattr(
        refresh_loop_engine,
        "_run_refresh_cycle",
        lambda **kwargs: cycles.append(kwargs),
    )

    def fake_sleep(seconds):
        sleeps.append(seconds)
        if len(sleeps) == 2:
            raise KeyboardInterrupt

    monkeypatch.setattr(refresh_loop_engine, "sleep", fake_sleep)

    with pytest.raises(KeyboardInterrupt):
        refresh_loop_engine.run_periodic_cache_refresh(
            cache_name="test-cache",
            ttl_seconds=60,
            payload_builder=dict,
            write_local_cache=lambda payload: None,
            mark_ready=lambda: None,
            startup_delay_seconds=1.5,
        )

    assert sleeps == [1.5, 60]
    assert len(cycles) == 1
    assert cycles[0]["cache_name"] == "test-cache"


def test_run_periodic_cache_refresh_survives_cycle_errors(monkeypatch):
    cycles = []
    sleeps = []

    def broken_cycle(**kwargs):
        cycles.append(kwargs)
        raise RuntimeError("unexpected")

    def fake_sleep(seconds):
        sleeps.append(seconds)
        if len(sleeps) == 2:
            raise KeyboardInterrupt

    monkeypatch.setattr(refresh_loop_engine, "_run_refresh_cycle", broken_cycle)
    monkeypatch.setattr(refresh_loop_engine, "sleep", fake_sleep)

    with pytest.raises(KeyboardInterrupt):
        refresh_loop_engine.run_periodic_cache_refresh(
            cache_name="test-cache",
            ttl_seconds=60,
            payload_builder=dict,
            write_local_cache=lambda payload: None,
            mark_ready=lambda: None,
            startup_delay_seconds=0,
        )

    assert len(cycles) == 1
    assert sleeps == [0, 60]
