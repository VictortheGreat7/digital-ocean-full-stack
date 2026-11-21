"""
OpenTelemetry setup — tracer provider, exporters, and instrumentors.

Call ``init_telemetry(app)`` once from the application factory.
"""

from __future__ import annotations

import atexit

from config import OTEL_EXPORTER_OTLP_ENDPOINT, TELEMETRY_ENABLED
from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.propagate import set_global_textmap
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.trace.propagation.tracecontext import TraceContextTextMapPropagator
from telemetry_setup import (
    build_resource,
    configure_app_logging,
    create_profiler,
    enable_runtime_metrics,
    instrument_app,
    start_profiler,
)

# Convenience handle used throughout the app. Creating a tracer is cheap and
# safe even before a provider is configured (it falls back to a no-op tracer).
tracer = trace.get_tracer(__name__)

_resource = None
tracer_provider: TracerProvider | None = None
_otlp_exporter: OTLPSpanExporter | None = None
prof = None

_runtime_metrics_enabled = False
_profiler_enabled = False


def configure_tracer_provider() -> None:
    """Create the global tracer provider and OTLP exporter exactly once."""
    global _resource, tracer_provider, _otlp_exporter, prof

    if tracer_provider is not None:
        return

    # ── Global propagator ──────────────────────────────────────────────
    set_global_textmap(TraceContextTextMapPropagator())

    _resource = build_resource()

    # ── Tracer provider + OTLP exporter ───────────────────────────────
    tracer_provider = TracerProvider(resource=_resource)
    trace.set_tracer_provider(tracer_provider)

    _otlp_exporter = OTLPSpanExporter(endpoint=OTEL_EXPORTER_OTLP_ENDPOINT, timeout=20)
    prof = create_profiler()


if TELEMETRY_ENABLED:
    # Production/gunicorn imports this module before the app factory runs, so
    # keep the provider available eagerly in that case.
    configure_tracer_provider()


def init_telemetry(app) -> None:
    """Instrument Flask, requests, psycopg2, and logging."""
    global _runtime_metrics_enabled, _profiler_enabled

    configure_tracer_provider()

    if not _runtime_metrics_enabled:
        _runtime_metrics_enabled = enable_runtime_metrics()

    _profiler_enabled = start_profiler(prof, _profiler_enabled)

    instrument_app(app)
    configure_app_logging(app)


@atexit.register
def _shutdown_tracer() -> None:
    if tracer_provider is not None:
        tracer_provider.shutdown()
