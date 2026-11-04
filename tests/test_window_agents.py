"""Offline boundary tests; run with PYTHONPATH=tank:. pytest this file."""
import uuid
from pathlib import Path
from unittest.mock import AsyncMock

import httpx
import pytest
import pytest_asyncio
from fastapi import HTTPException

from window_agents import Credential, Start, leased
from workers.settings import Settings
from workers.window_agent.github import UserGitHub
from workers.window_agent.service import argv_for


def test_task_container_is_non_root_and_has_no_service_key():
    job = {'job_id': str(uuid.uuid4()), 'tenant_id': str(uuid.uuid4()), 'repo': 'alice/project'}
    argv = argv_for(Settings(tank_url='http://127.0.0.1:8000'), 'tervory-worker-1-1234abcd', 'crun', Path('/tmp/task'), job)
    assert '--privileged' not in argv
    assert '--cap-add' not in argv
    assert argv[argv.index('--user') + 1] == '1001:1001'
    assert argv[argv.index('--cap-drop') + 1] == 'ALL'
    assert '--rm' in argv and '--read-only' in argv
    assert not any('sock' in a or 'tank_key' in a for a in argv)
    assert 'no-new-privileges' in argv


@pytest.mark.parametrize('repo', ['../project', 'alice/../project', 'https://github.com/alice/p', 'alice/p.git', '-alice/p'])
def test_repository_input_refused(repo):
    with pytest.raises(ValueError):
        Start(repo=repo, credential_name='github', prompt='fix', request_id=uuid.uuid4())


def test_credential_name_only_in_task():
    with pytest.raises(ValueError):
        Start(repo='alice/p', credential_name='github', prompt='fix', request_id=uuid.uuid4(), token='forbidden')
    with pytest.raises(ValueError):
        Credential(name='github', value='a' * 40)


@pytest.mark.asyncio
async def test_cancelled_or_wrong_lease_cannot_call_model():
    import hashlib
    lease = 'a' * 43
    conn = AsyncMock()
    conn.fetchrow.return_value = {'lease_hash': hashlib.sha256(lease.encode()).hexdigest(), 'status': 'cancelled'}
    with pytest.raises(HTTPException) as exc:
        await leased(conn, uuid.uuid4(), uuid.uuid4(), lease)
    assert exc.value.status_code == 409
    with pytest.raises(HTTPException) as exc:
        await leased(conn, uuid.uuid4(), uuid.uuid4(), 'wrong')
    assert exc.value.status_code == 404


@pytest.mark.asyncio
async def test_own_repository_default_branch_and_draft_never_merge():
    requests = []

    def fake(request):
        import json
        requests.append(request)
        if request.method == 'GET':
            return httpx.Response(200, json={'default_branch': 'develop', 'permissions': {'push': True}})
        data = json.loads(request.content)
        assert data['base'] == 'develop' and data['draft'] is True
        return httpx.Response(201, json={'number': 8, 'html_url': 'https://github.com/alice/project/pull/8'})

    async with httpx.AsyncClient(transport=httpx.MockTransport(fake)) as client:
        github = UserGitHub('alice/project', client)
        token = 'github_pat_' + 'test' * 8
        base = await github.default_branch(token)
        result = await github.draft(token, 'worker/window-test', base, 'Fix')
        assert result['number'] == 8
        with pytest.raises(RuntimeError):
            await github._send('PUT', 'https://api.github.com/repos/alice/project/merge', token)
        with pytest.raises(RuntimeError):
            await github._send('GET', 'https://api.github.com/repos/bob/other', token)
    assert len(requests) == 2


