"""Tests for the database pool lifecycle helpers."""

from __future__ import annotations

from types import SimpleNamespace

import db
import pytest
from config import DB_CONFIG


class FakePool:
    def __init__(self, **kwargs) -> None:
        self.kwargs = kwargs
        self.closed = False
        self.put_calls: list[tuple] = []

    def getconn(self):
        return "connection"

    def putconn(self, conn, close=None):
        self.put_calls.append((conn, close))

    def closeall(self):
        self.closed = True


def test_get_writer_connection_requires_pool():
    with pytest.raises(RuntimeError, match="init_db"):
        db.get_writer_connection()


def test_get_writer_connection_returns_pool_connection(monkeypatch):
    pool = FakePool()
    monkeypatch.setattr(db, "_writer_pool", pool)

    assert db.get_writer_connection() == "connection"


def test_put_writer_connection_is_noop_without_pool():
    db.put_writer_connection("connection")


def test_put_writer_connection_returns_to_pool(monkeypatch):
    pool = FakePool()
    monkeypatch.setattr(db, "_writer_pool", pool)

    db.put_writer_connection("connection", close=True)

    assert pool.put_calls == [("connection", True)]


def test_shutdown_db_closes_pool_and_is_idempotent(monkeypatch):
    pool = FakePool()
    monkeypatch.setattr(db, "_writer_pool", pool)
    monkeypatch.setattr(db, "_shutdown_called", False)

    db.shutdown_db()
    db.shutdown_db()

    assert pool.closed is True
    assert db._writer_pool is None


def test_init_db_creates_pool_and_registers_shutdown(monkeypatch):
    created = []
    registered = []

    def factory(**kwargs):
        pool = FakePool(**kwargs)
        created.append(pool)
        return pool

    monkeypatch.setattr(
        db, "atexit", SimpleNamespace(register=registered.append)
    )

    db.init_db(pool_factory=factory)

    assert len(created) == 1
    assert created[0].kwargs == {"minconn": 1, "maxconn": 2, **DB_CONFIG}
    assert db._writer_pool is created[0]
    assert registered == [db.shutdown_db]


def test_init_db_is_idempotent(monkeypatch):
    created = []

    def factory(**kwargs):
        created.append(FakePool(**kwargs))
        return created[-1]

    monkeypatch.setattr(
        db, "atexit", SimpleNamespace(register=lambda *args: None)
    )

    db.init_db(pool_factory=factory)
    db.init_db(pool_factory=factory)

    assert len(created) == 1


def test_init_db_propagates_pool_creation_failure(monkeypatch):
    def factory(**kwargs):
        raise RuntimeError("cannot connect")

    monkeypatch.setattr(
        db, "atexit", SimpleNamespace(register=lambda *args: None)
    )

    with pytest.raises(RuntimeError, match="cannot connect"):
        db.init_db(pool_factory=factory)

    assert db._writer_pool is None
