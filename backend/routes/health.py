"""
Health & readiness endpoints.
"""

from __future__ import annotations

import logging
from flask import Blueprint, jsonify
from psycopg2 import OperationalError
from db import get_health_connection, put_health_connection


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
    conn_healthy = True
    try:
        conn = get_health_connection()
        with conn.cursor() as cur:
            cur.execute("SELECT 1")

        return jsonify(
            {
                "status": "ready",
                "checks": {"database": "up"},
            }
        ), 200

    except OperationalError as exc:
        conn_healthy = False  # connection is likely unusable
        logger.exception("Database connection failed: %s", exc)

        return jsonify(
            {
                "status": "not_ready",
                "checks": {"database": "not_reachable"},
            }
        ), 503

    except Exception as exc:
        logger.exception("Readiness check failed: %s", exc)
        return jsonify(
            {
                "status": "not_ready",
                "checks": {"database": "not_reachable"},
            }
        ), 503

    finally:
        if conn is not None:
            put_health_connection(conn, close=not conn_healthy)
