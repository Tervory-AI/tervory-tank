"""Day-zero stores and actual scheduled handlers, with external services faked."""
import importlib.util
import json
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import UUID, uuid4

import httpx
import pytest

from test_radix_passive import database as database, A, FakeServer, ROOT
import active_routes
import passive_gateway


@pytest.mark.asyncio
async def test_own_scan_enrolls_weekly_only_after_verified_lease(database, monkeypatch):
    domain, target = 'tervory.com', 'https://tervory.com/'
    await database.issue(A, domain)
    assert not await database.pool.fetchval('SELECT 1 FROM agent_radix.weekly_domains WHERE tenant_id=$1', A)
    steps = []
    async def proof(*args): steps.append('proof'); return True
    monkeypatch.setattr(passive_gateway, 'private_bind_address', lambda: '127.0.0.1')
    lease = passive_gateway.Lease(database, check=proof, server=FakeServer)
    async def control(request):
        scan = UUID(json.loads(request.content)['scan_id'])
        if request.url.path == '/active/lease': await lease.start(A, scan, active=True)
        else: await lease.release(A, scan)
        return httpx.Response(200, json={'ready': True})
    async def scanner(url, directory):
        assert url == target
        steps.append('scanner')
        assert await database.pool.fetchval('SELECT own FROM agent_radix.weekly_domains WHERE tenant_id=$1', A)
        return {'findings': [], 'checks': {'active': {'status': 'complete'}}}
    result = await active_routes.execute(database, A, target, scanner=scanner,
        http=httpx.AsyncClient(transport=httpx.MockTransport(control)))
    assert steps == ['proof', 'scanner'] and result['status'] == 'complete' and lease.run is None
    assert await database.pool.fetchval('SELECT count(*) FROM agent_radix.weekly_domains WHERE tenant_id=$1', A) == 1


@pytest.mark.asyncio
async def test_day_zero_has_no_phantom_findings_watches_reports_or_receipts(database):
    assert await database.watches(A) == []
    assert await database.findings(A, uuid4()) == []
    assert await database.changes(A, 'placeholder.example') == {'status': 'pending'}
    with pytest.raises(LookupError): await database.report(A, uuid4())
    for table in ('passive_scans', 'findings', 'weekly_runs', 'regulation_runs'):
        assert await database.pool.fetchval(f'SELECT count(*) FROM agent_radix.{table} WHERE tenant_id=$1', A) == 0


@pytest.mark.asyncio
async def test_every_cron_handler_runs_in_day_zero_dry_run(database, monkeypatch):
    monkeypatch.syspath_prepend(str(ROOT / 'agents/radix'))
    spec = importlib.util.spec_from_file_location('placeholder_gate4_gold', ROOT / 'agents/radix/gold_sources.py')
    gold = importlib.util.module_from_spec(spec); spec.loader.exec_module(gold)
    monkeypatch.setitem(__import__('sys').modules, 'gold_sources', gold)
    spec = importlib.util.spec_from_file_location('placeholder_gate4_scheduled', ROOT / 'agents/radix/app.py')
    room = importlib.util.module_from_spec(spec); spec.loader.exec_module(room)
    room.app.state.pool = database.pool
    memory = SimpleNamespace(remember=AsyncMock(return_value={'seen': 1}))
    executed = {}
    for schedule in room.app.state.schedules:
        ctx = SimpleNamespace(agent='radix', tenant_id=schedule['tenant_id'], input=schedule['input'], memory=memory)
        executed[schedule['kind']] = await room.app.state.handlers[schedule['kind']](ctx)
    assert executed == {'watch_tick': {'count': 0}, 'ping': {'pong': True, 'agent': 'radix', 'heartbeats_seen': 1}}
    memory.remember.assert_awaited_once()
    assert not await database.pool.fetchval('SELECT 1 FROM agent_radix.passive_scans')
