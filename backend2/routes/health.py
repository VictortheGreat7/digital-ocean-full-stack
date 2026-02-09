"""
Health & readiness endpoints.
"""

from __future__ import annotations

from flask import Blueprint, jsonify

from db import get_connection, put_connection

health_bp = Blueprint("health", __name__)


@health_bp.route("/health", methods=["GET"])
def health():
    """Liveness probe — always returns 200 if the process is up."""
    return jsonify({"status": "alive"}), 200


@health_bp.route("/ready", methods=["GET"])
def ready():
    """Readiness probe — verifies DB connectivity with a lightweight query."""
    try:
        conn = get_connection()
        try:
            with conn.cursor() as cur:
                cur.execute("SELECT 1")
            return jsonify({"status": "ready", "database": "up"}), 200
        finally:
            put_connection(conn)
    except Exception as exc:
        return jsonify({
            "status": "not ready",
            "database": f"unhealthy: {exc}",
            "error": str(exc),
        }), 503
