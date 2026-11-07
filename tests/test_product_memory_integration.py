"""Collected gates exercise current Hermes SQL/Qdrant, not unapplied patch copies."""
import os
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

import httpx
import pytest
import pytest_asyncio
from qdrant_client import QdrantClient
from chassis.memory import MemoryClient
from hermes import record_schema, records as records_module
from hermes.records import Records
from hermes.record_index import RecordIndex
from hermes.service import create_app
from hermes.store import InMemoryStore
from hermes.user_scope import wide_kinds
from test_agent_memory_records import memory as database_fixture, Encoder

memory = database_fixture
ROOT = Path(__file__).resolve().parents[1]


@pytest_asyncio.fixture(params=['opli', 'trigger', 'workspace'])
async def product(request, memory, monkeypatch):
    name = request.param
    prefix = 'sync_' + uuid4().hex[:12] + '_'
    original = record_schema.schema_for
    def isolated(agent):
        return original(prefix + agent)
    monkeypatch.setattr(record_schema, 'schema_for', isolated)
    monkeypatch.setattr(records_module, 'schema_for', isolated)
    encoder = Encoder()
    index = RecordIndex(QdrantClient(':memory:'), 4)
    records = Records(memory.pool, index, encoder, 'placeholder-encoder', [name])
    await records.setup()
    for key in tuple(os.environ):
        if key.startswith('TANK_KEY_'):
            monkeypatch.delenv(key)
    key = 'placeholder-' + name + '-agent-key'
    monkeypatch.setenv('TANK_KEY_' + name.upper(), key)
    monkeypatch.setenv('TANK_API_KEY', 'placeholder-shared-key')
    monkeypatch.setenv('HERMES_URL', 'http://placeholder-hermes')
    app = create_app(InMemoryStore(), encoder, records=records)
    seen = []
    async def capture(req):
        seen.append(req)
    try:
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url='http://placeholder-hermes',
                                     event_hooks={'request': [capture]}) as http:
            if name == 'opli':
                from agents.opli.gates_memory import production_memory
                client = production_memory(http=http)
            elif name == 'workspace':
                from integrations.workspace.memory_client import build_workspace_memory_client
                client = build_workspace_memory_client(http=http)
            else:
                client = MemoryClient('http://placeholder-hermes', key, name, http)
            yield SimpleNamespace(name=name, client=client, http=http, records=records,
                tenant=memory.tenant, other=memory.other, key=key, seen=seen, encoder=encoder)
    finally:
        async with memory.pool.acquire() as conn:
            await conn.execute('DROP SCHEMA ' + records.schema(name) + ' CASCADE')
        index.client.close()


@pytest.mark.asyncio
async def test_personal_recall_list_get_forget_and_tenant_isolation(product):
    p = product
    a, b = 'placeholder-user-a', 'placeholder-user-b'
    async def save(user, tenant):
        return await p.client.remember(tenant, 'placeholder private ' + user, p.name + '.receipt',
            'placeholder-source', user_id=user)
    row_a, row_b, foreign = await save(a, p.tenant), await save(b, p.tenant), await save(a, p.other)
    for user, own, other in ((a, row_a, row_b), (b, row_b, row_a)):
        for rows in (await p.client.recall(p.tenant, 'placeholder', user_id=user),
                     await p.client.records(p.tenant, user_id=user)):
            ids = {row['id'] for row in rows}
            assert own['id'] in ids
            assert other['id'] not in ids and foreign['id'] not in ids
        headers = {'X-Tank-Key': p.key}
        params = {'tenant_id': p.tenant, 'user_id': user}
        assert (await p.http.get('/records/' + own['id'], params=params, headers=headers)).status_code == 200
        assert (await p.http.get('/records/' + other['id'], params=params, headers=headers)).status_code == 404
        with pytest.raises(RuntimeError, match='hermes answered 404'):
            await p.client.forget(other['id'], p.tenant, user_id=user)
    assert await p.client.records(p.tenant) == []
    await p.client.forget(row_a['id'], p.tenant, user_id=a)
    assert await p.client.records(p.tenant, user_id=a) == []
    assert {r['id'] for r in await p.client.records(p.tenant, user_id=b)} == {row_b['id']}
    assert all('/v1/memory' not in str(req.url) for req in p.seen)
    assert all(req.headers['X-Tank-Key'] == p.key for req in p.seen)


