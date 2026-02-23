"""
Database layer — connection pool + async request-log writer.

Call ``init_db(app)`` from the application factory and ``shutdown_db()``
at exit to drain the queue gracefully.
"""

from __future__ import annotations

import atexit
import logging
from queue import Queue, Empty, Full
from threading import Thread
from typing import Any

import psycopg2
from psycopg2 import pool
from psycopg2.extras import execute_values
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
# Bounded queue to prevent memory leaks during heavy load
_log_queue: Queue = Queue(maxsize=5000)
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
    item = (
        (path, method, status, latency_ms, timezone, city, trace_id),
        span_context,
        ctx,
    )
    
    try:
        # Use put_nowait so we don't block the Gunicorn worker thread.
        _log_queue.put_nowait(item)
    except Full:
        # DROP THE LOG: The database worker is overwhelmed.
        # Silently discard to protect application memory.
        pass


def _db_worker() -> None:
    """Background thread that drains *_log_queue* in batches."""
    from telemetry import tracer  # deferred to avoid circular import

    BATCH_SIZE = 100

    while True:
        batch_records = []
        exit_signaled = False

        # 1. Collect up to BATCH_SIZE items from the queue
        while len(batch_records) < BATCH_SIZE:
            try:
                # Wait up to 1 second for new logs to avoid a tight CPU loop
                item = _log_queue.get(timeout=1.0)
                
                if item is _SENTINEL:
                    exit_signaled = True
                    break
                    
                record, span_ctx, ctx = item
                batch_records.append(record)
                
            except Empty:
                # 1 second passed with no new items; break to flush what we have
                break

        # 2. If we have records, batch-insert them
        if batch_records:
            # We trace the batch insert as a single background span
            with tracer.start_as_current_span("db.batch_insert_request_logs") as span:
                span.set_attribute("db.operation", "insert")
                span.set_attribute("db.table", "requests")
                span.set_attribute("db.batch_size", len(batch_records))

                try:
                    conn = get_connection()
                    try:
                        with conn.cursor() as cur:
                            # Use execute_values for massive performance gains
                            execute_values(
                                cur,
                                """
                                INSERT INTO requests
                                    (path, method, status, latency_ms, timezone, city, trace_id)
                                VALUES %s
                                """,
                                batch_records
                            )
                        conn.commit()
                    except Exception as exc:
                        logger.error("DB batch write error: %s", exc)
                        try:
                            conn.rollback()
                        except Exception:
                            pass
                    finally:
                        put_connection(conn)
                except Exception as exc:
                    # Pool may be unavailable
                    logger.error("DB worker error (pool): %s", exc)
                    
        # 3. Exit gracefully if sentinel was received
        if exit_signaled:
            break


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