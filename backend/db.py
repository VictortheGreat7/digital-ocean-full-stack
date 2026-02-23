"""
Database layer — connection pool + async request-log writer.

Call ``init_db(app)`` from the application factory and ``shutdown_db()``
at exit to drain the queue gracefully.
"""

from __future__ import annotations

import atexit
import logging
from queue import Queue, Empty
from threading import Thread
from typing import Any

import psycopg2
from psycopg2 import pool
from opentelemetry import trace, context
from opentelemetry.trace import format_trace_id, SpanContext

from config import DB_CONFIG

logger = logging.getLogger(__name__)

# ── Connection pool ────────────────────────────────────────────────────
_pool: pool.ThreadedConnectionPool | None = None


def get_connection():
    """Get a connection from the pool (caller must return it via ``put_connection``)."""
    if _pool is None:
        raise RuntimeError("Database pool not initialised — call init_db() first")
    return _pool.getconn()


def put_connection(conn) -> None:
    """Return a connection to the pool."""
    if _pool is not None:
        _pool.putconn(conn)


def init_db(app=None) -> None:
    """Create the threaded connection pool."""
    global _pool
    try:
        _pool = pool.ThreadedConnectionPool(
            minconn=1,
            maxconn=5,
            **DB_CONFIG,
        )
        logger.info("Database connection pool created")
    except Exception as exc:
        logger.error("Failed to create DB pool: %s", exc)
        # The app can still start — the /ready check will report unhealthy.


# ── Async request-log queue + worker ───────────────────────────────────
_log_queue: Queue = Queue(maxsize=5000)  # unbounded would be risky if the DB is down, but we don't want to drop logs either
_SENTINEL = object()  # signals the worker to exit


def enqueue_request_log(
    *,
    path: str,
    method: str,
    status: int,
    latency_ms: int,
    timezone: str,
    city: str,
    trace_id: str | None,
    span_context: SpanContext | None,
) -> None:
    """Put a request-log record on the queue (non-blocking)."""
    ctx = context.get_current()
    _log_queue.put((
        (path, method, status, latency_ms, timezone, city, trace_id),
        span_context,
        ctx,
    ))


def _db_worker() -> None:
    """Background thread that drains *_log_queue* into the ``requests`` table."""
    from telemetry import tracer  # deferred to avoid circular import

    while True:
        item = _log_queue.get()
        if item is _SENTINEL:
            break

        record, span_ctx, ctx = item

        # Attach parent context if available
        token = context.attach(ctx) if ctx else None

        try:
            parent_span = trace.NonRecordingSpan(span_ctx) if span_ctx else None
            parent_ctx = (
                trace.set_span_in_context(parent_span)
                if parent_span
                else None
            )
            with tracer.start_as_current_span("db.insert_request_log", context=parent_ctx) as span:
                span.set_attribute("db.operation", "insert")
                span.set_attribute("db.table", "requests")

                conn = get_connection()
                try:
                    with conn.cursor() as cur:
                        cur.execute(
                            """
                            INSERT INTO requests
                                (path, method, status, latency_ms, timezone, city, trace_id)
                            VALUES (%s, %s, %s, %s, %s, %s, %s)
                            """,
                            record,
                        )
                    conn.commit()
                except Exception as exc:
                    logger.error("DB write error: %s", exc)
                    try:
                        conn.rollback()
                    except Exception:
                        pass
                finally:
                    put_connection(conn)
        except Exception as exc:
            # Pool may be unavailable — log and move on
            logger.error("DB worker error (pool): %s", exc)
        finally:
            if token is not None:
                context.detach(token)


_db_thread = Thread(target=_db_worker, daemon=True, name="db-log-writer")
_db_thread.start()


def shutdown_db() -> None:
    """Drain the queue and close the pool.  Registered via ``atexit``."""
    _log_queue.put(_SENTINEL)
    _db_thread.join(timeout=5)
    if _pool is not None:
        _pool.closeall()
    logger.info("DB pool closed")


atexit.register(shutdown_db)
