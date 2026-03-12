"""
Health & readiness endpoints.
"""

from __future__ import annotations

from flask import Blueprint, jsonify

import logging

health_bp = Blueprint("health", __name__)

logger = logging.getLogger(__name__)

@health_bp.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "alive"}), 200


@health_bp.route("/ready", methods=["GET"])
def ready():
    return jsonify({"status": "ready"}), 200
