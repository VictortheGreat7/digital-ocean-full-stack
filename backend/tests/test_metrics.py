"""Tests for Prometheus request instrumentation."""

from __future__ import annotations

from time import monotonic
from types import SimpleNamespace

import metrics
from flask import g


def test_start_timer_records_monotonic_time(app):
    with app.test_request_context("/time"):
        metrics._start_timer()

        assert isinstance(g.start_time, float)
        assert g.start_time <= monotonic()


def test_record_metrics_skips_excluded_paths(app, monkeypatch):
    published = []
    monkeypatch.setattr(
        metrics, "publish_request_observation", lambda obs: published.append(obs)
    )

    with app.test_request_context("/health"):
        g.start_time = monotonic()
        response = SimpleNamespace(status_code=200)
        assert metrics._record_metrics(response) is response

    assert published == []


def test_record_metrics_skips_when_timer_is_missing(app, monkeypatch):
    published = []
    monkeypatch.setattr(
        metrics, "publish_request_observation", lambda obs: published.append(obs)
    )

    with app.test_request_context("/time"):
        response = SimpleNamespace(status_code=200)
        assert metrics._record_metrics(response) is response

    assert published == []


def test_record_metrics_publishes_observation(app, monkeypatch):
    published = []
    enriched = []
    monkeypatch.setattr(metrics, "get_active_span", lambda: None)
    monkeypatch.setattr(
        metrics, "enrich_active_span", lambda *args, **kwargs: enriched.append(kwargs)
    )
    monkeypatch.setattr(
        metrics, "publish_request_observation", lambda obs: published.append(obs)
    )

    with app.test_request_context("/time?timezone=UTC"):
        g.start_time = monotonic() - 0.5
        metrics._record_metrics(SimpleNamespace(status_code=200))

    assert len(published) == 1
    observation = published[0]
    assert observation.path == "/time"
    assert observation.method == "GET"
    assert observation.status == 200
    assert observation.timezone == "UTC"
    assert observation.latency_ms >= 500
    assert enriched == [{"path": "/time", "method": "GET", "status": 200}]


def test_record_metrics_counts_error_responses(app, monkeypatch):
    monkeypatch.setattr(metrics, "get_active_span", lambda: None)
    monkeypatch.setattr(metrics, "enrich_active_span", lambda *args, **kwargs: None)
    monkeypatch.setattr(metrics, "publish_request_observation", lambda obs: None)

    error_counter = metrics.custom_request_errors.labels(
        method="GET", path="/time", status=500
    )
    before = error_counter._value.get()

    with app.test_request_context("/time"):
        g.start_time = monotonic()
        metrics._record_metrics(SimpleNamespace(status_code=500))

    assert error_counter._value.get() == before + 1


def test_init_metrics_is_idempotent(app, monkeypatch):
    monkeypatch.setattr(metrics, "_metrics", None)

    metrics.init_metrics(app)
    first = metrics._metrics
    metrics.init_metrics(app)

    assert metrics._metrics is first
    assert metrics._start_timer in app.before_request_funcs[None]
    assert metrics._record_metrics in app.after_request_funcs[None]
