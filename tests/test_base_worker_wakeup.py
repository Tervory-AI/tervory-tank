"""Ingress wake between an empty queue read and wait must never be discarded."""
import asyncio
from contextlib import asynccontextmanager
from types import SimpleNamespace

import pytest
from test_base_gate5 import room


@pytest.mark.asyncio
async def test_committed_ingress_wake_survives_empty_select(monkeypatch):
    wake = asyncio.Event()
    observed = []
    class Finished(BaseException):
        pass
    class Connection:
        async def fetchrow(self, sql):
            assert "status='queued'" in sql
            # The empty result was already determined, then ingress commits and
            # signals before the worker receives that empty result.
            wake.set()
            return None
    class Pool:
        @asynccontextmanager
        async def acquire(self):
            yield Connection()
    async def tables(conn):
        pass
    async def waiting(awaitable, *, timeout):
        observed.append((wake.is_set(), timeout))
        awaitable.close()
        raise Finished
    monkeypatch.setattr(room, '_wake', wake)
    monkeypatch.setattr(room, 'ensure_tables', tables)
    monkeypatch.setattr(room, 'models_paused', lambda: False)
    monkeypatch.setattr(room, 'asyncio', SimpleNamespace(wait_for=waiting, TimeoutError=asyncio.TimeoutError))
    with pytest.raises(Finished):
        await room._owned_loop(Pool(), None)
    assert observed == [(True, 30)]