@pytest_asyncio.fixture
async def agent_db(monkeypatch):
    import os
    import base64
    import secrets
    import asyncpg
    from urllib.parse import urlsplit, urlunsplit
    import command
    from window_agents import SCHEMA

    url = os.environ.get('POOL_SCHEMA_DATABASE_URL')
    if not url:
        pytest.skip('POOL_SCHEMA_DATABASE_URL is required for PostgreSQL integration')
    parsed = urlsplit(url)
    database = 'window_agents_' + uuid.uuid4().hex
    admin = await asyncpg.connect(url)
    await admin.execute(f'CREATE DATABASE "{database}"')
    pool = await asyncpg.create_pool(urlunsplit(parsed._replace(path='/' + database)), min_size=1, max_size=4)
    try:
        async with pool.acquire() as conn:
            await conn.execute('CREATE SCHEMA tank; CREATE TABLE tank.command_threads(thread_id uuid PRIMARY KEY,tenant_id uuid,user_id text,title text,state jsonb)')
            await conn.execute("CREATE TABLE tank.vault_items(tenant_id uuid,vault text,kind text,name text,metadata jsonb,sealed text, PRIMARY KEY(tenant_id,vault,kind,name))")
            await conn.execute(SCHEMA)
            await conn.execute(SCHEMA)  # Every Tank restart is safe.
        monkeypatch.setattr(command, 'db', lambda: pool)
        monkeypatch.setenv('TANK_VAULT_KEY', base64.urlsafe_b64encode(secrets.token_bytes(32)).decode())
        yield pool
    finally:
        await pool.close()
        await admin.execute(f'DROP DATABASE "{database}"')
        await admin.close()


@pytest.mark.asyncio
async def test_durable_queue_tenant_and_user_isolation_cancel_and_recovery(agent_db, monkeypatch):
    import command
    import window_agents as agents
    from fastapi import FastAPI
    pool = agent_db
    actor = [command.Actor(uuid.uuid4(), 'alice', False)]
    original = actor[0]
    application = FastAPI()
    application.include_router(agents.router)
    application.dependency_overrides[agents.actor_identity] = lambda: actor[0]
    application.dependency_overrides[command.worker] = lambda: None
    job_id = str(uuid.uuid4())
    start = {'repo': 'alice/project', 'credential_name': 'github', 'prompt': 'Fix the counter', 'request_id': job_id}
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=application), base_url='http://test') as client:
        token = 'github_pat_' + 'test' * 8
        assert (await client.put('/v1/window-agents/vault/github', json={'name': 'github', 'value': token})).status_code == 204
        assert (await client.post('/v1/window-agents/jobs', json=start)).status_code == 202
        # Idempotent enqueue cannot create a second paid task.
        assert (await client.post('/v1/window-agents/jobs', json=start)).status_code == 202
        actor[0] = command.Actor(original.tenant_id, 'bob', False)
        assert (await client.get('/v1/window-agents/jobs')).json() == []
        assert (await client.get('/v1/window-agents/vault/github')).json() == []
        assert (await client.post(f'/v1/window-agents/jobs/{job_id}/cancel', json={})).status_code == 404
        actor[0] = command.Actor(uuid.uuid4(), 'alice', True)
        assert (await client.get('/v1/window-agents/jobs')).json() == []
        actor[0] = original
        # Exactly one worker can claim it, independently of any client window.
        import asyncio
        claims = await asyncio.gather(*[client.post('/v1/window-agents/worker/next', json={}) for _ in range(2)])
        job = next(c.json() for c in claims if c.json())
        assert sum(c.json() is not None for c in claims) == 1
        path = f"/v1/window-agents/worker/{job['tenant_id']}/{job_id}"
        lease = {'lease': job['lease']}
        assert (await client.post(path + '/credential', json=lease)).json() == {'value': token}
        assert (await client.post(path + '/credential', json={'lease': 'z' * 43})).status_code == 404
        assert (await client.post(f'/v1/window-agents/jobs/{job_id}/cancel', json={})).json()['status'] == 'cancelled'
        assert (await client.post(path + '/heartbeat', json=lease)).status_code == 409
        assert (await client.post(path + '/finish', json={**lease, 'status': 'done'})).status_code == 409
        # A different queued task claimed by a lost worker stops, never replays.
        next_id = str(uuid.uuid4())
        await client.post('/v1/window-agents/jobs', json={**start, 'request_id': next_id})
        lost = (await client.post('/v1/window-agents/worker/next', json={})).json()
        async with pool.acquire() as conn:
            await conn.execute("UPDATE tank.window_agent_jobs SET heartbeat=now()-interval '3 minutes' WHERE tenant_id=$1 AND job_id=$2", original.tenant_id, uuid.UUID(lost['job_id']))
            stored = await conn.fetchval("SELECT sealed FROM tank.vault_items WHERE tenant_id=$1 AND vault=$2 AND kind='secrets' AND name=$3", original.tenant_id, agents.vault_name(original), 'github')
            assert token not in stored
        assert (await client.post('/v1/window-agents/worker/next', json={})).json() is None
        rows = (await client.get('/v1/window-agents/jobs')).json()
        assert {r['status'] for r in rows} == {'cancelled', 'failed'}
        assert token not in str(rows) and job['lease'] not in str(rows)


