"""
Database layer — connection pool + async request-log writer.

Call ``init_db(app)`` from the application factory and ``shutdown_db()``
at exit to drain the queue gracefully.
"""

import logging
from __future__ import annotations

import atexit
from time import monotonic
from threading import Thread
from queue import Queue, Full, Empty

from psycopg2 import pool
from psycopg2.extras import execute_values
from psycogreen.gevent import patch_psycopg

from opentelemetry import context
from opentelemetry.trace import SpanContext

from config import DB_CONFIG, BATCH_SIZE, BATCH_FLUSH_SECONDS

# patch_psycopg() should be called before any psycopg2 connections are created. It monkey-patches psycopg2 to make it cooperative with gevent's green threads to prevent blocking of the server during db operations.
patch_psycopg()

logger = logging.getLogger(__name__)

# Connection pool
_pool: pool.ThreadedConnectionPool | None = None

# Async request-log queue
_log_queue: Queue = Queue(maxsize=5000)

# Sentinel value to signal worker thread shutdown
_SENTINEL = object() 

# Worker thread and shutdown flags
_db_thread: Thread | None = None
_shutdown_registered = False
_shutdown_called = False

_DROP_LOG_EVERY_SECONDS = 5.0
_dropped_since_last_log = 0
_last_drop_log_at = 0.0


def enqueue_request_log(
    *,
    path: str,
    method: str,
    status: int,
    latency_ms: int,
    timezone: str,
    trace_id: str | None,
    span_context: SpanContext | None,
) -> None:
    """Put a request-log record on the queue (non-blocking)."""
    global _dropped_since_last_log, _last_drop_log_at

    ctx = context.get_current()
    item = (
        (path, method, status, latency_ms, timezone, trace_id),
        span_context,
        ctx,
    )

    try:
        _log_queue.put_nowait(item)
    except Full:
        _dropped_since_last_log += 1
        now = monotonic()
        if now - _last_drop_log_at > _DROP_LOG_EVERY_SECONDS:
            logger.warning(
                "Request-log queue full: dropped=%s in last %.1fs (queue_max=%s)",
                _dropped_since_last_log,
                _DROP_LOG_EVERY_SECONDS,
                _log_queue.maxsize,
            )
            _dropped_since_last_log = 0
            _last_drop_log_at = now


def get_connection():
    """Get a connection from the pool (caller must return it via ``put_connection``)."""
    if _pool is None:
        raise RuntimeError("Database pool not initialised — call init_db() first")
    return _pool.getconn()


def put_connection(conn) -> None:
    """Return a connection to the pool."""
    if _pool is not None:
        _pool.putconn(conn)


def _flush_batch(rows: list[tuple]) -> None:
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            execute_values(
                cur,
                """
                INSERT INTO requests
                    (path, method, status, latency_ms, timezone, trace_id)
                VALUES %s
                """,
                rows,
                page_size=200,
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


def _db_worker() -> None:
    """Background thread that drains *_log_queue* into the ``requests`` table."""
    from telemetry import tracer # deferred to avoid circular import

    while True:
        item = _log_queue.get()
        if item is _SENTINEL:
            break

        batch: list[tuple] = [item[0]]  # row payload only
        deadline = monotonic() + BATCH_FLUSH_SECONDS

        while len(batch) < BATCH_SIZE:
            remaining = deadline - monotonic()
            if remaining <= 0:
                break
            try:
                nxt = _log_queue.get(timeout=remaining)
                if nxt is _SENTINEL:
                    _flush_batch(batch)
                    return
                batch.append(nxt[0])
            except Empty:
                break

        with tracer.start_as_current_span("db.insert_request_log_batch") as span:
            span.set_attribute("db.operation", "insert")
            span.set_attribute("db.table", "requests")
            span.set_attribute("db.batch_size", len(batch))
            _flush_batch(batch)


def shutdown_db() -> None:
    """Drain the queue and close the pool.  Registered via ``atexit``."""
    global _shutdown_called, _pool, _db_thread

    if _shutdown_called:
        return
    _shutdown_called = True

    # Stop worker thread
    if _db_thread is not None and _db_thread.is_alive():
        _log_queue.put(_SENTINEL)
        _db_thread.join(timeout=5)

    # Close DB connection pool
    if _pool is not None:
        _pool.closeall()
        _pool = None
    logger.info("DB pool closed")

def init_db(app=None) -> None:
    """Create the threaded connection pool."""
    global _pool, _db_thread, _shutdown_registered

    if _pool is None:
        try:
            _pool = pool.ThreadedConnectionPool(
                minconn=1,
                maxconn=10,
                **DB_CONFIG,
            )
            logger.info("Database connection pool created")
        except Exception as exc:
            logger.error("Failed to create DB pool: %s", exc)
    else:
        logger.debug("DB pool already initialized")
    
    if _db_thread is None or not _db_thread.is_alive():
        _db_thread = Thread(target=_db_worker, daemon=True, name="db-log-writer")
        _db_thread.start()
        logger.info("DB log worker thread started")
    else:
        logger.debug("DB log worker thread already running")
    
    if not _shutdown_registered:
        atexit.register(shutdown_db)
        _shutdown_registered = True
        logger.debug("DB shutdown registered with atexit")
