"""
Prometheus metrics — counters, histograms, and Flask exporter setup.

Call ``init_metrics(app)`` once from the application factory.
"""

from __future__ import annotations

from time import monotonic

from config import EXCLUDED_PATHS
from flask import Flask, g, request
from prometheus_client import Counter, Histogram
from prometheus_flask_exporter import PrometheusMetrics
from request_observability import (
    build_request_observation,
    enrich_active_span,
    get_active_span,
    get_observed_path,
    publish_request_observation,
    should_observe_request,
)

# ── Custom application metrics ─────────────────────────────────────────
custom_request_errors = Counter(
    "custom_request_errors_total",
    "Total request errors",
    ["method", "path", "status"],
)

custom_request_latency = Histogram(
    "custom_request_duration_seconds",
    "Request Latency in seconds",
    ["method", "path", "status"],
)

_metrics: PrometheusMetrics | None = None


# ── Hooks ───────────────────────────────────────────────────────────────
def _start_timer() -> None:
    g.start_time = monotonic()


def _record_metrics(response):
    """Observe latency/error metrics and enqueue an async DB log entry."""
    if not should_observe_request(request.path, EXCLUDED_PATHS):
        return response

    start_time = getattr(g, "start_time", None)
    if start_time is None:
        return response

    path = get_observed_path(request)
    duration = monotonic() - start_time
    status = response.status_code

    # Prometheus
    custom_request_latency.labels(
        method=request.method, path=path, status=status
    ).observe(duration)
    if status >= 400:
        custom_request_errors.labels(
            method=request.method, path=path, status=status
        ).inc()

    # Enrich the active span
    root_span = get_active_span()
    enrich_active_span(root_span, path=path, method=request.method, status=status)

    publish_request_observation(
        build_request_observation(
            request,
            duration_seconds=duration,
            status_code=status,
            path=path,
            span=root_span,
        )
    )

    return response


def init_metrics(app: Flask) -> None:
    """Initialize Prometheus metrics and Flask exporter.

    The exporter and its collectors are process-global, so they are created
    only once. Request hooks are attached to every app instance.
    """
    global _metrics

    if _metrics is None:
        _metrics = PrometheusMetrics(app)
        _metrics.info("app_info", "World Clock Backend Application", version="1.0.0")

    app.before_request(_start_timer)
    app.after_request(_record_metrics)
