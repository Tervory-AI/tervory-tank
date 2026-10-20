import asyncio
import threading
import time

import pytest

from agents.zenas.pool.adapters import courtlistener_bulk as bulk


@pytest.mark.asyncio
async def test_full_queue_finishes_without_losing_or_duplicating_rows():
    stop = threading.Event()
    result = []
    async for row in bulk._aiter_thread(lambda: iter(range(100)), stop):
        result.append(row)
        await asyncio.sleep(0.001)
    assert result == list(range(100))
    assert stop.is_set()


@pytest.mark.asyncio
async def test_reader_failure_propagates_after_queued_rows():
    def worker():
        yield "one"
        raise TimeoutError("socket timed out")

    result = []
    with pytest.raises(bulk.BulkStalled, match="resumable"):
        async for row in bulk._aiter_thread(worker, threading.Event()):
            result.append(row)
    assert result == ["one"]


@pytest.mark.asyncio
async def test_stalled_reader_and_cancel_are_bounded(monkeypatch):
    monkeypatch.setattr(bulk, "STALL_SECONDS", 0.02)
    stop = threading.Event()

    def worker():
        stop.wait(2)
        return iter([])

    started = time.monotonic()
    with pytest.raises(bulk.BulkStalled):
        async for _row in bulk._aiter_thread(worker, stop):
            pass
    assert time.monotonic() - started < 1
    assert stop.is_set()


def test_rate_in_detail():
    progress = bulk._Progress(None, "2026-01-01")
    progress.rows_read = 10
    assert "rows/second" in progress.line()
