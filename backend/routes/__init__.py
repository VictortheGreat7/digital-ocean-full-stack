"""
Routes — ``__init__.py``

Registers all Blueprints with the app.
"""

from flask import Flask
from .time import time_bp
from .health import health_bp
from __future__ import annotations


def register_routes(app: Flask) -> None:
    """Attach every Blueprint to *app*."""
    app.register_blueprint(time_bp)
    app.register_blueprint(health_bp)
