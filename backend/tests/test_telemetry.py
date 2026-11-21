"""Tests for the telemetry bootstrap module."""

from __future__ import annotations

import telemetry


def test_configure_tracer_provider_is_idempotent(monkeypatch):
    calls = []

    class FakeTracerProvider:
        def __init__(self, resource):
            calls.append(("provider", resource))

    class FakeExporter:
        def __init__(self, endpoint, timeout):
            calls.append(("exporter", endpoint, timeout))

    monkeypatch.setattr(telemetry, "tracer_provider", None)
    monkeypatch.setattr(telemetry, "_resource", None)
    monkeypatch.setattr(telemetry, "_otlp_exporter", None)
    monkeypatch.setattr(telemetry, "prof", None)
    monkeypatch.setattr(telemetry, "build_resource", lambda: "resource")
    monkeypatch.setattr(telemetry, "TracerProvider", FakeTracerProvider)
    monkeypatch.setattr(
        telemetry.trace,
        "set_tracer_provider",
        lambda provider: calls.append(("set_provider", provider)),
    )
    monkeypatch.setattr(telemetry, "OTLPSpanExporter", FakeExporter)
    monkeypatch.setattr(telemetry, "create_profiler", lambda: "profiler")
    monkeypatch.setattr(
        telemetry,
        "set_global_textmap",
        lambda propagator: calls.append(("textmap", propagator)),
    )
    monkeypatch.setattr(
        telemetry, "TraceContextTextMapPropagator", lambda: "propagator"
    )

    telemetry.configure_tracer_provider()
    telemetry.configure_tracer_provider()

    kinds = [call[0] for call in calls]
    assert kinds.count("provider") == 1
    assert kinds.count("exporter") == 1
    assert kinds.count("textmap") == 1
    assert telemetry.prof == "profiler"


def test_init_telemetry_instruments_app(monkeypatch):
    calls = []

    monkeypatch.setattr(
        telemetry, "configure_tracer_provider", lambda: calls.append("configure")
    )
    monkeypatch.setattr(
        telemetry,
        "enable_runtime_metrics",
        lambda: calls.append("runtime_metrics") or True,
    )
    monkeypatch.setattr(
        telemetry,
        "start_profiler",
        lambda profiler, started: calls.append(
            ("profiler", profiler, started)
        )
        or True,
    )
    monkeypatch.setattr(
        telemetry, "instrument_app", lambda app: calls.append(("instrument", app))
    )
    monkeypatch.setattr(
        telemetry,
        "configure_app_logging",
        lambda app: calls.append(("logging", app)),
    )
    monkeypatch.setattr(telemetry, "_runtime_metrics_enabled", False)
    monkeypatch.setattr(telemetry, "_profiler_enabled", False)
    monkeypatch.setattr(telemetry, "prof", "profiler")
    application = object()

    telemetry.init_telemetry(application)

    assert calls == [
        "configure",
        "runtime_metrics",
        ("profiler", "profiler", False),
        ("instrument", application),
        ("logging", application),
    ]
    assert telemetry._runtime_metrics_enabled is True
    assert telemetry._profiler_enabled is True


def test_init_telemetry_skips_runtime_metrics_when_already_enabled(monkeypatch):
    calls = []
    monkeypatch.setattr(telemetry, "configure_tracer_provider", lambda: None)
    monkeypatch.setattr(
        telemetry,
        "enable_runtime_metrics",
        lambda: calls.append("runtime_metrics") or True,
    )
    monkeypatch.setattr(
        telemetry, "start_profiler", lambda profiler, started: started
    )
    monkeypatch.setattr(telemetry, "instrument_app", lambda app: None)
    monkeypatch.setattr(telemetry, "configure_app_logging", lambda app: None)
    monkeypatch.setattr(telemetry, "_runtime_metrics_enabled", True)
    monkeypatch.setattr(telemetry, "_profiler_enabled", True)

    telemetry.init_telemetry(object())

    assert calls == []


def test_shutdown_tracer_handles_missing_provider(monkeypatch):
    monkeypatch.setattr(telemetry, "tracer_provider", None)

    telemetry._shutdown_tracer()


def test_shutdown_tracer_shuts_provider_down(monkeypatch):
    calls = []

    class FakeProvider:
        def shutdown(self):
            calls.append(True)

    monkeypatch.setattr(telemetry, "tracer_provider", FakeProvider())

    telemetry._shutdown_tracer()

    assert calls == [True]
