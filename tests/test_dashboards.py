"""DASH-1: real source projections, isolation, auth, and paid-work enforcement."""
import os
import uuid
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

import httpx
import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

import controls
import dashboards
os.environ.setdefault("DATABASE_URL", "postgresql://x:y@localhost/z")
os.environ.setdefault("LITELLM_MASTER_KEY", "test")
os.environ.setdefault("TANK_API_KEY", "test")
import main
import skala

ROOT = Path(__file__).resolve().parents[1]
TENANT = uuid.UUID('00000000-0000-0000-0000-0000000000aa')


class Conn:
    def __init__(self):
        self.value = False
        self.writes = []
        self.reads = []

    def acquire(self):
        return self

    def transaction(self):
        return self

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_):
        return False

    async def fetchval(self, sql, *args):
        self.reads.append((sql, args))
        if 'tank.controls' in sql:
            return self.value
        return 4

    async def execute(self, sql, *args):
        self.writes.append((sql, args))
        if 'INSERT INTO tank.controls' in sql:
            self.value = args[1]

    async def fetch(self, sql, *args):
        self.reads.append((sql, args))
        if 'tank.ledger' in sql:
            return [{'day': '2026-10-21', 'calls': 9, 'code': 5, 'delivered': 8, 'spent': 0.24}]
        if 'tank.tasks' in sql:
            return [{'id': 'one', 'title': 'A requested list', 'status': 'done'}]
        return []


@pytest.fixture
def conn(monkeypatch):
    value = Conn()
    monkeypatch.setattr(controls, 'db', lambda: value)
    monkeypatch.setattr(dashboards, 'db', lambda: value)
    return value


@pytest.fixture
def client(monkeypatch, conn):
    monkeypatch.setenv('TANK_API_KEY', 'offline-workspace-key')
    monkeypatch.setenv('TERVORY_ADMIN_USER_IDS', 'founder-one')
    app = FastAPI()
    app.include_router(controls.router)
    app.include_router(dashboards.router)
    return TestClient(app)


HEADERS = {'x-tank-key': 'offline-workspace-key', 'x-tervory-admin': 'founder-one'}


def test_non_founder_cannot_read_or_write_controls(client, conn):
    for headers in ({}, {**HEADERS, 'x-tervory-admin': 'other-user'}, {**HEADERS, 'x-tank-key': 'room-key'}):
        assert client.put('/v1/controls/paid-paused', headers=headers, json={'paused': True}).status_code == 404
        assert client.get('/v1/dashboards/founder', headers=headers).status_code == 404
    assert not conn.writes


def test_every_control_write_logs_identity_old_new_and_database_time(client, conn):
    for value in (True, False, False):
        assert client.put('/v1/controls/paid-paused', headers=HEADERS, json={'paused': value}).status_code == 200
    audit = [args for sql, args in conn.writes if 'INSERT INTO tank.control_log' in sql]
    assert [args[2:] for args in audit] == [(False, True), (True, False), (False, False)]
    assert all(args[:2] == (controls.PLATFORM, 'founder-one') for args in audit)
    schema = (ROOT / 'tank/schema.sql').read_text()
    assert 'at timestamptz NOT NULL DEFAULT now()' in schema


@pytest.mark.asyncio
async def test_pause_on_off_and_fail_closed(conn, monkeypatch):
    conn.value = True
    with pytest.raises(HTTPException, match='paid work is paused'):
        await controls.refuse_paid(task='base.extract', path='route')
    assert any('paid_refused' in sql and args[1:] == ('base.extract', 'route') for sql, args in conn.writes)
    await controls.refuse_paid(paid=False)
    conn.value = False
    await controls.refuse_paid()
    monkeypatch.setattr(controls, 'paid_paused', AsyncMock(side_effect=RuntimeError('database unavailable')))
    with pytest.raises(HTTPException, match='pause state unavailable'):
        await controls.refuse_paid()
    await controls.refuse_paid(paid=False)


@pytest.mark.asyncio
async def test_paid_host_refused_and_unlisted_free_host_runs(conn):
    conn.value = True
    with pytest.raises(HTTPException):
        await controls.paid_host_hook(httpx.Request('GET', 'https://api.search.brave.com/res/v1/web/search?q=private'))
    before = len(conn.reads)
    await controls.paid_host_hook(httpx.Request('GET', 'http://searxng:8080/search'))
    await controls.paid_host_hook(httpx.Request('GET', 'https://example.org/public'))
    assert len(conn.reads) == before
    assert all('private' not in str(row) for row in conn.writes)


