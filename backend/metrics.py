"""
Prometheus metrics — counters, histograms, and Flask exporter setup.

Call ``init_metrics(app)`` once from the application factory.
"""

from __future__ import annotations

from time import monotonic

from flask import Flask, g, request
from opentelemetry import trace
from opentelemetry.trace import format_trace_id
from prometheus_client import Counter, Histogram
from prometheus_flask_exporter import PrometheusMetrics

from config import EXCLUDED_PATHS
# from db import enqueue_request_log

# ── Custom application metrics ─────────────────────────────────────────
frontend_http_errors = Counter(
    "frontend_http_request_errors_total",
    "Total frontend HTTP request errors",
    ["method", "path", "status"],
)

frontend_http_latency = Histogram(
    "frontend_http_request_duration_seconds",
    "Latency of frontend HTTP requests",
    ["method", "path", "status"],
)

_metrics: PrometheusMetrics | None = None


def init_metrics(app: Flask) -> None:
    """Register the ``/metrics`` endpoint and before/after hooks."""
    global _metrics

    _metrics = PrometheusMetrics(app)
    _metrics.info("app_info", "World Clock Backend Application", version="1.0.0")

    app.before_request(_start_timer)
    app.after_request(_record_metrics)


# ── Hooks ───────────────────────────────────────────────────────────────
def _start_timer() -> None:
    g.start_time = monotonic()


def _record_metrics(response):
    """Observe latency/error metrics and enqueue an async DB log entry."""
    if request.path in EXCLUDED_PATHS:
        return response

    path = request.url_rule.rule if request.url_rule else request.path
    duration = monotonic() - g.start_time
    status = response.status_code

    # Prometheus
    frontend_http_latency.labels(method=request.method, path=path, status=status).observe(duration)
    if status >= 400:
        frontend_http_errors.labels(method=request.method, path=path, status=status).inc()

    # Enrich the active span
    root_span = trace.get_current_span()
    if root_span and root_span.get_span_context().is_valid:
        root_span.set_attribute("http.route", path)
        root_span.set_attribute("http.method", request.method)
        root_span.set_attribute("http.status_code", status)

    trace_id = (
        format_trace_id(root_span.get_span_context().trace_id)
        if root_span and root_span.get_span_context().is_valid
        else None
    )

    # Non-blocking DB log
    # enqueue_request_log(
    #     path=path,
    #     method=request.method,
    #     status=status,
    #     latency_ms=int(duration * 1000),
    #     timezone=request.args.get("timezone", "unknown"),
    #     trace_id=trace_id,
    #     span_context=root_span.get_span_context() if root_span else None,
    # )

    return response
