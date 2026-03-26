"""
Health & readiness endpoints.
"""

from __future__ import annotations

from flask import Blueprint, jsonify

import logging

from db import get_connection, put_connection, init_db

health_bp = Blueprint("health", __name__)

logger = logging.getLogger(__name__)

@health_bp.route("/health", methods=["GET"])
def health():
    """Liveness probe — always returns 200 if the process is up."""
    return jsonify({"status": "alive"}), 200


@health_bp.route("/ready", methods=["GET"])
def ready():
    """Readiness probe — returns 200 only if critical dependencies are reachable."""
    conn = None
    try:
        conn = get_connection()
        with conn.cursor() as cur:
            cur.execute("SELECT 1")

        return jsonify({
            "status": "ready",
            "checks": {"database": "up"},
        }), 200

    except Exception as exc:
        logger.exception("Readiness check failed: %s", exc)
        return jsonify({
            "status": "not_ready",
            "checks": {"database": "not_reachable"},
        }), 503

    finally:
        if conn is not None:
            put_connection(conn)