@pytest.mark.asyncio
@pytest.mark.parametrize('purpose', ['judge', 'shadow', 'bench'])
async def test_llm_refuses_before_gateway_for_all_purposes(conn, monkeypatch, purpose):
    conn.value = True
    gateway = AsyncMock()
    monkeypatch.setattr(main.httpx, 'AsyncClient', gateway)
    with pytest.raises(HTTPException, match='paid work is paused'):
        await main._llm('offline-test-model', [{'role': 'user', 'content': purpose}], 10)
    gateway.assert_not_called()


@pytest.mark.asyncio
async def test_main_call_stops_after_cache_miss_and_cache_still_runs(conn, monkeypatch):
    monkeypatch.setattr(main, 'pool', lambda: conn)
    monkeypatch.setattr(main, 'load_policy', AsyncMock(return_value={
        'model': 'offline-test-model', 'priority': 'standard', 'system_prompt': None,
        'max_tokens_out': 100, 'rung': 1, 'cache_scope': 'tenant',
    }))
    monkeypatch.setattr(main, 'zenas_pool_prompt', AsyncMock(return_value=False))
    monkeypatch.setattr(main, 'model_call_refusal', lambda *a, **kw: None)
    monkeypatch.setenv('TANK_REGION', 'us-east')
    cache = SimpleNamespace(get=AsyncMock(return_value=None))
    monkeypatch.setattr(main, '_redis', cache)
    conn.value = True
    request = main.RouteRequest(tenant_id=TENANT, messages=[main.Message(role='user', content='Hello')])
    with pytest.raises(HTTPException, match='paid work is paused'):
        await main.run_route(request)
    cache.get.return_value = '{"content":"already answered"}'
    result = await main.run_route(request)
    assert result.content == 'already answered' and result.rung == 4 and result.cost_usd == 0


@pytest.mark.asyncio
async def test_code_skill_still_runs_with_paused_or_unreadable_state(conn, monkeypatch):
    conn.value = True
    monkeypatch.setattr(controls, 'paid_paused', AsyncMock(side_effect=RuntimeError('unavailable')))
    async def run(payload, _ctx):
        return {'value': payload['value'] * 2}
    monkeypatch.setattr(skala, '_import_run', lambda pkg: run)
    result = await skala.run_skill(SimpleNamespace(ref='offline.code@1.0.0'), {'value': 3}, SimpleNamespace())
    assert result['value'] == 6


@pytest.mark.asyncio
async def test_client_measurements_come_from_scoped_sources_and_unknowns_are_null(conn):
    data = await dashboards.client_dashboard(TENANT)
    assert data['jobs_done'] == 4
    assert data['daily'][0]['spent'] == 0.24
    assert data['saved_usd'] is None and data['credits_left'] is None
    assert data['recent'] == [{'id': 'one', 'title': 'A requested list', 'status': 'done'}]
    assert all(args == (TENANT,) and 'tenant_id' in sql for sql, args in conn.reads)


def test_workspace_read_key_and_uuid_required(client):
    assert client.get(f'/v1/dashboards/client?tenant_id={TENANT}').status_code == 404
    assert client.get('/v1/dashboards/client?tenant_id=invalid', headers=HEADERS).status_code == 422


def test_readonly_controls_have_no_write_path(client):
    for name in ('shadow', 'batch', 'squad', 'approve-all', 'paid-tools', 'budget', 'ghost'):
        assert client.put(f'/v1/controls/{name}', headers=HEADERS, json={}).status_code == 404


def test_only_approved_narrow_main_hooks_and_no_approved_skill_edits():
    source = (ROOT / 'tank/main.py').read_text()
    assert 'event_hooks={"request": [__import__("controls").paid_host_hook]}' in source
    assert 'refuse_paid(paid=policy["rung"] == 1' in source

@pytest.mark.asyncio
async def test_resume_restores_paid_gateway(conn, monkeypatch):
    conn.value = False
    real_client = httpx.AsyncClient
    calls = []
    async def gateway(request):
        calls.append(request)
        return httpx.Response(200, json={'choices': [{'message': {'content': 'ok'}}]})
    monkeypatch.setattr(main.httpx, 'AsyncClient', lambda **kw: real_client(transport=httpx.MockTransport(gateway), **kw))
    content, cost = await main._llm('offline-test-model', [{'role': 'user', 'content': 'test'}], 10)
    assert content == 'ok' and cost == 0 and len(calls) == 1
