"""
Async request-log writer.
"""

from __future__ import annotations

import atexit
import logging
from queue import Empty, Full, Queue
from threading import Thread
from time import monotonic

from opentelemetry import context
from opentelemetry.trace import SpanContext
from psycopg2 import InterfaceError, OperationalError
from psycopg2.extras import execute_values

from config import BATCH_FLUSH_SECONDS, BATCH_SIZE
from db import get_writer_connection, put_writer_connection

logger = logging.getLogger(__name__)

_log_queue: Queue = Queue(maxsize=5000)
_SENTINEL = object()
_writer_thread: Thread | None = None
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
    timezone: str | None,
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


def _flush_batch(rows: list[tuple]) -> None:
    """Insert a batch of request logs using a dedicated writer-pool connection."""
    conn = get_writer_connection()
    conn_healthy = True
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
                page_size=50,
            )
        conn.commit()
    except (OperationalError, InterfaceError) as exc:
        conn_healthy = False
        logger.error("Database connection error: %s", exc)

        # One retry with a fresh connection from the pool
        try:
            put_writer_connection(conn, close=not conn_healthy)
            conn = get_writer_connection()
            conn_healthy = True
            with conn.cursor() as cur:
                execute_values(
                    cur,
                    """
                    INSERT INTO requests
                        (path, method, status, latency_ms, timezone, trace_id)
                    VALUES %s
                    """,
                    rows,
                    page_size=50,
                )
            conn.commit()
            logger.info("Writer batch re-inserted after reconnect")
        except Exception as retry_exc:
            conn_healthy = False
            logger.error("Writer retry failed: %s", retry_exc)

    except Exception as exc:
        logger.error("DB batch write error: %s", exc)
    finally:
        put_writer_connection(conn, close=not conn_healthy)


def _writer_loop() -> None:
    from telemetry import tracer  # deferred to avoid circular import

    while True:
        item = _log_queue.get()
        if item is _SENTINEL:
            break

        batch: list[tuple] = [item[0]]
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


def shutdown_request_log_writer() -> None:
    """Drain the queue and stop the worker thread."""
    global _shutdown_called

    if _shutdown_called:
        return
    _shutdown_called = True

    if _writer_thread is not None and _writer_thread.is_alive():
        _log_queue.put(_SENTINEL)
        _writer_thread.join(timeout=5)


def init_request_log_writer() -> None:
    """Start the request-log writer thread once the database pool is ready."""
    global _writer_thread, _shutdown_registered

    if _writer_thread is None or not _writer_thread.is_alive():
        _writer_thread = Thread(target=_writer_loop, daemon=True, name="db-log-writer")
        _writer_thread.start()
        logger.info("DB log worker thread started")
    else:
        logger.debug("DB log worker thread already running")

    if not _shutdown_registered:
        atexit.register(shutdown_request_log_writer)
        _shutdown_registered = True
        logger.debug("DB log worker shutdown registered with atexit")
