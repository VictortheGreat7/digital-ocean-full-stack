"""
Application factory for the Kronos World-Clock backend.

Usage:
    from app import create_app
    app = create_app()
"""

from __future__ import annotations

from flask import Flask
from flask_cors import CORS

from db import init_db
from metrics import init_metrics
from routes import register_routes
from telemetry import init_telemetry

from cache import init_cache

from ddtrace.runtime import RuntimeMetrics
from ddtrace.profiling import Profiler

_runtime_metrics_enabled = False
_profiler_enabled = False
prof = Profiler(
    env="dev",
    service="kronos-backend",
    version="1.0.0"
)

def create_app() -> Flask:
    """Build and return a fully configured Flask application."""
    app = Flask(__name__)
    CORS(app)

    global _runtime_metrics_enabled, _profiler_enabled

    # Enable Datadog runtime metrics (CPU, memory, etc.)
    if not _runtime_metrics_enabled:
        RuntimeMetrics.enable()
        _runtime_metrics_enabled = True

    # Enable Datadog profiler (CPU and wall-time)
    if not _profiler_enabled:
        prof.start()
        _profiler_enabled = True

    # Observability
    init_telemetry(app)
    init_metrics(app)

    # Cache
    init_cache(app)

    # Database
    init_db(app)

    # Route blueprints
    register_routes(app)

    return app


# ── Entrypoint ─────────────────────────────────────────────────────────
if __name__ == "__main__":
    application = create_app()
    application.run(host="0.0.0.0", port=5000)
