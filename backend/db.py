"""
Database layer — connection pool and connection lifecycle.

Call ``init_db(app)`` from the application factory and ``shutdown_db()``
at exit to close the pool gracefully.
"""

from __future__ import annotations

import atexit
import logging

from psycogreen.gevent import patch_psycopg
from psycopg2 import pool

from config import DB_CONFIG

# patch_psycopg() should be called before any psycopg2 connections are created.
# It monkey-patches psycopg2 to make it cooperative with gevent's green threads
# to prevent blocking of the server during db operations.
patch_psycopg()

logger = logging.getLogger(__name__)

# Connection pools
_app_pool: pool.ThreadedConnectionPool | None = None
_health_pool: pool.ThreadedConnectionPool | None = None

# Worker thread and shutdown flags
_shutdown_registered = False
_shutdown_called = False


def get_app_connection():
    """Get a connection from the app pool (caller must return it via ``put_app_connection``)."""
    if _app_pool is None:
        raise RuntimeError("Database app pool not initialised — call init_db() first")
    return _app_pool.getconn()


def put_app_connection(conn, close=None) -> None:
    """Return a connection to the app pool."""
    if _app_pool is not None:
        _app_pool.putconn(conn, close=close)


def get_health_connection():
    """Get a connection from the health-check pool (caller must return it via ``put_health_connection``)."""
    if _health_pool is None:
        raise RuntimeError("Database health pool not initialised — call init_db() first")
    return _health_pool.getconn()


def put_health_connection(conn, close=None) -> None:
    """Return a connection to the health-check pool."""
    if _health_pool is not None:
        _health_pool.putconn(conn, close=close)


def shutdown_db() -> None:
    """Close the pools. Registered via ``atexit``."""
    global _shutdown_called, _app_pool, _health_pool

    if _shutdown_called:
        return
    _shutdown_called = True

    # Close app pool
    if _app_pool is not None:
        _app_pool.closeall()
        _app_pool = None

    # Close health pool
    if _health_pool is not None:
        _health_pool.closeall()
        _health_pool = None

    logger.info("DB pools closed")


def init_db(app=None) -> None:
    """Create the threaded connection pools."""
    global _app_pool, _health_pool, _shutdown_registered

    if _app_pool is None:
        try:
            _app_pool = pool.ThreadedConnectionPool(
                minconn=1,
                maxconn=2,
                **DB_CONFIG,
            )
            logger.info("App connection pool created")
        except Exception as exc:
            logger.error("Failed to create app DB pool: %s", exc)
            raise
    else:
        logger.debug("App DB pool already initialized")

    if _health_pool is None:
        try:
            _health_pool = pool.ThreadedConnectionPool(
                minconn=1,
                maxconn=1,
                **DB_CONFIG,
            )
            logger.info("Health connection pool created")
        except Exception as exc:
            logger.error("Failed to create health DB pool: %s", exc)
            raise

    if not _shutdown_registered:
        atexit.register(shutdown_db)
        _shutdown_registered = True
        logger.debug("DB shutdown registered with atexit")