@pytest.mark.asyncio
async def test_only_declared_tenant_wide_types_can_omit_owner(product):
    p = product
    with pytest.raises(ValueError, match='user_id required'):
        await p.client.remember(p.tenant, 'placeholder personal', p.name + '.receipt', 'placeholder-source')
    denied = await p.http.post('/memories', headers={'X-Tank-Key': p.key}, json={
        'tenant_id': p.tenant, 'text': 'placeholder personal', 'kind': p.name + '.receipt',
        'source': 'placeholder-source', 'meta': {'scope': 'tenant'}})
    assert denied.status_code == 422
    for kind in wide_kinds(p.name):
        row = await p.client.remember(p.tenant, 'placeholder shared', kind, 'placeholder-source', tenant_wide=True)
        for user in ('placeholder-user-a', 'placeholder-user-b'):
            assert row['id'] in {r['id'] for r in await p.client.records(p.tenant, user_id=user)}
            assert row['id'] in {r['id'] for r in await p.client.recall(p.tenant, 'placeholder shared', user_id=user)}
    assert 'workspace.project' in wide_kinds('workspace')
    assert 'opli.repo_map' in wide_kinds('opli')
    assert wide_kinds('trigger') == []


@pytest.mark.asyncio
async def test_shared_wrong_keys_and_invalid_kind_are_refused(product):
    p = product
    body = {'tenant_id': p.tenant, 'text': 'placeholder text', 'source': 'placeholder-source',
            'kind': p.name + '.receipt', 'user_id': 'placeholder-user'}
    for key, code in (('placeholder-shared-key', 403), ('placeholder-wrong-key', 401)):
        response = await p.http.post('/memories', headers={'X-Tank-Key': key}, json=body)
        assert response.status_code == code
    response = await p.http.post('/memories', headers={'X-Tank-Key': p.key}, json={**body, 'kind': 'Invalid kind'})
    assert response.status_code == 422
    assert await p.client.records(p.tenant, user_id='placeholder-user') == []


@pytest.mark.asyncio
@pytest.mark.parametrize('product', ['opli', 'workspace'], indirect=True)
async def test_product_controls_edit_and_forget_only_owned_records(product, monkeypatch):
    from importlib import import_module
    p = product
    module = import_module('agents.opli.gates_memory' if p.name == 'opli' else 'integrations.workspace.gates_memory')
    monkeypatch.setenv(p.name.upper() + '_MEMORY_ENABLED', 'true')
    a, b = 'placeholder-owner', 'placeholder-other-user'
    own = await p.client.remember(p.tenant, 'placeholder original', p.name + '.receipt', 'placeholder-source', user_id=a, meta={'reusable_result':{'answer':'placeholder stale'}})
    other = await p.client.remember(p.tenant, 'placeholder other', p.name + '.receipt', 'placeholder-source', user_id=b)
    args = dict(tenant_id=p.tenant, user_id=a)
    with pytest.raises(module.MemoryScopeError):
        await module.apply_memory_edit(p.client, memory_id=other['id'], text='placeholder forbidden', memory_control='edit', **args)
    with pytest.raises(module.MemoryScopeError):
        await module.apply_memory_forget(p.client, memory_id=other['id'], **args)
    await module.apply_memory_edit(p.client, memory_id=own['id'], text='placeholder corrected', memory_control='edit', **args)
    rows = await p.client.records(p.tenant, user_id=a)
    assert len(rows) == 1 and rows[0]['id'] == own['id'] and rows[0]['claim'] == 'placeholder corrected'
    assert rows[0]['meta']['invalidated'] and rows[0]['meta']['reusable_result'] is None
    await module.apply_memory_forget(p.client, memory_id=own['id'], **args)
    assert await p.client.records(p.tenant, user_id=a) == []
    assert {row['id'] for row in await p.client.records(p.tenant, user_id=b)} == {other['id']}


