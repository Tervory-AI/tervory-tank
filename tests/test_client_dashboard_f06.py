"""Dashboard projection reads only the requested tenant; no Tank startup or network."""
import uuid
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
import dashboards

TENANT = uuid.UUID('00000000-0000-0000-0000-0000000000aa')
OTHER = uuid.UUID('00000000-0000-0000-0000-0000000000bb')

class ReadOnlyDB:
    def __init__(self):
        self.reads = []
    def acquire(self): return self
    async def __aenter__(self): return self
    async def __aexit__(self, *_): pass
    async def fetch(self, sql, *args):
        self.reads.append((sql, args))
        assert args == (TENANT,)
        assert 'tenant_id' in sql
        if 'tenant_squad' in sql: return [{'agent': 'base'}]
        if 'tank.tasks' in sql: return [{'id': 'own-job', 'title': 'Own work', 'status': 'done'}]
        return []
    async def fetchval(self, sql, *args):
        self.reads.append((sql, args))
        assert args == (TENANT,)
        return 0

@pytest.mark.asyncio
async def test_grants_and_jobs_project_only_requested_tenant(monkeypatch):
    db = ReadOnlyDB()
    monkeypatch.setattr(dashboards, 'db', lambda: db)
    result = await dashboards.client_dashboard(TENANT)
    assert result['granted_squads'] == ['base']
    assert result['recent'] == [{'id': 'own-job', 'title': 'Own work', 'status': 'done'}]
    assert result['jobs_done'] == 0
    assert all(OTHER not in args for _, args in db.reads)


def test_dashboard_read_requires_workspace_key_and_rejects_platform(monkeypatch):
    monkeypatch.setenv('TANK_API_KEY', 'offline-f06-key')
    app = FastAPI()
    app.include_router(dashboards.router)
    with TestClient(app) as client:
        for headers in [{}, {'x-tank-key': 'wrong'}]:
            assert client.get(f'/v1/dashboards/client?tenant_id={TENANT}', headers=headers).status_code == 404
        assert client.get('/v1/dashboards/client?tenant_id=00000000-0000-0000-0000-000000000001', headers={'x-tank-key':'offline-f06-key'}).status_code == 404
