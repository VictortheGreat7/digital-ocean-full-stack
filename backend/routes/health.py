"""
Health & readiness endpoints.
"""

from __future__ import annotations

import logging

from flask import Blueprint, jsonify
from redis_cache import is_cache_ready
from refresh_loops import (
    _timezones_ready,
    _world_clocks_ready,
)

health_bp = Blueprint("health", __name__)
logger = logging.getLogger(__name__)


@health_bp.route("/health", methods=["GET"])
def health():
    """Liveness probe — always returns 200 if the process is up."""
    return jsonify({"status": "alive"}), 200


@health_bp.route("/ready", methods=["GET"])
def ready():
    """Readiness probe — returns 200 only if critical dependencies are reachable."""
    if (_world_clocks_ready.is_set() and _timezones_ready.is_set()) or is_cache_ready():
        return jsonify(
            {
                "status": "ready",
                "checks": {"cache": "ready"},
            }
        ), 200

    return jsonify(
        {
            "status": "not_ready",
            "checks": {"cache": "not_set"},
        }
    ), 503
