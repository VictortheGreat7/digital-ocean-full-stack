"""Tests for the application factory and feature toggles."""

from __future__ import annotations

import app as app_module
import db
import refresh_loops
import request_log_writer
import telemetry

DISABLED = {
    "TESTING": True,
    "ENABLE_TELEMETRY": False,
    "ENABLE_METRICS": False,
    "ENABLE_CACHE": False,
    "ENABLE_REFRESH_LOOPS": False,
    "ENABLE_DB": False,
    "ENABLE_REQUEST_LOG_WRITER": False,
}


def _create(**overrides):
    config = {**DISABLED, **overrides}
    return app_module.create_app(config)


def test_create_app_registers_all_routes():
    application = _create()

    rules = {rule.rule for rule in application.url_map.iter_rules()}
    assert {
        "/time",
        "/timezones",
        "/world-clocks",
        "/legacy/time",
        "/health",
        "/ready",
    } <= rules
    assert application.blueprints.keys() == {"time", "health"}


def test_create_app_applies_config_overrides():
    application = _create(TESTING=True, CUSTOM_SETTING="custom")

    assert application.config["TESTING"] is True
    assert application.config["CUSTOM_SETTING"] == "custom"
    assert application.config["ENABLE_CACHE"] is False


def test_create_app_enables_telemetry_when_configured(monkeypatch):
    calls = []
    monkeypatch.setattr(telemetry, "init_telemetry", lambda app: calls.append(app))

    application = _create(ENABLE_TELEMETRY=True)

    assert calls == [application]


def test_create_app_skips_telemetry_when_disabled(monkeypatch):
    calls = []
    monkeypatch.setattr(telemetry, "init_telemetry", lambda app: calls.append(app))

    _create(ENABLE_TELEMETRY=False)

    assert calls == []


def test_create_app_initialises_metrics_when_enabled(monkeypatch):
    calls = []
    monkeypatch.setattr(app_module, "init_metrics", lambda app: calls.append(app))

    application = _create(ENABLE_METRICS=True)

    assert calls == [application]


def test_create_app_passes_cache_toggle(monkeypatch):
    calls = []
    monkeypatch.setattr(
        app_module,
        "init_cache",
        lambda app, *, enabled: calls.append((app, enabled)),
    )

    application = _create(ENABLE_CACHE=True)

    assert calls == [(application, True)]


def test_create_app_initialises_db_when_enabled(monkeypatch):
    calls = []
    monkeypatch.setattr(db, "init_db", lambda app: calls.append(app))

    application = _create(ENABLE_DB=True)

    assert calls == [application]


def test_create_app_starts_request_log_writer_when_enabled(monkeypatch):
    calls = []
    monkeypatch.setattr(
        request_log_writer,
        "init_request_log_writer",
        lambda: calls.append(True),
    )

    _create(ENABLE_REQUEST_LOG_WRITER=True)

    assert calls == [True]


def test_create_app_starts_refresh_loops_when_enabled(monkeypatch):
    calls = []
    monkeypatch.setattr(
        refresh_loops, "start_refresh_loops", lambda: calls.append(True)
    )

    _create(ENABLE_REFRESH_LOOPS=True)

    assert calls == [True]


def test_create_app_skips_refresh_loops_when_disabled(monkeypatch):
    calls = []
    monkeypatch.setattr(
        refresh_loops, "start_refresh_loops", lambda: calls.append(True)
    )

    _create(ENABLE_REFRESH_LOOPS=False)

    assert calls == []


def test_cors_headers_are_present(client):
    response = client.get("/health", headers={"Origin": "http://example.com"})

    assert response.headers["Access-Control-Allow-Origin"] in {
        "*",
        "http://example.com",
    }
