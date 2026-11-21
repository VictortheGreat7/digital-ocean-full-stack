"""Tests for liveness and readiness endpoints."""

from __future__ import annotations

import redis_cache
import refresh_loops


def test_health_reports_alive(client):
    response = client.get("/health")

    assert response.status_code == 200
    assert response.get_json() == {"status": "alive"}


def test_ready_is_503_while_caches_warm_up(client):
    response = client.get("/ready")

    assert response.status_code == 503
    assert response.get_json() == {
        "status": "not_ready",
        "checks": {"cache": "not_set"},
    }


def test_ready_requires_both_local_caches(client):
    refresh_loops._timezones_ready.set()

    response = client.get("/ready")

    assert response.status_code == 503


def test_ready_when_both_local_caches_are_ready(client):
    refresh_loops._timezones_ready.set()
    refresh_loops._world_clocks_ready.set()

    response = client.get("/ready")

    assert response.status_code == 200
    assert response.get_json() == {
        "status": "ready",
        "checks": {"cache": "ready"},
    }


def test_ready_when_redis_is_ready(client, monkeypatch):
    monkeypatch.setattr(redis_cache, "is_cache_ready", lambda: True)

    response = client.get("/ready")

    assert response.status_code == 200
    assert response.get_json()["status"] == "ready"
