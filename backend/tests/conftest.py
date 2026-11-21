"""Shared pytest fixtures for the Kronos backend.

Environment variables are set before importing the application so that the
production defaults (telemetry, metrics, cache, background loops) are disabled
for the whole test session.
"""

from __future__ import annotations

import os
from queue import Empty

# Must run before importing app/config. Force test-safe values so an
# operator's shell environment cannot make the suite depend on Redis, OTel, etc.
os.environ["TELEMETRY_ENABLED"] = "false"
os.environ["METRICS_ENABLED"] = "false"
os.environ["CACHE_ENABLED"] = "false"
os.environ["REFRESH_LOOPS_ENABLED"] = "false"
os.environ["DB_ENABLED"] = "false"
os.environ["REQUEST_LOG_WRITER_ENABLED"] = "false"

import db
import pytest
import redis_cache
import refresh_loops
import request_log_writer
from app import create_app

TEST_CONFIG = {
    "TESTING": True,
    "ENABLE_TELEMETRY": False,
    "ENABLE_METRICS": False,
    "ENABLE_CACHE": False,
    "ENABLE_REFRESH_LOOPS": False,
    "ENABLE_DB": False,
    "ENABLE_REQUEST_LOG_WRITER": False,
}


class FakeRedis:
    """Small in-memory stand-in for the Redis commands used by the backend."""

    def __init__(
        self,
        values: dict | None = None,
        *,
        ping_error: Exception | None = None,
        get_error: Exception | None = None,
        set_error: Exception | None = None,
        set_result: bool = True,
    ) -> None:
        self.values = dict(values or {})
        self.ping_error = ping_error
        self.get_error = get_error
        self.set_error = set_error
        self.set_result = set_result
        self.get_calls: list[str] = []
        self.set_calls: list[tuple] = []
        self.setex_calls: list[tuple] = []

    def ping(self):
        if self.ping_error is not None:
            raise self.ping_error
        return True

    def get(self, key):
        self.get_calls.append(key)
        if self.get_error is not None:
            raise self.get_error
        return self.values.get(key)

    def set(self, key, value, nx=False, ex=None):
        if self.set_error is not None:
            raise self.set_error
        self.set_calls.append((key, value, nx, ex))
        if nx and key in self.values:
            return None
        self.values[key] = value
        return self.set_result

    def setex(self, key, ttl, value):
        if self.set_error is not None:
            raise self.set_error
        self.setex_calls.append((key, ttl, value))
        self.values[key] = value
        return True


def _drain_queue() -> None:
    queue = request_log_writer._log_queue
    if not hasattr(queue, "get_nowait"):
        return
    while True:
        try:
            queue.get_nowait()
        except Empty:
            return


@pytest.fixture(autouse=True)
def reset_module_state(monkeypatch):
    """Reset process-global state between tests."""
    monkeypatch.setattr(redis_cache, "_client", None)
    monkeypatch.setattr(redis_cache, "_ready", False)

    monkeypatch.setattr(refresh_loops, "_timezones_cache_json", None)
    monkeypatch.setattr(refresh_loops, "_world_clocks_cache_json", None)
    monkeypatch.setattr(refresh_loops, "_sorted_tz", None)
    monkeypatch.setattr(refresh_loops, "_refresh_threads", [])
    refresh_loops._timezones_ready.clear()
    refresh_loops._world_clocks_ready.clear()

    monkeypatch.setattr(request_log_writer, "_dropped_since_last_log", 0)
    monkeypatch.setattr(request_log_writer, "_last_drop_log_at", 0.0)
    request_log_writer.set_enabled(False)
    _drain_queue()

    monkeypatch.setattr(db, "_writer_pool", None)
    monkeypatch.setattr(db, "_shutdown_registered", False)
    monkeypatch.setattr(db, "_shutdown_called", False)

    yield

    request_log_writer.set_enabled(False)
    _drain_queue()
    refresh_loops._timezones_ready.clear()
    refresh_loops._world_clocks_ready.clear()


@pytest.fixture
def app():
    return create_app(TEST_CONFIG)


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def make_fake_redis():
    return FakeRedis
