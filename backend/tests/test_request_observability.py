"""Tests for request observation helpers."""

from __future__ import annotations

import request_observability
from flask import request
from opentelemetry.trace import SpanContext


class FakeSpan:
    def __init__(self, span_context: SpanContext, *, recording: bool = True) -> None:
        self._span_context = span_context
        self.recording = recording
        self.attributes: dict[str, object] = {}

    def get_span_context(self) -> SpanContext:
        return self._span_context

    def is_recording(self) -> bool:
        return self.recording

    def set_attribute(self, key: str, value: object) -> None:
        self.attributes[key] = value


def test_should_observe_request_excludes_configured_paths():
    excluded = {"/metrics", "/health"}

    assert request_observability.should_observe_request("/time", excluded) is True
    assert request_observability.should_observe_request("/metrics", excluded) is False


def test_get_observed_path_prefers_matched_route(app):
    with app.test_request_context("/time?timezone=UTC"):
        assert request_observability.get_observed_path(
            request
        ) == "/time"


def test_build_request_observation_without_span(app):
    with app.test_request_context("/time?timezone=Asia/Tokyo"):
        observation = request_observability.build_request_observation(
            request,
            duration_seconds=0.1234,
            status_code=200,
            path="/time",
            span=None,
        )

    assert observation.path == "/time"
    assert observation.method == "GET"
    assert observation.status == 200
    assert observation.latency_ms == 123
    assert observation.timezone == "Asia/Tokyo"
    assert observation.trace_id is None
    assert observation.span_context is None


def test_build_request_observation_includes_trace_id(app):
    span_context = SpanContext(
        trace_id=0x1234567890ABCDEF1234567890ABCDEF,
        span_id=0x1234567890ABCDEF,
        is_remote=False,
    )
    span = FakeSpan(span_context)

    with app.test_request_context("/time?timezone=UTC"):
        observation = request_observability.build_request_observation(
            request,
            duration_seconds=1.5,
            status_code=500,
            path="/time",
            span=span,
        )

    assert observation.trace_id == "1234567890abcdef1234567890abcdef"
    assert observation.span_context is span_context
    assert observation.latency_ms == 1500


def test_build_request_observation_only_records_timezone_for_time_route(app):
    with app.test_request_context("/world-clocks?timezone=Asia/Tokyo"):
        observation = request_observability.build_request_observation(
            request,
            duration_seconds=0.01,
            status_code=200,
            path="/world-clocks",
            span=None,
        )

    assert observation.timezone is None


def test_publish_request_observation_enqueues_log(monkeypatch):
    captured = {}
    monkeypatch.setattr(
        request_observability,
        "enqueue_request_log",
        lambda **kwargs: captured.update(kwargs),
    )
    observation = request_observability.RequestObservation(
        path="/time",
        method="GET",
        status=200,
        latency_ms=5,
        timezone="UTC",
        trace_id=None,
        span_context=None,
    )

    request_observability.publish_request_observation(observation)

    assert captured == {
        "path": "/time",
        "method": "GET",
        "status": 200,
        "latency_ms": 5,
        "timezone": "UTC",
        "trace_id": None,
        "span_context": None,
    }


def test_enrich_active_span_sets_http_attributes():
    span = FakeSpan(
        SpanContext(trace_id=1, span_id=2, is_remote=False), recording=True
    )

    request_observability.enrich_active_span(
        span, path="/time", method="GET", status=200
    )

    assert span.attributes == {
        "http.route": "/time",
        "http.method": "GET",
        "http.status_code": 200,
    }


def test_enrich_active_span_skips_non_recording_span():
    span = FakeSpan(
        SpanContext(trace_id=1, span_id=2, is_remote=False), recording=False
    )

    request_observability.enrich_active_span(
        span, path="/time", method="GET", status=200
    )

    assert span.attributes == {}


def test_enrich_active_span_accepts_none():
    request_observability.enrich_active_span(
        None, path="/time", method="GET", status=200
    )


def test_get_active_span_returns_a_span():
    assert request_observability.get_active_span() is not None
