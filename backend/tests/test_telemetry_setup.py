"""Tests for telemetry bootstrap helpers."""

from __future__ import annotations

import logging

import telemetry_setup
from flask import Flask


def test_build_resource_includes_service_attributes(monkeypatch):
    monkeypatch.setattr(telemetry_setup, "SERVICE_NAME", "kronos-test")
    monkeypatch.setattr(telemetry_setup, "SERVICE_NAMESPACE", "test")
    monkeypatch.setattr(telemetry_setup, "DEPLOYMENT_ENV", "ci")
    monkeypatch.setattr(telemetry_setup, "SERVICE_VERSION", "9.9.9")

    resource = telemetry_setup.build_resource()

    assert resource.attributes == {
        "service.name": "kronos-test",
        "service.namespace": "test",
        "deployment.environment": "ci",
        "service.version": "9.9.9",
    }


def test_create_profiler_uses_config(monkeypatch):
    calls = []

    class FakeProfiler:
        def __init__(self, **kwargs):
            calls.append(kwargs)

    monkeypatch.setattr(telemetry_setup, "Profiler", FakeProfiler)
    monkeypatch.setattr(telemetry_setup, "DEPLOYMENT_ENV", "dev")
    monkeypatch.setattr(telemetry_setup, "SERVICE_NAME", "kronos-test")
    monkeypatch.setattr(telemetry_setup, "SERVICE_VERSION", "1.2.3")

    profiler = telemetry_setup.create_profiler()

    assert isinstance(profiler, FakeProfiler)
    assert calls == [
        {"env": "dev", "service": "kronos-test", "version": "1.2.3"}
    ]


def test_enable_runtime_metrics_when_configured(monkeypatch):
    calls = []
    monkeypatch.setattr(telemetry_setup, "RUNTIME_METRICS_ENABLED", True)
    monkeypatch.setattr(
        telemetry_setup.RuntimeMetrics, "enable", lambda: calls.append(True)
    )

    assert telemetry_setup.enable_runtime_metrics() is True
    assert calls == [True]


def test_enable_runtime_metrics_when_disabled(monkeypatch):
    calls = []
    monkeypatch.setattr(telemetry_setup, "RUNTIME_METRICS_ENABLED", False)
    monkeypatch.setattr(
        telemetry_setup.RuntimeMetrics, "enable", lambda: calls.append(True)
    )

    assert telemetry_setup.enable_runtime_metrics() is False
    assert calls == []


class FakeProfiler:
    def __init__(self):
        self.started = False

    def start(self):
        self.started = True


def test_start_profiler_starts_when_enabled(monkeypatch):
    profiler = FakeProfiler()
    monkeypatch.setattr(telemetry_setup, "PROFILER_ENABLED", True)

    assert telemetry_setup.start_profiler(profiler, False) is True
    assert profiler.started is True


def test_start_profiler_is_idempotent(monkeypatch):
    profiler = FakeProfiler()
    monkeypatch.setattr(telemetry_setup, "PROFILER_ENABLED", True)

    assert telemetry_setup.start_profiler(profiler, True) is True
    assert profiler.started is False


def test_start_profiler_does_nothing_when_disabled(monkeypatch):
    profiler = FakeProfiler()
    monkeypatch.setattr(telemetry_setup, "PROFILER_ENABLED", False)

    assert telemetry_setup.start_profiler(profiler, False) is False
    assert profiler.started is False


def test_configure_app_logging_sets_handler_and_format():
    application = Flask(__name__)

    telemetry_setup.configure_app_logging(application)

    assert application.logger.level == logging.INFO
    assert len(application.logger.handlers) == 1
    formatter = application.logger.handlers[0].formatter
    assert "trace_id=%(otelTraceID)s" in formatter._fmt
    assert "span_id=%(otelSpanID)s" in formatter._fmt


def test_instrument_app_instruments_each_library(monkeypatch):
    calls = []

    class FakeFlaskInstrumentor:
        def instrument_app(self, app):
            calls.append(("flask", app))

    class FakeInstrumentor:
        def instrument(self, **kwargs):
            calls.append((self.name, kwargs))

    def fake_instrumentor(name):
        def factory():
            instance = FakeInstrumentor()
            instance.name = name
            return instance

        return factory

    monkeypatch.setattr(
        telemetry_setup, "FlaskInstrumentor", FakeFlaskInstrumentor
    )
    monkeypatch.setattr(
        telemetry_setup, "RequestsInstrumentor", fake_instrumentor("requests")
    )
    monkeypatch.setattr(
        telemetry_setup, "Psycopg2Instrumentor", fake_instrumentor("psycopg2")
    )
    monkeypatch.setattr(
        telemetry_setup, "LoggingInstrumentor", fake_instrumentor("logging")
    )
    application = Flask(__name__)

    telemetry_setup.instrument_app(application)

    assert ("flask", application) in calls
    assert ("requests", {}) in calls
    assert ("psycopg2", {}) in calls
    assert ("logging", {"set_logging_format": True}) in calls
