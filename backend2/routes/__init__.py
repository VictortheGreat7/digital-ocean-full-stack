"""
Routes — ``__init__.py``

Registers all Blueprints with the app.
"""

from __future__ import annotations

from flask import Flask

from .time import time_bp
from .health import health_bp
# from .traces import traces_bp


def register_routes(app: Flask) -> None:
    """Attach every Blueprint to *app*."""
    app.register_blueprint(time_bp)
    app.register_blueprint(health_bp)
    # app.register_blueprint(traces_bp)
