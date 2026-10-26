"""Opt-in replay of CI's random UUID substring failure; never auto-collected.

Run the unchanged savings test with `-p ci_savings_replay` and this directory
on PYTHONPATH. Only the first disposable ledger row's random ID is fixed;
prices, tenant ownership, export code and the test assertion are unchanged.
"""
from functools import wraps

import asyncpg
import pytest


@pytest.fixture(autouse=True)
def replay_row_id(request, monkeypatch):
    if request.node.name != 'test_exports_reconcile_and_keep_precise_decimals':
        return
    original = asyncpg.Connection.fetchval
    assigned = False

    @wraps(original)
    async def fetchval(connection, query, *args, **kwargs):
        nonlocal assigned
        if not assigned and 'INSERT INTO tank.ledger(' in query:
            assigned = True
            # Valid UUID, containing 777, last in the export's ts DESC,id DESC
            # order. Generate it at insertion so all FK receipts stay intact.
            query = query.replace('INSERT INTO tank.ledger(', 'INSERT INTO tank.ledger(id,', 1)
            query = query.replace('VALUES(', "VALUES('00000000-0000-4777-8000-000000000001'::uuid,", 1)
        return await original(connection, query, *args, **kwargs)

    monkeypatch.setattr(asyncpg.Connection, 'fetchval', fetchval)