@pytest.mark.asyncio
async def test_rls_policies_install_idempotently_and_hide_other_tenants(agent_db):
    from window_agents import SCHEMA
    owner, stranger = uuid.uuid4(), uuid.uuid4()
    role = 'window_agent_' + uuid.uuid4().hex
    async with agent_db.acquire() as conn:
        await conn.execute('ALTER TABLE tank.command_threads ENABLE ROW LEVEL SECURITY')
        await conn.execute(SCHEMA)
        await conn.execute(SCHEMA)
        await conn.execute("INSERT INTO tank.window_agent_jobs(tenant_id,user_id,job_id,thread_id,repo,credential_name,prompt) VALUES($1,'alice',$2,$3,'alice/project','github','fix')", owner, uuid.uuid4(), uuid.uuid4())
        await conn.execute(f'CREATE ROLE "{role}" NOLOGIN NOSUPERUSER NOBYPASSRLS')
        try:
            await conn.execute(f'GRANT USAGE ON SCHEMA tank TO "{role}"')
            await conn.execute(f'GRANT SELECT ON tank.window_agent_jobs TO "{role}"')
            async with conn.transaction():
                await conn.execute(f'SET LOCAL ROLE "{role}"')
                await conn.execute("SELECT set_config('app.tenant_id',$1,true)", str(stranger))
                assert await conn.fetchval('SELECT count(*) FROM tank.window_agent_jobs') == 0
                await conn.execute("SELECT set_config('app.tenant_id',$1,true)", str(owner))
                assert await conn.fetchval('SELECT count(*) FROM tank.window_agent_jobs') == 1
        finally:
            await conn.execute(f'DROP OWNED BY "{role}"')
            await conn.execute(f'DROP ROLE "{role}"')


@pytest.mark.asyncio
async def test_container_runner_cancellation_stops_child(tmp_path):
    import asyncio
    import os
    import sys
    from workers.window_agent.runtime import ContainerRunner
    pidfile = tmp_path / 'pid'
    code = 'import os,sys,time; open(sys.argv[1],"w").write(str(os.getpid())); time.sleep(60)'
    stop = 'import os,sys,signal; os.kill(int(open(sys.argv[1]).read()),signal.SIGTERM)'
    runner = ContainerRunner()
    running = asyncio.create_task(runner([sys.executable, '-c', code, str(pidfile)], timeout_s=90,
                                         kill=[sys.executable, '-c', stop, str(pidfile)]))
    try:
        for _ in range(500):
            if pidfile.exists():
                break
            await asyncio.sleep(.01)
        assert pidfile.exists()
        pid = int(pidfile.read_text())
        running.cancel()
        with pytest.raises(asyncio.CancelledError):
            await asyncio.wait_for(running, 15)
        with pytest.raises(ProcessLookupError):
            os.kill(pid, 0)
    finally:
        if not running.done():
            running.cancel()
            await asyncio.gather(running, return_exceptions=True)
