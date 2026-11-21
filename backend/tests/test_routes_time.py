"""Tests for the time, timezones, world-clocks, and legacy endpoints."""

from __future__ import annotations

import re

import redis_cache
import refresh_loops


def test_time_defaults_to_utc(client):
    response = client.get("/time")

    assert response.status_code == 200
    data = response.get_json()
    assert data["timezone"] == "UTC"
    assert re.fullmatch(r"\d{2}:\d{2}:\d{2}", data["time"])
    assert re.fullmatch(r"\d{4}-\d{2}-\d{2}", data["date"])


def test_time_accepts_timezone_query_parameter(client):
    response = client.get("/time?timezone=Asia/Tokyo")

    assert response.status_code == 200
    assert response.get_json()["timezone"] == "Asia/Tokyo"


def test_time_rejects_unknown_timezone(client):
    response = client.get("/time?timezone=Mars/Olympus_Mons")

    assert response.status_code == 400
    assert response.get_json() == {
        "error": "Unknown timezone: Mars/Olympus_Mons"
    }


def test_timezones_returns_503_while_warming_up(client):
    response = client.get("/timezones")

    assert response.status_code == 503
    assert response.get_json() == {
        "error": "Service warming up or cache unavailable."
    }


def test_timezones_serves_redis_cache(client, monkeypatch):
    cached = b'{"count": 2, "regions": {"Europe": ["Europe/Paris"]}}'
    monkeypatch.setattr(redis_cache, "is_cache_ready", lambda: True)
    monkeypatch.setattr(redis_cache, "get_raw_bytes", lambda key: cached)

    response = client.get("/timezones")

    assert response.status_code == 200
    assert response.data == cached
    assert response.mimetype == "application/json"


def test_timezones_falls_back_to_memory_cache(client, monkeypatch):
    cached = b'{"count": 1, "regions": {"Europe": ["Europe/Paris"]}}'
    monkeypatch.setattr(redis_cache, "is_cache_ready", lambda: True)
    monkeypatch.setattr(redis_cache, "get_raw_bytes", lambda key: None)
    refresh_loops._timezones_ready.set()
    refresh_loops._timezones_cache_json = cached

    response = client.get("/timezones")

    assert response.status_code == 200
    assert response.data == cached


def test_timezones_serves_memory_when_cache_is_not_ready(client):
    cached = b'{"count": 1, "regions": {}}'
    refresh_loops._timezones_ready.set()
    refresh_loops._timezones_cache_json = cached

    response = client.get("/timezones")

    assert response.status_code == 200
    assert response.data == cached


def test_world_clocks_returns_503_while_warming_up(client):
    response = client.get("/world-clocks")

    assert response.status_code == 503
    assert response.get_json() == {
        "error": "Service warming up or cache unavailable."
    }


def test_world_clocks_serves_redis_cache(client, monkeypatch):
    cached = b'{"cities": [{"city": "London"}], "count": 1}'
    monkeypatch.setattr(redis_cache, "is_cache_ready", lambda: True)
    monkeypatch.setattr(redis_cache, "get_raw_bytes", lambda key: cached)

    response = client.get("/world-clocks")

    assert response.status_code == 200
    assert response.data == cached
    assert response.mimetype == "application/json"


def test_world_clocks_serves_memory_cache(client):
    cached = b'{"cities": [{"city": "London"}], "count": 1}'
    refresh_loops._world_clocks_ready.set()
    refresh_loops._world_clocks_cache_json = cached

    response = client.get("/world-clocks")

    assert response.status_code == 200
    assert response.data == cached


def test_world_clocks_search_uses_sorted_timezone_cache(client, monkeypatch):
    monkeypatch.setattr(
        refresh_loops,
        "_sorted_tz",
        ["America/New_York", "Europe/London", "Asia/Tokyo"],
    )

    response = client.get("/world-clocks?search=tokyo")

    assert response.status_code == 200
    data = response.get_json()
    assert data["count"] == 1
    assert data["cities"][0]["timezone"] == "Asia/Tokyo"


def test_world_clocks_search_falls_back_to_available_timezones(client, monkeypatch):
    monkeypatch.setattr(
        "routes.time.available_timezones",
        lambda: {"Europe/Paris", "Asia/Tokyo"},
    )

    response = client.get("/world-clocks?search=paris")

    assert response.status_code == 200
    data = response.get_json()
    assert data["count"] == 1
    assert data["cities"][0]["city"] == "Paris"


def test_world_clocks_search_normalizes_query(client):
    response = client.get("/world-clocks?search=%20TOKYO%20")

    assert response.status_code == 200
    assert response.get_json()["cities"][0]["timezone"] == "Asia/Tokyo"


def test_legacy_time_returns_formatted_utc_timestamp(client):
    response = client.get("/legacy/time")

    assert response.status_code == 200
    current_time = response.get_json()["current_time"]
    assert re.fullmatch(r"\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}", current_time)
