"""Tests for the asynchronous request-log writer."""

from __future__ import annotations

from queue import Empty, Full

import request_log_writer as writer
from psycopg2 import OperationalError


class FakeCursor:
    def __init__(self, error: Exception | None = None) -> None:
        self.error = error

    def __enter__(self):
        if self.error is not None:
            raise self.error
        return self

    def __exit__(self, *exc_info):
        return False


class FakeConnection:
    def __init__(self, error: Exception | None = None) -> None:
        self.error = error
        self.committed = False

    def cursor(self):
        return FakeCursor(self.error)

    def commit(self):
        self.committed = True


class FakeThread:
    def __init__(self, *, target, daemon, name) -> None:
        self.target = target
        self.daemon = daemon
        self.name = name
        self.alive = False
        self.joined = False

    def start(self):
        self.alive = True

    def is_alive(self):
        return self.alive

    def join(self, timeout=None):
        self.joined = True
        self.alive = False


class SequenceQueue:
    def __init__(self, *items) -> None:
        self.items = list(items)

    def get(self, timeout=None):
        item = self.items.pop(0)
        if isinstance(item, BaseException):
            raise item
        return item


def _row():
    return ("/time", "GET", 200, 5, "UTC", None)


def test_enqueue_is_noop_when_disabled():
    writer.set_enabled(False)

    writer.enqueue_request_log(
        path="/time",
        method="GET",
        status=200,
        latency_ms=5,
        timezone="UTC",
        trace_id=None,
        span_context=None,
    )

    assert writer._log_queue.empty()


def test_enqueue_puts_item_on_queue_when_enabled():
    writer.set_enabled(True)

    writer.enqueue_request_log(
        path="/time",
        method="GET",
        status=200,
        latency_ms=5,
        timezone="UTC",
        trace_id="abc",
        span_context=None,
    )

    item = writer._log_queue.get_nowait()
    assert item[0] == ("/time", "GET", 200, 5, "UTC", "abc")
    assert item[1] is None
    assert item[2] is not None


def test_enqueue_counts_drops_when_queue_is_full(monkeypatch):
    writer.set_enabled(True)

    def full_queue(item):
        raise Full

    monkeypatch.setattr(writer._log_queue, "put_nowait", full_queue)
    timestamps = iter([100.0, 100.5])
    monkeypatch.setattr(writer, "monotonic", lambda: next(timestamps))

    writer.enqueue_request_log(
        path="/time",
        method="GET",
        status=200,
        latency_ms=5,
        timezone=None,
        trace_id=None,
        span_context=None,
    )
    writer.enqueue_request_log(
        path="/time",
        method="GET",
        status=200,
        latency_ms=5,
        timezone=None,
        trace_id=None,
        span_context=None,
    )

    assert writer._dropped_since_last_log == 1


def test_flush_batch_inserts_and_returns_connection(monkeypatch):
    connection = FakeConnection()
    returned = []
    executed = []

    monkeypatch.setattr(writer, "get_writer_connection", lambda: connection)
    monkeypatch.setattr(
        writer,
        "put_writer_connection",
        lambda conn, close=None: returned.append((conn, close)),
    )
    monkeypatch.setattr(
        writer,
        "execute_values",
        lambda cur, sql, rows, page_size: executed.append((sql, rows, page_size)),
    )

    writer._flush_batch([_row()])

    assert connection.committed is True
    assert returned == [(connection, False)]
    assert executed[0][1] == [_row()]
    assert executed[0][2] == 50


def test_flush_batch_retries_with_a_fresh_connection(monkeypatch):
    first = FakeConnection(error=OperationalError("connection lost"))
    second = FakeConnection()
    connections = iter([first, second])
    returned = []

    monkeypatch.setattr(
        writer, "get_writer_connection", lambda: next(connections)
    )
    monkeypatch.setattr(
        writer,
        "put_writer_connection",
        lambda conn, close=None: returned.append((conn, close)),
    )
    monkeypatch.setattr(writer, "execute_values", lambda *args, **kwargs: None)

    writer._flush_batch([_row()])

    assert returned == [(first, True), (second, False)]
    assert second.committed is True


def test_flush_batch_returns_broken_connection_when_retry_fails(monkeypatch):
    first = FakeConnection(error=OperationalError("first failure"))
    second = FakeConnection(error=OperationalError("second failure"))
    connections = iter([first, second])
    returned = []

    monkeypatch.setattr(
        writer, "get_writer_connection", lambda: next(connections)
    )
    monkeypatch.setattr(
        writer,
        "put_writer_connection",
        lambda conn, close=None: returned.append((conn, close)),
    )

    writer._flush_batch([_row()])

    assert returned == [(first, True), (second, True)]


