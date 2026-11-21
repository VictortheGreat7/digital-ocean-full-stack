"""
Application factory for the Kronos World-Clock backend.

Usage:
    from app import create_app
    app = create_app()
"""

from __future__ import annotations

from collections.abc import Mapping

import refresh_loops
from config import (
    CACHE_ENABLED,
    DB_ENABLED,
    METRICS_ENABLED,
    REFRESH_LOOPS_ENABLED,
    REQUEST_LOG_WRITER_ENABLED,
    TELEMETRY_ENABLED,
)
from flask import Flask
from flask_cors import CORS
from metrics import init_metrics
from redis_cache import init_cache
from routes import register_routes

# Defaults mirror the production configuration. They can be overridden per
# application (most importantly by tests) via ``create_app({...})``.
DEFAULT_CONFIG: dict[str, object] = {
    "ENABLE_TELEMETRY": TELEMETRY_ENABLED,
    "ENABLE_METRICS": METRICS_ENABLED,
    "ENABLE_CACHE": CACHE_ENABLED,
    "ENABLE_REFRESH_LOOPS": REFRESH_LOOPS_ENABLED,
    "ENABLE_DB": DB_ENABLED,
    "ENABLE_REQUEST_LOG_WRITER": REQUEST_LOG_WRITER_ENABLED,
}


def create_app(config: Mapping[str, object] | None = None) -> Flask:
    """Build and return a fully configured Flask application.

    *config* is merged into ``app.config`` after the defaults, so callers can
    disable external dependencies (Redis, OpenTelemetry, background threads,
    …) without touching module-level state.
    """
    app = Flask(__name__)
    app.config.from_mapping(DEFAULT_CONFIG)
    if config is not None:
        app.config.update(config)

    CORS(app)

    # Observability
    if app.config["ENABLE_TELEMETRY"]:
        from telemetry import init_telemetry

        init_telemetry(app)

    if app.config["ENABLE_METRICS"]:
        init_metrics(app)

    # Cache
    init_cache(app, enabled=bool(app.config["ENABLE_CACHE"]))

    # Database
    if app.config["ENABLE_DB"]:
        from db import init_db

        init_db(app)

    # Request logs
    if app.config["ENABLE_REQUEST_LOG_WRITER"]:
        from request_log_writer import init_request_log_writer

        init_request_log_writer()

    # Route blueprints
    register_routes(app)

    # Background cache refresh loops
    if app.config["ENABLE_REFRESH_LOOPS"]:
        refresh_loops.start_refresh_loops()

    return app


# ── Entrypoint ─────────────────────────────────────────────────────────
if __name__ == "__main__":
    application = create_app()
    application.run(host="0.0.0.0", port=5000)
