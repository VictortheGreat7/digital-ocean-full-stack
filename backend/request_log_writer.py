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

from config import BATCH_FLUSH_SECONDS, BATCH_SIZE, DB_CONFIG
from psycopg2 import InterfaceError, OperationalError, connect
from psycopg2.extras import execute_values

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


def _create_writer_connection():
    """Open a raw persistent connection for the log writer."""
    return connect(**DB_CONFIG)


def _flush_batch(rows: list[tuple], conn):
    """
    Insert a batch of request logs using a persistent connection.

    Returns the (possibly replaced) connection so the caller can keep
    a valid handle after a reconnect.
    """
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

        try:
            conn.rollback()
        except Exception:
            pass

        # Attempt one reconnect + retry
        try:
            logger.info("Writer reconnecting to database after %s", exc)
            conn.close()
        except Exception:
            pass

        try:
            conn = _create_writer_connection()
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
            logger.error("Writer retry failed: %s", retry_exc)
            try:
                conn.rollback()
            except Exception:
                pass
    except Exception as exc:
        logger.error("DB batch write error: %s", exc)
        try:
            conn.rollback()
        except Exception:
            pass

    return conn


def _writer_loop() -> None:
    from telemetry import tracer  # deferred to avoid circular import

    conn = None
    try:
        conn = _create_writer_connection()
        logger.info("DB log writer persistent connection established")
    except Exception as exc:
        logger.error("Could not establish writer DB connection: %s", exc)

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
                    if conn is not None:
                        conn = _flush_batch(batch, conn)
                    return
                batch.append(nxt[0])
            except Empty:
                break

        if conn is None:
            try:
                conn = _create_writer_connection()
                logger.info("DB log writer persistent connection re-established")
            except Exception as exc:
                logger.error("Writer still cannot connect: %s; dropping batch", exc)
                continue

        with tracer.start_as_current_span("db.insert_request_log_batch") as span:
            span.set_attribute("db.operation", "insert")
            span.set_attribute("db.table", "requests")
            span.set_attribute("db.batch_size", len(batch))
            conn = _flush_batch(batch, conn)

    if conn is not None:
        try:
            conn.close()
        except Exception:
            pass


def shutdown_request_log_writer() -> None:
    """Drain the queue and stop the worker thread."""
    global _shutdown_called, _writer_thread

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
