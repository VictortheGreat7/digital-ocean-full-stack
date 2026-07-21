"""
Database layer — connection pool and connection lifecycle.

Call ``init_db(app)`` from the application factory and ``shutdown_db()``
at exit to close the pool gracefully.
"""

from __future__ import annotations

import atexit
import logging
from threading import Thread

from psycopg2 import pool
from psycogreen.gevent import patch_psycopg

from config import DB_CONFIG

# patch_psycopg() should be called before any psycopg2 connections are created.
# It monkey-patches psycopg2 to make it cooperative with gevent's green threads
# to prevent blocking of the server during db operations.
patch_psycopg()

logger = logging.getLogger(__name__)

# Connection pool
_pool: pool.ThreadedConnectionPool | None = None

# Worker thread and shutdown flags
_shutdown_registered = False
_shutdown_called = False


def get_connection():
    """Get a connection from the pool (caller must return it via ``put_connection``)."""
    if _pool is None:
        raise RuntimeError("Database pool not initialised — call init_db() first")
    return _pool.getconn()


def put_connection(conn, close=None) -> None:
    """Return a connection to the pool."""
    if _pool is not None:
        _pool.putconn(conn, close=close)


def shutdown_db() -> None:
    """Close the pool. Registered via ``atexit``."""
    global _shutdown_called, _pool

    if _shutdown_called:
        return
    _shutdown_called = True

    # Close DB connection pool
    if _pool is not None:
        _pool.closeall()
        _pool = None
    logger.info("DB pool closed")


def init_db(app=None) -> None:
    """Create the threaded connection pool."""
    global _pool, _shutdown_registered

    if _pool is None:
        try:
            _pool = pool.ThreadedConnectionPool(
                minconn=1,
                maxconn=3,
                **DB_CONFIG,
            )
            logger.info("Database connection pool created")
        except Exception as exc:
            logger.error("Failed to create DB pool: %s", exc)
            raise
    else:
        logger.debug("DB pool already initialized")

    if not _shutdown_registered:
        atexit.register(shutdown_db)
        _shutdown_registered = True
        logger.debug("DB shutdown registered with atexit")
