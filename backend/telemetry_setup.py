"""
Helper functions for telemetry bootstrap and instrumentation.
"""

from __future__ import annotations

import logging

from ddtrace.profiling import Profiler
from ddtrace.runtime import RuntimeMetrics
from flask import Flask
from opentelemetry.instrumentation.flask import FlaskInstrumentor
from opentelemetry.instrumentation.logging import LoggingInstrumentor
from opentelemetry.instrumentation.psycopg2 import Psycopg2Instrumentor
from opentelemetry.instrumentation.requests import RequestsInstrumentor
from opentelemetry.sdk.resources import Resource

from config import (
    DEPLOYMENT_ENV,
    PROFILER_ENABLED,
    RUNTIME_METRICS_ENABLED,
    SERVICE_NAME,
    SERVICE_NAMESPACE,
    SERVICE_VERSION,
)


def build_resource() -> Resource:
    return Resource(
        attributes={
            "service.name": SERVICE_NAME,
            "service.namespace": SERVICE_NAMESPACE,
            "deployment.environment": DEPLOYMENT_ENV,
            "service.version": SERVICE_VERSION,
        }
    )


def create_profiler() -> Profiler:
    return Profiler(env=DEPLOYMENT_ENV, service=SERVICE_NAME, version=SERVICE_VERSION)


def enable_runtime_metrics() -> bool:
    if RUNTIME_METRICS_ENABLED:
        RuntimeMetrics.enable()
        return True
    return False


def start_profiler(profiler: Profiler, already_started: bool) -> bool:
    if PROFILER_ENABLED and not already_started:
        profiler.start()
        return True
    return already_started


def instrument_app(app: Flask) -> None:
    FlaskInstrumentor().instrument_app(app)
    RequestsInstrumentor().instrument()
    Psycopg2Instrumentor().instrument()
    LoggingInstrumentor().instrument(set_logging_format=True)


def configure_app_logging(app: Flask) -> None:
    handler = logging.StreamHandler()
    handler.setFormatter(
        logging.Formatter(
            "%(asctime)s - %(name)s - "
            "[trace_id=%(otelTraceID)s span_id=%(otelSpanID)s] - "
            "%(levelname)s - %(message)s"
        )
    )
    app.logger.handlers.clear()
    app.logger.addHandler(handler)
    app.logger.setLevel(logging.INFO)
