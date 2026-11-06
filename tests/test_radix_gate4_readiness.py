"""Missing settings keep diagnostics up and all affected operations closed."""
from contextlib import asynccontextmanager
import importlib.util
from pathlib import Path
from types import SimpleNamespace

from fastapi import FastAPI
import httpx
import pytest

from test_rx1_scans import ROOT
import readiness
import egress


@pytest.mark.parametrize('service,required', [
    ('room', 'DATABASE_URL'), ('room', 'TANK_KEY'), ('gateway', 'DATABASE_URL'),
    ('room', 'CHASSIS_ADMIN_DATABASE_URL'), ('room', 'CHASSIS_RLS_ADMIN_ROLE'),
    ('gateway', 'RADIX_GATEWAY_ADMIN_DATABASE_URL'), ('gateway', 'RADIX_GATEWAY_RLS_ADMIN_ROLE'),
])
@pytest.mark.asyncio
async def test_missing_core_binding_keeps_health_up_and_starts_no_work(monkeypatch, service, required):
    names = ['DATABASE_URL', 'TANK_KEY', 'CHASSIS_ADMIN_DATABASE_URL', 'CHASSIS_RLS_ADMIN_ROLE',
             'RADIX_GATEWAY_ADMIN_DATABASE_URL', 'RADIX_GATEWAY_RLS_ADMIN_ROLE']
    for name in names:
        monkeypatch.setenv(name, 'postgresql://postgres@127.0.0.1/placeholder' if name == 'DATABASE_URL' else 'placeholder-setting')
    monkeypatch.delenv(required)
    started = []
    @asynccontextmanager
    async def inner(app):
        started.append(True)
        yield
    app = FastAPI(lifespan=inner)
    readiness.install(app, service=service)
    async with app.router.lifespan_context(app), httpx.AsyncClient(transport=httpx.ASGITransport(app), base_url='http://placeholder') as client:
        health = await client.get('/health')
        assert health.status_code == 200 and health.json()['status'] == 'blocked'
        assert required in health.json()['missing_settings']
        assert 'placeholder-setting' not in health.text
        for path in ('/jobs', '/lease', '/evals/run'):
            assert (await client.post(path, json={})).status_code == 503
    assert started == []


@pytest.mark.parametrize('name', readiness.STORAGE)
@pytest.mark.asyncio
async def test_optional_storage_binding_names_missing_setting_without_calling_storage(monkeypatch, name):
    for setting in readiness.STORAGE:
        monkeypatch.setenv(setting, 'placeholder-setting')
    monkeypatch.delenv(name)
    app = FastAPI()
    readiness.install(app)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app), base_url='http://placeholder') as client:
        response = await client.put('/storage/objects/placeholder', content=b'placeholder')
        assert response.status_code == 503 and response.json()['missing_settings'] == [name]
        assert 'placeholder-setting' not in response.text


@pytest.mark.parametrize('service,prefix', [('room', 'CHASSIS'), ('gateway', 'RADIX_GATEWAY')])
@pytest.mark.asyncio
async def test_enforced_database_names_missing_admin_pair_and_closes_probe(monkeypatch, service, prefix):
    for suffix in ('_ADMIN_DATABASE_URL', '_RLS_ADMIN_ROLE'):
        monkeypatch.delenv(prefix + suffix, raising=False)
    conn = SimpleNamespace(closed=False)
    async def fetchval(query): return True
    async def close(): conn.closed = True
    conn.fetchval, conn.close = fetchval, close
    async def connect(*args, **kwargs): return conn
    monkeypatch.setattr(readiness.asyncpg, 'connect', connect)
    assert await readiness.database_settings(service) == [prefix + '_ADMIN_DATABASE_URL', prefix + '_RLS_ADMIN_ROLE']
    assert conn.closed


@pytest.mark.asyncio
async def test_database_failure_is_safe_setting_diagnostic(monkeypatch):
    async def connect(*args, **kwargs): raise OSError('placeholder-private-connection-detail')
    monkeypatch.setattr(readiness.asyncpg, 'connect', connect)
    assert await readiness.database_settings('room') == ['DATABASE_URL']


@pytest.mark.asyncio
async def test_actual_room_starts_without_settings_and_never_enters_inner_lifespans(monkeypatch):
    for name in ('DATABASE_URL', 'TANK_KEY', 'CHASSIS_ADMIN_DATABASE_URL', 'CHASSIS_RLS_ADMIN_ROLE'):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.syspath_prepend(str(ROOT / 'agents/radix'))
    gold = importlib.util.spec_from_file_location('placeholder_gate4_gold', ROOT / 'agents/radix/gold_sources.py')
    module = importlib.util.module_from_spec(gold); gold.loader.exec_module(module)
    monkeypatch.setitem(__import__('sys').modules, 'gold_sources', module)
    spec = importlib.util.spec_from_file_location('placeholder_gate4_room', ROOT / 'agents/radix/app.py')
    room = importlib.util.module_from_spec(spec); spec.loader.exec_module(room)
    async with room.app.router.lifespan_context(room.app):
        async with httpx.AsyncClient(transport=httpx.ASGITransport(room.app), base_url='http://placeholder') as client:
            response = await client.get('/health')
            assert response.status_code == 200 and response.json()['missing_settings'] == ['DATABASE_URL', 'TANK_KEY']
            assert (await client.post('/jobs', json={})).status_code == 503
        assert not hasattr(room.app.state, 'pool')


def test_composed_database_url_without_password_names_founder_setting():
    assert readiness.missing_settings(environ={'DATABASE_URL': 'postgresql://agent_radix:@postgres/placeholder',
                                               'TANK_KEY': 'placeholder'}) == ['AGENT_DB_PASSWORD_RADIX']


def test_unconfigured_egress_stays_up_and_refuses_before_dns(monkeypatch, capsys):
    monkeypatch.delenv('R2_ACCOUNT_ID', raising=False)
    monkeypatch.setenv('RADIX_EGRESS_POLICY', str(ROOT / 'agents/radix/egress-policy.json'))
    monkeypatch.setattr(egress, 'private_bind_address', lambda: '127.0.0.1')
    observed = []
    class Wire:
        def __init__(self, request): self.request, self.output = request, b''
        def settimeout(self, value): pass
        def recv(self, size): value, self.request = self.request, b''; return value
        def sendall(self, value): self.output += value
        def close(self): pass
    class Server:
        def __init__(self, proxy, **kwargs): self.proxy = proxy
        def serve_forever(self):
            for request in (b'GET /health HTTP/1.1\r\n\r\n', b'CONNECT lokd.co.za:443 HTTP/1.1\r\n\r\n'):
                wire = Wire(request); self.proxy.handle(wire); observed.append(wire.output)
    monkeypatch.setattr(egress, 'Server', Server)
    assert egress.main() == 0
    assert b'200 OK' in observed[0] and b'R2_ACCOUNT_ID' in observed[0]
    assert b'403 Forbidden' in observed[1]
    assert 'R2_ACCOUNT_ID' in capsys.readouterr().err


def test_missing_room_proxy_names_setting_before_any_tunnel(monkeypatch):
    monkeypatch.delenv('RADIX_EGRESS_PROXY', raising=False)
    with pytest.raises(egress.ProxyError, match='RADIX_EGRESS_PROXY'):
        egress.open_tunnel()
