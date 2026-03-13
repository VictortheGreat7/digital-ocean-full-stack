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
from clock_worker import init_clock_updater


def create_app() -> Flask:
    """Build and return a fully configured Flask application."""
    app = Flask(__name__)
    CORS(app)

    # Observability
    init_telemetry(app)
    init_metrics(app)

    # Cache
    init_cache(app)

    # Clock Background Worker
    init_clock_updater(app)

    # Database
    init_db(app)

    # Route blueprints
    register_routes(app)

    return app


# ── Entrypoint ─────────────────────────────────────────────────────────
if __name__ == "__main__":
    application = create_app()
    application.run(host="0.0.0.0", port=5000)
