"""Tests for the background refresh loop wiring."""

from __future__ import annotations

import refresh_loops
from config import CACHE_TTL_TIMEZONES, CACHE_TTL_WORLD_CLOCKS


class FakeThread:
    def __init__(self, *, target, daemon, name) -> None:
        self.target = target
        self.daemon = daemon
        self.name = name
        self.alive = False
        self.started = False

    def start(self):
        self.started = True
        self.alive = True

    def is_alive(self):
        return self.alive


def test_build_timezones_payload_groups_regions(monkeypatch):
    monkeypatch.setattr(
        refresh_loops,
        "available_timezones",
        lambda: {
            "UTC",
            "Europe/London",
            "Europe/Paris",
            "America/New_York",
            "NoSlash",
        },
    )

    payload = refresh_loops._build_timezones_payload()

    assert payload["count"] == 5
    assert payload["regions"] == {
        "Europe": ["Europe/London", "Europe/Paris"],
        "America": ["America/New_York"],
    }
    assert refresh_loops._sorted_tz == [
        "America/New_York",
        "Europe/London",
        "Europe/Paris",
        "NoSlash",
        "UTC",
    ]


def test_build_timezones_payload_reuses_sorted_timezones(monkeypatch):
    calls = []

    def available():
        calls.append(True)
        return {"Europe/Paris"}

    monkeypatch.setattr(refresh_loops, "available_timezones", available)

    refresh_loops._build_timezones_payload()
    refresh_loops._build_timezones_payload()

    assert calls == [True]


def test_local_cache_setters_and_getters():
    refresh_loops._set_timezones_cache(b"timezones")
    refresh_loops._set_world_clocks_cache(b"world-clocks")

    assert refresh_loops.get_timezones_cache_json() == b"timezones"
    assert refresh_loops.get_world_clocks_cache_json() == b"world-clocks"


def test_start_timezones_refresh_passes_configuration(monkeypatch):
    calls = []
    monkeypatch.setattr(
        refresh_loops,
        "run_periodic_cache_refresh",
        lambda **kwargs: calls.append(kwargs),
    )

    refresh_loops._start_timezones_refresh()

    assert calls[0]["cache_name"] == "timezones"
    assert calls[0]["ttl_seconds"] == CACHE_TTL_TIMEZONES
    assert calls[0]["payload_builder"] is refresh_loops._build_timezones_payload
    assert calls[0]["write_local_cache"] is refresh_loops._set_timezones_cache
    assert calls[0]["mark_ready"] == refresh_loops._timezones_ready.set


def test_start_world_clocks_refresh_passes_configuration(monkeypatch):
    calls = []
    monkeypatch.setattr(
        refresh_loops,
        "run_periodic_cache_refresh",
        lambda **kwargs: calls.append(kwargs),
    )

    refresh_loops._start_world_clocks_refresh()

    assert calls[0]["cache_name"] == "world-clocks"
    assert calls[0]["ttl_seconds"] == CACHE_TTL_WORLD_CLOCKS
    assert calls[0]["payload_builder"] is refresh_loops.build_world_clocks_payload
    assert calls[0]["write_local_cache"] is refresh_loops._set_world_clocks_cache
    assert calls[0]["mark_ready"] == refresh_loops._world_clocks_ready.set


def test_start_refresh_loops_starts_threads_once(monkeypatch):
    created = []

    def fake_thread(**kwargs):
        thread = FakeThread(**kwargs)
        created.append(thread)
        return thread

    monkeypatch.setattr(refresh_loops, "Thread", fake_thread)
    monkeypatch.setattr(refresh_loops, "run_periodic_cache_refresh", lambda **_: None)
    monkeypatch.setattr(refresh_loops, "_refresh_threads", [])

    refresh_loops.start_refresh_loops()
    refresh_loops.start_refresh_loops()

    assert len(created) == 2
    assert all(thread.started for thread in created)
    assert {thread.name for thread in created} == {
        "timezones-refresh",
        "world-clocks-refresh",
    }
    assert all(thread.daemon for thread in created)


def test_start_refresh_loops_restarts_after_threads_die(monkeypatch):
    created = []

    def fake_thread(**kwargs):
        thread = FakeThread(**kwargs)
        created.append(thread)
        return thread

    monkeypatch.setattr(refresh_loops, "Thread", fake_thread)
    monkeypatch.setattr(refresh_loops, "run_periodic_cache_refresh", lambda **_: None)
    monkeypatch.setattr(refresh_loops, "_refresh_threads", [])

    refresh_loops.start_refresh_loops()
    for thread in created:
        thread.alive = False
    refresh_loops.start_refresh_loops()

    assert len(created) == 4
