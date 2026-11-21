"""
Database layer — connection pool and connection lifecycle.

Call ``init_db(app)`` from the application factory and ``shutdown_db()``
at exit to close the pool gracefully.
"""

from __future__ import annotations

import atexit
import logging

from config import DB_CONFIG
from psycopg2 import pool

logger = logging.getLogger(__name__)

# Connection pools
_writer_pool: pool.ThreadedConnectionPool | None = None

# Worker thread and shutdown flags
_shutdown_registered = False
_shutdown_called = False


def get_writer_connection():
    """Get a connection from the writer pool (caller must return it via ``put_writer_connection``)."""
    if _writer_pool is None:
        raise RuntimeError("Database writer pool not initialised — call init_db() first")
    return _writer_pool.getconn()


def put_writer_connection(conn, close=None) -> None:
    """Return a connection to the writer pool."""
    if _writer_pool is not None:
        _writer_pool.putconn(conn, close=close)


def shutdown_db() -> None:
    """Close the pools. Registered via ``atexit``."""
    global _shutdown_called, _writer_pool

    if _shutdown_called:
        return
    _shutdown_called = True

    # Close writer pool
    if _writer_pool is not None:
        _writer_pool.closeall()
        _writer_pool = None

    logger.info("DB pools closed")


def init_db(app=None, *, pool_factory=None) -> None:
    """Create the threaded connection pools.

    *pool_factory* can be supplied by tests to avoid opening real database
    connections.
    """
    global _writer_pool, _shutdown_registered

    if _writer_pool is None:
        # patch_psycopg() must be called before any psycopg2 connections are
        # created. It monkey-patches psycopg2 to make it cooperative with
        # gevent's green threads and prevent blocking during db operations.
        from psycogreen.gevent import patch_psycopg

        patch_psycopg()

        factory = pool_factory or pool.ThreadedConnectionPool
        try:
            _writer_pool = factory(
                minconn=1,
                maxconn=2,
                **DB_CONFIG,
            )
            logger.info("Writer connection pool created")
        except Exception as exc:
            logger.error("Failed to create writer DB pool: %s", exc)
            raise

    if not _shutdown_registered:
        atexit.register(shutdown_db)
        _shutdown_registered = True
        logger.debug("DB shutdown registered with atexit")