@pytest.mark.asyncio
async def test_explicit_edit_checks_sql_owner_and_preserves_create_conflicts(product, monkeypatch):
    p = product
    owner = 'placeholder-owner'
    row = await p.client.remember(p.tenant, 'placeholder original', p.name + '.receipt', 'placeholder-source', user_id=owner)
    body = dict(tenant_id=p.tenant, user_id=owner, text='placeholder changed',
                kind=p.name + '.receipt', source='placeholder-source')
    headers = {'X-Tank-Key': p.key}
    path = '/memories/' + row['id']
    for change, code in [({'user_id':'placeholder-other'},404), ({'tenant_id':p.other},404),
                         ({'user_id':None},422), ({'meta':{'user_id':'placeholder-other'}},422),
                         ({'kind':p.name+'.task'},404), ({'id':str(uuid4())},422)]:
        assert (await p.http.patch(path, json={**body, **change}, headers=headers)).status_code == code
    assert (await p.http.patch('/memories/'+str(uuid4()), json=body, headers=headers)).status_code == 404
    assert (await p.http.patch(path, json=body, headers={'X-Tank-Key':'placeholder-shared-key'})).status_code == 403
    assert (await p.http.post('/memories', json={**body,'id':row['id']}, headers=headers)).status_code == 409
    rows = await p.client.records(p.tenant, user_id=owner)
    assert len(rows) == 1 and rows[0]['claim'] == 'placeholder original'
    result = await p.http.patch(path, json=body, headers=headers)
    assert result.status_code == 200 and result.json()['id'] == row['id']
    assert result.json()['updated'] and not result.json()['index_pending']
    recalled = await p.client.recall(p.tenant, 'placeholder changed', user_id=owner)
    assert len(recalled) == 1 and recalled[0]['text'] == 'placeholder changed'
    embed = p.encoder.embed
    def unavailable(text):
        if text == 'placeholder pending correction':
            raise RuntimeError('placeholder embedding unavailable')
        return embed(text)
    monkeypatch.setattr(p.encoder, 'embed', unavailable)
    pending = await p.http.patch(path, json={**body, 'text':'placeholder pending correction'}, headers=headers)
    assert pending.status_code == 200 and pending.json()['index_pending']
    assert await p.client.recall(p.tenant, 'placeholder changed', user_id=owner) == []
    assert (await p.client.records(p.tenant, user_id=owner))[0]['claim'] == 'placeholder pending correction'
    monkeypatch.setattr(p.encoder, 'embed', embed)
    repaired = await p.http.patch(path, json=body, headers=headers)
    assert repaired.status_code == 200 and not repaired.json()['index_pending']


def test_shipped_clients_and_namespaces_match_product_sources():
    assert (ROOT/'tank/command_tools/_shared_memory.py').read_bytes() == (ROOT/'agents/_chassis/chassis/memory.py').read_bytes()
    for src, dst, old, new in [('agents/opli','tank/command_tools/_opli','agents.opli','command_tools._opli'),
                             ('integrations/workspace','tank/command_tools/_workspace','integrations.workspace','command_tools._workspace')]:
        for path in (ROOT/dst).glob('*.py'):
            assert path.read_text() == (ROOT/src/path.name).read_text().replace(old,new)


@pytest.mark.asyncio
async def test_default_off_keeps_plain_opli_task_without_memory(monkeypatch):
    from fastapi import APIRouter, FastAPI
    from unittest.mock import AsyncMock
    from integrations.tank import opli_memory
    import command as types
    for name in ('OPLI_MEMORY_ENABLED', 'TRIGGER_MEMORY_ENABLED', 'WORKSPACE_MEMORY_ENABLED', 'TRIGGER_BRAIN_ENABLED'):
        monkeypatch.delenv(name, raising=False)
    actor = types.Actor(uuid4(), 'placeholder-user', False)
    async def identity():
        return actor
    original = AsyncMock(return_value={'answer': 'placeholder plain result'})
    cmd = SimpleNamespace(router=APIRouter(), code_turn=original, CodeTurn=types.CodeTurn,
                          authorized_actor=AsyncMock(return_value=actor), identity=identity)
    def forbidden(*args):
        raise AssertionError('default-off path constructed memory')
    monkeypatch.setattr(opli_memory, '_memory_client', forbidden)
    opli_memory.install(cmd)
    app = FastAPI()
    app.include_router(cmd.router)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url='http://placeholder') as http:
        response = await http.post('/opli/code-turn', json={'thread_id': str(uuid4()), 'text': 'placeholder task'})
    assert response.status_code == 200 and response.json() == {'answer': 'placeholder plain result'}
    assert original.await_count == 1
    monkeypatch.syspath_prepend(str(ROOT / 'agents'))
    from trigger.trigger_brain import brain_enabled
    from trigger.gates_memory import memory_enabled
    assert not brain_enabled() and not memory_enabled()


@pytest.mark.asyncio
async def test_default_off_keeps_workspace_task_without_memory(monkeypatch):
    from unittest.mock import AsyncMock
    from integrations.tank import workspace
    monkeypatch.delenv('WORKSPACE_MEMORY_ENABLED', raising=False)
    def forbidden(*args):
        raise AssertionError('default-off path constructed memory')
    monkeypatch.setattr(workspace, '_workspace_memory', forbidden)
    expected = {'id': str(uuid4()), 'status': 'queued'}
    main = SimpleNamespace(TaskCreate=lambda **kwargs: kwargs, Message=lambda **kwargs: kwargs,
                           create_task=AsyncMock(return_value=expected))
    actor = SimpleNamespace(tenant_id=uuid4(), user_id='placeholder-user')
    args = workspace.Create(title='placeholder task', request='placeholder input', memory_control='edit')
    result = await workspace._run_task_create_with_memory(actor, args, main)
    assert result == expected and main.create_task.await_count == 1
