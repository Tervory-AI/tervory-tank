import asyncio
import threading
import time
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

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


@pytest.mark.asyncio
async def test_heartbeat_marks_a_hung_load_stalled_and_keeps_resume(monkeypatch):
    monkeypatch.setenv("TANK_REGION", "us-east")
    monkeypatch.setattr(bulk, "HEARTBEAT_SECONDS", 0.01)
    monkeypatch.setattr(bulk, "STALL_SECONDS", 0.03)
    snapshot = bulk.Snapshot("2026-01-01", {kind: kind for kind in bulk.REQUIRED_KINDS})
    notes = []

    async def keys(_getter):
        return []

    async def hung(*_args):
        await asyncio.sleep(10)

    async def note(progress, force=False):
        notes.append(progress.line())

    monkeypatch.setattr(bulk, "_collect_keys", keys)
    monkeypatch.setattr(bulk, "choose_snapshot", lambda _keys: snapshot)
    monkeypatch.setattr(bulk, "_read_schema", hung)
    monkeypatch.setattr(bulk._Progress, "note", note)
    state = bulk.BulkState(day=snapshot.day, last_opinion_id=42)
    with pytest.raises(bulk.BulkStalled, match="resumable"):
        await bulk.load_bulk(None, state=state)
    assert len(notes) >= 2
    assert state.last_opinion_id == 42
    assert not state.files_done
