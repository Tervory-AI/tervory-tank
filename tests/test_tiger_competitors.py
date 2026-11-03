"""Tiger catalogue matching: synthetic identifiers and offline pages only."""
import sys
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import UUID

import pytest

import trigger_routes

TENANT = UUID('11111111-1111-4111-8111-111111111111')


@pytest.mark.asyncio
async def test_code_receipt_default_still_records_trigger(monkeypatch):
    pool = SimpleNamespace(fetchval=AsyncMock(return_value=TENANT))
    monkeypatch.setitem(sys.modules, 'main', SimpleNamespace(pool=lambda: pool, box_region=lambda: 'us-east'))
    assert await trigger_routes.code_receipt(TENANT, 'trigger.check') == TENANT
    sql, *args = pool.fetchval.call_args.args
    assert "VALUES($1,$2,$5,$3,3,'code',0,0,0,$4)" in sql
    assert args == [TENANT, 'us-east', 'trigger.check', None, 'trigger']


@pytest.mark.asyncio
async def test_code_receipt_records_tiger_without_interpolating_agent(monkeypatch):
    pool = SimpleNamespace(fetchval=AsyncMock(return_value=TENANT))
    monkeypatch.setitem(sys.modules, 'main', SimpleNamespace(pool=lambda: pool, box_region=lambda: 'us-east'))
    await trigger_routes.code_receipt(TENANT, 'tiger.match', agent='tiger')
    sql, *args = pool.fetchval.call_args.args
    assert 'tiger' not in sql
    assert args == [TENANT, 'us-east', 'tiger.match', None, 'tiger']
