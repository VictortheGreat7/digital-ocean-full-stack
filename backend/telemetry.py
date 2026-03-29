"""
OpenTelemetry setup — tracer provider, exporters, and instrumentors.

Call ``init_telemetry(app)`` once from the application factory.
"""

from __future__ import annotations

import atexit
import logging

from opentelemetry import trace
from opentelemetry.instrumentation.flask import FlaskInstrumentor
from opentelemetry.instrumentation.logging import LoggingInstrumentor
from opentelemetry.instrumentation.psycopg2 import Psycopg2Instrumentor
from opentelemetry.instrumentation.requests import RequestsInstrumentor

# HTTP exporter uses standard Python sockets, which gevent can monkey-patch to be non-blocking. This allows spans to be exported in the background without blocking the main application.
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter

from opentelemetry.propagate import set_global_textmap
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.trace.propagation.tracecontext import TraceContextTextMapPropagator

from ddtrace.runtime import RuntimeMetrics
from ddtrace.profiling import Profiler


from config import (
    OTEL_EXPORTER_OTLP_ENDPOINT,
    SERVICE_NAME,
    SERVICE_NAMESPACE,
    DEPLOYMENT_ENV,
    SERVICE_VERSION,
    RUNTIME_METRICS_ENABLED,
    PROFILER_ENABLED,
)

# ── Global propagator ──────────────────────────────────────────────────
set_global_textmap(TraceContextTextMapPropagator())

# ── Resource identity ──────────────────────────────────────────────────
_resource = Resource(attributes={
    "service.name": SERVICE_NAME,
    "service.namespace": SERVICE_NAMESPACE,
    "deployment.environment": DEPLOYMENT_ENV,
    "service.version": SERVICE_VERSION,
})

# ── Tracer provider + OTLP exporter ───────────────────────────────────
tracer_provider = TracerProvider(resource=_resource)
trace.set_tracer_provider(tracer_provider)

_otlp_exporter = OTLPSpanExporter(endpoint=OTEL_EXPORTER_OTLP_ENDPOINT, timeout=20)
# We handle adding the BatchSpanProcessor in gunicorn.conf.py's post_fork hook
# to ensure the background thread survives the worker processes.

prof = Profiler(
    env="dev",
    service="kronos-backend",
    version="1.0.0"
)

_runtime_metrics_enabled = False
_profiler_enabled = False

# Convenience handle used throughout the app
tracer = trace.get_tracer(__name__)


def init_telemetry(app) -> None:
    """Instrument Flask, requests, psycopg2, and logging."""
    global _runtime_metrics_enabled, _profiler_enabled

    # Enable Datadog runtime metrics (CPU, memory, etc.)
    if RUNTIME_METRICS_ENABLED and not _runtime_metrics_enabled:
        RuntimeMetrics.enable()
        _runtime_metrics_enabled = True

    # Enable Datadog profiler (CPU and wall-time)
    if PROFILER_ENABLED and not _profiler_enabled:
        prof.start()
        _profiler_enabled = True

    # Flask auto-instrumentation (creates spans per request)
    FlaskInstrumentor().instrument_app(app)
    RequestsInstrumentor().instrument()
    Psycopg2Instrumentor().instrument()
    LoggingInstrumentor().instrument(set_logging_format=True)

    # Structured log handler with trace context
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter(
        "%(asctime)s - %(name)s - "
        "[trace_id=%(otelTraceID)s span_id=%(otelSpanID)s] - "
        "%(levelname)s - %(message)s"
    ))
    app.logger.handlers.clear()
    app.logger.addHandler(handler)
    app.logger.setLevel(logging.INFO)


@atexit.register
def _shutdown_tracer() -> None:
    tracer_provider.shutdown()
