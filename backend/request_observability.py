"""
Request observation helpers for metrics, tracing, and request logging.
"""

from __future__ import annotations

from dataclasses import dataclass

from flask import Request
from opentelemetry import trace
from opentelemetry.trace import Span, SpanContext, format_trace_id

from request_log_writer import enqueue_request_log


@dataclass(frozen=True, slots=True)
class RequestObservation:
    path: str
    method: str
    status: int
    latency_ms: int
    timezone: str | None
    trace_id: str | None
    span_context: SpanContext | None


def should_observe_request(path: str, excluded_paths: set[str]) -> bool:
    return path not in excluded_paths


def get_observed_path(request: Request) -> str:
    return request.url_rule.rule if request.url_rule else request.path


def build_request_observation(
    request: Request,
    *,
    duration_seconds: float,
    status_code: int,
    path: str,
    span: Span | None,
) -> RequestObservation:
    span_context = span.get_span_context() if span else None
    has_valid_span = bool(span_context and span_context.is_valid)

    return RequestObservation(
        path=path,
        method=request.method,
        status=status_code,
        latency_ms=int(duration_seconds * 1000),
        timezone=request.args.get("timezone") if path == "/time" else None,
        trace_id=format_trace_id(span_context.trace_id) if has_valid_span else None,
        span_context=span_context,
    )


def publish_request_observation(observation: RequestObservation) -> None:
    enqueue_request_log(
        path=observation.path,
        method=observation.method,
        status=observation.status,
        latency_ms=observation.latency_ms,
        timezone=observation.timezone,
        trace_id=observation.trace_id,
        span_context=observation.span_context,
    )


def enrich_active_span(
    span: Span | None, *, path: str, method: str, status: int
) -> None:
    if span and span.is_recording():
        span.set_attribute("http.route", path)
        span.set_attribute("http.method", method)
        span.set_attribute("http.status_code", status)


def get_active_span() -> Span | None:
    span = trace.get_current_span()
    return span if span else None