def test_flush_batch_returns_connection_after_unexpected_error(monkeypatch):
    connection = FakeConnection(error=ValueError("bad row"))
    returned = []

    monkeypatch.setattr(writer, "get_writer_connection", lambda: connection)
    monkeypatch.setattr(
        writer,
        "put_writer_connection",
        lambda conn, close=None: returned.append((conn, close)),
    )

    writer._flush_batch([_row()])

    assert returned == [(connection, False)]


def test_writer_loop_flushes_batch_before_sentinel(monkeypatch):
    writer._log_queue.put((_row(), None, None))
    writer._log_queue.put(writer._SENTINEL)
    flushed = []

    monkeypatch.setattr(writer, "BATCH_FLUSH_SECONDS", 1.0)
    monkeypatch.setattr(writer, "BATCH_SIZE", 10)
    monkeypatch.setattr(
        writer, "_flush_batch", lambda batch: flushed.append(batch)
    )

    writer._writer_loop()

    assert flushed == [[_row()]]


def test_writer_loop_exits_without_flush_when_sentinel_is_first(monkeypatch):
    writer._log_queue.put(writer._SENTINEL)
    flushed = []
    monkeypatch.setattr(
        writer, "_flush_batch", lambda batch: flushed.append(batch)
    )

    writer._writer_loop()

    assert flushed == []


def test_writer_loop_flushes_when_batch_deadline_expires(monkeypatch):
    writer._log_queue.put((_row(), None, None))
    writer._log_queue.put(writer._SENTINEL)
    flushed = []

    monkeypatch.setattr(writer, "BATCH_FLUSH_SECONDS", 0)
    monkeypatch.setattr(writer, "BATCH_SIZE", 10)
    monkeypatch.setattr(
        writer, "_flush_batch", lambda batch: flushed.append(batch)
    )

    writer._writer_loop()

    assert flushed == [[_row()]]


def test_writer_loop_flushes_when_queue_times_out(monkeypatch):
    queue = SequenceQueue((_row(), None, None), Empty(), writer._SENTINEL)
    flushed = []

    monkeypatch.setattr(writer, "_log_queue", queue)
    monkeypatch.setattr(writer, "BATCH_FLUSH_SECONDS", 10)
    monkeypatch.setattr(writer, "BATCH_SIZE", 10)
    monkeypatch.setattr(
        writer, "_flush_batch", lambda batch: flushed.append(batch)
    )

    writer._writer_loop()

    assert flushed == [[_row()]]


def test_writer_loop_batches_multiple_items(monkeypatch):
    second_row = ("/ready", "GET", 503, 2, None, None)
    writer._log_queue.put((_row(), None, None))
    writer._log_queue.put((second_row, None, None))
    writer._log_queue.put(writer._SENTINEL)
    flushed = []

    monkeypatch.setattr(writer, "BATCH_FLUSH_SECONDS", 10)
    monkeypatch.setattr(writer, "BATCH_SIZE", 10)
    monkeypatch.setattr(
        writer, "_flush_batch", lambda batch: flushed.append(batch)
    )

    writer._writer_loop()

    assert flushed == [[_row(), second_row]]


def test_init_request_log_writer_starts_thread_once(monkeypatch):
    created = []

    def fake_thread(**kwargs):
        thread = FakeThread(**kwargs)
        created.append(thread)
        return thread

    monkeypatch.setattr(writer, "Thread", fake_thread)
    monkeypatch.setattr(writer, "_writer_thread", None)
    monkeypatch.setattr(writer, "_shutdown_registered", False)
    monkeypatch.setattr(writer.atexit, "register", lambda *args: None)

    writer.init_request_log_writer()
    writer.init_request_log_writer()

    assert len(created) == 1
    assert created[0].alive is True
    assert writer.is_enabled() is True


def test_shutdown_request_log_writer_signals_and_joins(monkeypatch):
    thread = FakeThread(target=lambda: None, daemon=True, name="test")
    thread.start()
    monkeypatch.setattr(writer, "_writer_thread", thread)
    monkeypatch.setattr(writer, "_shutdown_called", False)

    writer.shutdown_request_log_writer()
    writer.shutdown_request_log_writer()

    assert thread.joined is True
    assert writer.is_enabled() is False
    assert writer._log_queue.get_nowait() is writer._SENTINEL
