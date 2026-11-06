import asyncio
from contextlib import asynccontextmanager
from copy import deepcopy
from uuid import uuid4

import pytest

from test_b3_base_room import _call
import pipeline
import room


@pytest.mark.asyncio
async def test_completed_record_is_checkpointed_before_slow_record_and_survives_cancel(monkeypatch):
    completed = asyncio.Event()
    slow = asyncio.Event()
    saved = []

    async def enrich(raw, *args):
        if raw['name'] == 'slow':
            slow.set()
            await asyncio.Event().wait()
        return pipeline.Outcome(status='done', cost_usd=0)

    async def checkpoint(index, outcome):
        saved.append(index)
        completed.set()

    monkeypatch.setattr(pipeline, 'enrich_one', enrich)
    task = asyncio.create_task(pipeline.enrich_queued(
        [0, 1], ['first', 'second'], [{'name': 'fast'}, {'name': 'slow'}],
        [None, None], [], True, None, _call, lambda: False, 2, on_result=checkpoint))
    await asyncio.wait_for(completed.wait(), 2)
    await asyncio.wait_for(slow.wait(), 2)
    assert saved == [0] and not task.done()
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert saved == [0]


@pytest.mark.asyncio
async def test_provider_pause_prevents_dispatch_of_remaining_records(monkeypatch):
    attempted = []
    paused = False

    async def enrich(raw, *args):
        attempted.append(raw['name'])
        return pipeline.Outcome(status='queued', error='billing refused')

    async def checkpoint(index, outcome):
        nonlocal paused
        paused = True

    monkeypatch.setattr(pipeline, 'enrich_one', enrich)
    results = await pipeline.enrich_queued(
        list(range(10)), [str(i) for i in range(10)], [{'name': str(i)} for i in range(10)],
        [None] * 10, [], True, None, _call, lambda: paused, 0, on_result=checkpoint)
    assert attempted == ['0']
    assert sum(outcome is None for _, outcome in results) == 9


@pytest.mark.asyncio
async def test_checkpoint_failure_cancels_other_inflight_work(monkeypatch):
    stopped = asyncio.Event()
    ready = asyncio.Event()

    async def enrich(raw, *args):
        if raw['name'] == 'waiting':
            ready.set()
            try:
                await asyncio.Event().wait()
            finally:
                stopped.set()
        await ready.wait()
        return pipeline.Outcome(status='done')

    async def checkpoint(*args):
        raise OSError('fixture storage failure')

    monkeypatch.setattr(pipeline, 'enrich_one', enrich)
    with pytest.raises(OSError):
        await pipeline.enrich_queued(
            [0, 1], ['one', 'two'], [{'name': 'failed'}, {'name': 'waiting'}],
            [None, None], [], True, None, _call, lambda: False, 2, on_result=checkpoint)
    assert stopped.is_set()


@pytest.mark.asyncio
async def test_batch_and_records_are_atomic_on_partial_insert_failure():
    class Connection:
        tasks = []
        records = []

        @asynccontextmanager
        async def transaction(self):
            before = deepcopy((self.tasks, self.records))
            try:
                yield
            except BaseException:
                self.tasks, self.records = before
                raise

        async def fetchrow(self, sql, *args):
            self.tasks.append(args[0])
            return {'id': args[0]}

        async def executemany(self, sql, rows):
            self.records.append(rows[0])
            raise OSError('fixture insert interrupted')

    conn = Connection()
    with pytest.raises(OSError):
        await room.insert_batch(conn, uuid4(), None, 'fixture batch', [{'name': 'one'}],
                                '', False, None, 1, None)
    assert conn.tasks == conn.records == []
