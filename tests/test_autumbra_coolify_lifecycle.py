"""Offline Enforce API contract: MockTransport only, no Docker or provider calls."""
import json
import re
import sys
from types import SimpleNamespace
import uuid
from pathlib import Path
from unittest.mock import AsyncMock

import httpx
import pytest
import yaml
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

import command
import ghost_routes
import trigger_routes
from agents.ghost import enforce_lifecycle as lifecycle
from agents.ghost.app import create_app

A = '11111111-1111-4111-8111-111111111111'
B = '22222222-2222-4222-8222-222222222222'
TOKEN = 'placeholder-coolify-token'
ROOT = Path(__file__).resolve().parents[1]


def owned(tenant, app_uuid):
    return {'name': lifecycle.project_name(tenant), 'uuid': app_uuid, 'status': 'exited',
            'description': 'autumbra-enforce:' + tenant, 'build_pack': 'dockercompose',
            'git_repository': 'https://github.com/Tervory-AI/tervory-tank.git',
            'docker_compose_location': '/agents/ghost/docker-compose.enforce.yml'}


class FakeAPI:
    def __init__(self):
        self.rows = []
        self.calls = []
        self.failure = None
        self.failure_method = None

    def __call__(self, request):
        self.calls.append(request)
        assert request.headers['Authorization'] == 'Bearer ' + TOKEN
        assert TOKEN not in str(request.url) and TOKEN.encode() not in request.content
        path = request.url.path.removeprefix('/api/v1')
        if request.method == 'GET':
            assert path == '/applications'  # No settings, env, logs, deployment reads.
            return httpx.Response(200, json=self.rows)
        if self.failure and (self.failure_method is None or self.failure_method == request.method):
            if self.failure == 'timeout':
                raise httpx.ReadTimeout('placeholder timeout', request=request)
            return httpx.Response(self.failure, json={'error': TOKEN})
        if request.method == 'POST':
            body = json.loads(request.content)
            row = {**body, 'uuid': 'placeholder-app', 'status': 'exited'}
            self.rows.append(row)
            return httpx.Response(201, json={'uuid': row['uuid']})
        if request.method == 'DELETE':
            self.rows = [r for r in self.rows if r['uuid'] != path.split('/')[-1]]
            return httpx.Response(200, json={'message': 'placeholder deleted'})
        assert request.method == 'PATCH' and path.endswith('/envs/bulk')
        # Deliberately not JSON: no response environment value may be decoded.
        return httpx.Response(201, content=b'placeholder acknowledgement')


def backend(http):
    return lifecycle.CoolifyEnforceBackend(
        lifecycle.Coolify(http, 'https://placeholder.invalid', TOKEN),
        project='placeholder-project', server='placeholder-test-server',
        environment='placeholder-test', github_app='placeholder-source')


@pytest.mark.asyncio
async def test_create_four_values_only_and_no_deploy_or_secret_leak(caplog):
    caplog.set_level("DEBUG")
    api = FakeAPI()
    api.rows = [{'name': lifecycle.project_name(B), 'uuid': 'placeholder-other', 'status': 'exited'},
                {'name': 'placeholder-unrelated', 'uuid': 'placeholder-unrelated', 'status': 'exited'}]
    async with httpx.AsyncClient(transport=httpx.MockTransport(api), trust_env=False) as http:
        service = backend(http)
        # A stale/untrusted count is ignored at the mutation boundary.
        receipt = await service.create(lifecycle.plan_create(A, existing_count=999))
        assert receipt['outcome'] == 'created'
        assert len(await service.list()) == 2
    create = next(r for r in api.calls if r.method == 'POST')
    body = json.loads(create.content)
    assert body == {'project_uuid': 'placeholder-project', 'server_uuid': 'placeholder-test-server',
                    'environment_name': 'placeholder-test', 'github_app_uuid': 'placeholder-source',
                    'git_repository': 'https://github.com/Tervory-AI/tervory-tank.git',
                    'git_branch': 'main', 'build_pack': 'dockercompose', 'name': lifecycle.project_name(A),
                    'description': 'autumbra-enforce:' + A,
                    'docker_compose_location': '/agents/ghost/docker-compose.enforce.yml',
                    'instant_deploy': False, 'is_auto_deploy_enabled': False}
    patch = next(r for r in api.calls if r.method == 'PATCH')
    env = json.loads(patch.content)['data']
    assert {r['key']: r['value'] for r in env} == {
        'TENANT_ID': A, 'ENFORCE_DATA_VOLUME': lifecycle.volume_name(A),
        'THREAT_PAYLOAD_QUEUE_VOLUME': lifecycle.queue_name(A), 'ENFORCE_NETWORK_NAME': lifecycle.network_name(A)}
    assert len(env) == 4
    assert TOKEN not in json.dumps(receipt) + caplog.text
    assert set(receipt['founder_fills']) == {'AUTUMBRA_EDGE_CREDENTIAL', 'AUTUMBRA_UNDO_TOKEN_SECRET',
        'SITE_NAME', 'CLOUDFLARE_API_TOKEN_ENFORCE', 'AUTUMBRA_HEALTH_SECRET'}


@pytest.mark.asyncio
async def test_duplicate_refused_and_cap_uses_coolify_count(monkeypatch):
    api = FakeAPI()
    api.rows = [{'name': lifecycle.project_name(B), 'uuid': 'placeholder-other', 'status': 'exited'}]
    async with httpx.AsyncClient(transport=httpx.MockTransport(api)) as http:
        service = backend(http)
        assert (await service.create_plan(A))['cap']['current'] == 1
        monkeypatch.setattr(lifecycle, 'DEFAULT_CONTAINER_CAP', 1)
        with pytest.raises(RuntimeError):
            await service.create(lifecycle.plan_create(A, existing_count=0))
        with pytest.raises(lifecycle.Refused, match='already exists'):
            await service.create(lifecycle.plan_create(B, existing_count=0))
    assert all(r.method == 'GET' for r in api.calls)


@pytest.mark.asyncio
async def test_destroy_exact_tenant_and_absent():
    api = FakeAPI()
    api.rows = [owned(A, 'placeholder-a'),
                owned(B, 'placeholder-b')]
    async with httpx.AsyncClient(transport=httpx.MockTransport(api)) as http:
        service = backend(http)
        assert (await service.destroy(lifecycle.plan_destroy(A)))['outcome'] == 'destroyed'
        assert (await service.destroy(lifecycle.plan_destroy(A)))['outcome'] == 'absent'
    deletes = [r for r in api.calls if r.method == 'DELETE']
    assert len(deletes) == 1 and deletes[0].url.path.endswith('/placeholder-a')
    assert dict(deletes[0].url.params) == {'delete_configurations': 'true', 'delete_volumes': 'false',
                                         'delete_connected_networks': 'true', 'docker_cleanup': 'false'}
    assert [r['uuid'] for r in api.rows] == ['placeholder-b']


@pytest.mark.asyncio
@pytest.mark.parametrize('action', ['create', 'destroy'])
@pytest.mark.parametrize('failure', ['timeout', 500, 503])
async def test_ambiguous_mutation_unknown_no_retry(action, failure, caplog):
    caplog.set_level("DEBUG")
    api = FakeAPI()
    api.failure = failure
    if action == 'destroy':
        api.rows = [owned(A, 'placeholder-a')]
    async with httpx.AsyncClient(transport=httpx.MockTransport(api)) as http:
        service = backend(http)
        plan = lifecycle.plan_create(A, existing_count=0) if action == 'create' else lifecycle.plan_destroy(A)
        result = await getattr(service, action)(plan)
    assert result['outcome'] == 'unknown'
    assert len([r for r in api.calls if r.method != 'GET']) == 1
    assert TOKEN not in json.dumps(result) + caplog.text


def test_real_compose_isolation_and_dynamic_founder_names(tmp_path, monkeypatch):
    assert lifecycle.DEFAULT_CONTAINER_CAP is None
    compose = lifecycle.COMPOSE_PATH.read_text()
    all_names = set(re.findall(r'\$\{([A-Z_]+)', compose))
    plans = [lifecycle.plan_create(t, existing_count=0) for t in (A, B)]
    inventories = []
    for plan in plans:
        settings = lifecycle.CoolifyEnforceBackend.settings_for(plan)
        assert set(lifecycle.CoolifyEnforceBackend.founder_fills(plan)) == all_names - settings.keys()
        rendered = re.sub(r'\$\{([A-Z_]+)(?::-[^}]*)?\}', lambda m: settings.get(m[1], ''), compose)
        doc = yaml.safe_load(rendered)
        assert {'egress-proxy', 'health-observer', 'health-egress-proxy'} <= doc['services'].keys()
        # Unnamed networks are Compose project-scoped; explicit names are rendered.
        inventories.append({plan['project']} | {v.get('name', plan['project'] + '_' + k)
            for group in ('volumes', 'networks') for k, v in doc[group].items()})
    assert inventories[0].isdisjoint(inventories[1])
    changed = tmp_path / 'placeholder-compose.yml'
    changed.write_text(compose + '\n# ${PLACEHOLDER_FUTURE_SETTING}\n')
    monkeypatch.setattr(lifecycle, 'COMPOSE_PATH', changed)
    assert 'PLACEHOLDER_FUTURE_SETTING' in lifecycle.CoolifyEnforceBackend.founder_fills(plans[0])
    assert 'COPY tisan/promotion.py /app/enforce_coolify.py' in (ROOT / 'agents/ghost/Dockerfile').read_text()


def test_unset_settings_fixture_routes_unchanged(tmp_path, monkeypatch):
    for setting in lifecycle.COOLIFY_SETTINGS:
        monkeypatch.delenv(setting, raising=False)
    monkeypatch.setenv('TANK_KEY', 'placeholder-tank-key')
    monkeypatch.setenv('DATA_DIR', str(tmp_path))
    monkeypatch.delenv('AUTUMBRA_FIXTURE_COMPOSE_ROOT', raising=False)
    with TestClient(create_app()) as client:
        headers = {'X-Tank-Key': 'placeholder-tank-key'}
        body = {'tenant_id': A, 'execute': True}
        result = client.post('/ghost/autumbra/enforce/plan-create', headers=headers, json=body)
        assert result.status_code == 422 and result.json()['detail'] == 'Fixture compose root is not configured.'
        monkeypatch.setenv('AUTUMBRA_FIXTURE_COMPOSE_ROOT', str(tmp_path / 'placeholder-compose'))
        result = client.post('/ghost/autumbra/enforce/plan-create', headers=headers, json=body)
        assert result.status_code == 200 and result.json()['receipt']['outcome'] == 'created'
        result = client.post('/ghost/autumbra/enforce/plan-destroy', headers=headers, json=body)
        assert result.status_code == 200 and result.json()['receipt']['outcome'] == 'destroyed'


@pytest.mark.asyncio
@pytest.mark.parametrize('tool', ['list', 'create', 'destroy'])
async def test_founder_only_tools_propose_confirm_without_model(tool, monkeypatch):
    monkeypatch.setitem(sys.modules, 'main', SimpleNamespace(box_region=lambda: 'us-east'))
    monkeypatch.setenv('TERVORY_ADMIN_USER_IDS', 'placeholder-founder')
    actor = command.Actor(uuid.UUID(A), 'placeholder-founder', True)
    monkeypatch.setattr(command, 'authorized_actor', AsyncMock(side_effect=lambda a: a))
    monkeypatch.setattr(trigger_routes, 'code_receipt', AsyncMock(return_value=uuid.UUID(B)))
    name = 'autumbra.enforce.' + tool
    text = name if tool == 'list' else name + ' ' + B
    proposal = await command.autumbra_enforce_code_plan(actor, [{'role': 'user', 'content': text}], None)
    action = command.PlannedAction.model_validate(json.loads(proposal.content)['actions'][0])
    assert action.tool == name
    assert command.adapter_request(action, actor)[3] == (None if tool == 'list' else {'tenant_id': B})
    member = command.Actor(uuid.UUID(A), 'placeholder-member', False, tenant_admin=True)
    with pytest.raises(HTTPException) as error:
        await command.autumbra_enforce_code_plan(member, [{'role': 'user', 'content': text}], None)
    assert error.value.status_code == 403
    # Creating the pending proposal never calls a room.


@pytest.mark.asyncio
async def test_tank_admin_boundary_and_list_receipt(monkeypatch):
    app = FastAPI()
    app.include_router(ghost_routes.router)
    monkeypatch.setenv('TANK_API_KEY', 'placeholder-workspace-key')
    monkeypatch.setenv('TERVORY_ADMIN_USER_IDS', 'placeholder-founder')
    room = AsyncMock(return_value=httpx.Response(200, json={'applications': []}))
    actor = command.Actor(uuid.UUID(A), 'placeholder-founder', True)
    monkeypatch.setattr(command, 'identity', AsyncMock(return_value=actor))
    monkeypatch.setattr(ghost_routes, 'call_room', room)
    receipt = AsyncMock(return_value=uuid.UUID(B))
    monkeypatch.setattr(trigger_routes, 'code_receipt', receipt)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url='http://placeholder') as client:
        headers = {'X-Tank-Key': 'placeholder-workspace-key', 'X-Tervory-Tenant': A}
        for action in ('list', 'create', 'destroy'):
            path = '/v1/ghost/autumbra/enforce/' + action
            method = 'GET' if action == 'list' else 'POST'
            denied = await client.request(method, path, headers=headers, json=None if action == 'list' else {'tenant_id': B})
            assert denied.status_code == 404
        assert not room.called
        headers['X-Tervory-Admin'] = 'placeholder-founder'
        result = await client.get('/v1/ghost/autumbra/enforce/list', headers=headers)
        assert result.json()['cost_usd'] == 0 and result.json()['ledger_id'] == B
        receipt.assert_awaited_once_with(uuid.UUID(A), 'autumbra.enforce.list', agent='ghost')
        from trigger_commands import CONFIRMED
        for action in ('create', 'destroy'):
            room.reset_mock()
            path = '/v1/ghost/autumbra/enforce/' + action
            result = await client.post(path, headers=headers, json={'tenant_id': B})
            assert result.status_code == 409 and not room.called
            room.return_value = httpx.Response(200, json={'receipt': {'outcome': 'created' if action == 'create' else 'destroyed'}})
            token = CONFIRMED.set((actor.tenant_id, actor.user_id, uuid.UUID(B), 'autumbra.enforce.' + action, {'tenant_id': B}))
            try:
                result = await client.post(path, headers=headers, json={'tenant_id': B})
            finally:
                CONFIRMED.reset(token)
            assert result.status_code == 200 and result.json()['cost_usd'] == 0
            assert room.call_args.kwargs['body'] == {'tenant_id': B, 'execute': True}


@pytest.mark.asyncio
async def test_configured_room_uses_live_count_and_requires_room_key(tmp_path, monkeypatch):
    for setting in lifecycle.COOLIFY_SETTINGS:
        monkeypatch.setenv(setting, 'placeholder-setting')
    monkeypatch.setenv('TANK_KEY', 'placeholder-room-key')
    monkeypatch.setenv('DATA_DIR', str(tmp_path))
    api = FakeAPI()
    api.rows = [owned(B, 'placeholder-b')]
    async with httpx.AsyncClient(transport=httpx.MockTransport(api)) as http:
        service = backend(http)
        monkeypatch.setattr(lifecycle.CoolifyEnforceBackend, 'from_env', classmethod(lambda cls, _: service))
        with TestClient(create_app()) as client:
            path = '/ghost/autumbra/enforce/'
            headers = {'X-Tank-Key': 'placeholder-room-key'}
            assert client.get(path + 'list').status_code == 404
            assert not api.calls
            result = client.post(path + 'plan-create', headers=headers,
                                 json={'tenant_id': A, 'existing_count': 999, 'execute': True})
            assert result.status_code == 200
            assert result.json()['plan']['cap']['current'] == 1
            assert result.json()['receipt']['outcome'] == 'created'
            assert len(client.get(path + 'list', headers=headers).json()['applications']) == 2
            duplicate = client.post(path + 'plan-create', headers=headers,
                                    json={'tenant_id': A, 'existing_count': 0, 'execute': True})
            assert duplicate.status_code == 422
            assert len([r for r in api.calls if r.method == 'POST']) == 1
            result = client.post(path + 'plan-destroy', headers=headers, json={'tenant_id': A, 'execute': True})
            assert result.json()['receipt']['outcome'] == 'destroyed'


@pytest.mark.asyncio
async def test_concurrent_create_same_tenant_is_refused_after_first():
    import asyncio
    api = FakeAPI()

    async def yield_before_api(request):
        await asyncio.sleep(0)
        return api(request)

    async with httpx.AsyncClient(transport=httpx.MockTransport(yield_before_api)) as http:
        service = backend(http)
        plan = lifecycle.plan_create(A, existing_count=0)
        results = await asyncio.gather(service.create(plan), service.create(plan), return_exceptions=True)
    assert sum(isinstance(r, dict) and r['outcome'] == 'created' for r in results) == 1
    assert sum(isinstance(r, lifecycle.Refused) for r in results) == 1
    assert len([r for r in api.calls if r.method == 'POST']) == 1


def test_coolify_setting_messages_keep_tisan_defaults():
    with httpx.Client() as unused:
        with pytest.raises(lifecycle.Refused, match='TISAN_COOLIFY_URL'):
            lifecycle.Coolify(unused, 'http://placeholder.invalid', TOKEN)
        with pytest.raises(lifecycle.Refused, match='AUTUMBRA_COOLIFY_URL'):
            lifecycle.Coolify(unused, 'http://placeholder.invalid', TOKEN,
                             url_setting='AUTUMBRA_COOLIFY_URL', token_setting='AUTUMBRA_COOLIFY_TOKEN')


@pytest.mark.asyncio
async def test_foreign_resource_is_never_deleted():
    api = FakeAPI()
    api.rows = [{'name': lifecycle.project_name(A), 'uuid': 'placeholder-foreign', 'status': 'exited'}]
    async with httpx.AsyncClient(transport=httpx.MockTransport(api)) as http:
        with pytest.raises(lifecycle.Refused, match='not created by Autumbra'):
            await backend(http).destroy(lifecycle.plan_destroy(A))
    assert all(r.method == 'GET' for r in api.calls)


@pytest.mark.asyncio
@pytest.mark.parametrize('method,outcome', [('POST', 'refused'), ('PATCH', 'created_unconfigured')])
async def test_definite_refusal_classification(method, outcome):
    api = FakeAPI()
    api.failure, api.failure_method = 422, method
    async with httpx.AsyncClient(transport=httpx.MockTransport(api)) as http:
        result = await backend(http).create(lifecycle.plan_create(A, existing_count=0))
    assert result['outcome'] == outcome
    if method == 'PATCH':
        assert result['uuid'] == 'placeholder-app'


@pytest.mark.asyncio
@pytest.mark.parametrize('outcome', ['unknown', 'refused', 'created_unconfigured'])
async def test_uncertain_outcome_is_not_a_success(outcome):
    actor = command.Actor(uuid.UUID(A), 'placeholder-founder', True)
    with pytest.raises(HTTPException) as error:
        await ghost_routes.enforce_write_result(httpx.Response(200, json={'receipt': {'outcome': outcome}}), actor, 'autumbra.enforce.create')
    assert error.value.status_code == 409
    assert error.value.detail == 'Enforce outcome ' + outcome + '; check Coolify before repeating'


@pytest.mark.asyncio
async def test_redirect_is_not_followed():
    calls = []
    def redirect(request):
        calls.append(request)
        return httpx.Response(302, headers={'Location': 'https://placeholder-other.invalid'})
    async with httpx.AsyncClient(transport=httpx.MockTransport(redirect)) as http:
        with pytest.raises(lifecycle.Refused):
            await backend(http).list()
    assert len(calls) == 1


def test_watch_has_no_lifecycle_control_plane_settings():
    compose = yaml.safe_load((ROOT / 'agents/ghost/docker-compose.yml').read_text())
    for service in ('agent-ghost', 'ghost-browser'):
        assert set(lifecycle.COOLIFY_SETTINGS).isdisjoint(compose['services'][service]['environment'])


@pytest.mark.asyncio
@pytest.mark.parametrize('field', ['description', 'git_repository', 'build_pack', 'docker_compose_location'])
async def test_missing_provenance_field_refuses_delete(field):
    api = FakeAPI()
    row = owned(A, 'placeholder-owned')
    row.pop(field)
    api.rows = [row]
    async with httpx.AsyncClient(transport=httpx.MockTransport(api)) as http:
        with pytest.raises(lifecycle.Refused, match='not created by Autumbra'):
            await backend(http).destroy(lifecycle.plan_destroy(A))
    assert all(r.method == 'GET' for r in api.calls)


@pytest.mark.asyncio
@pytest.mark.parametrize('verb', ['create', 'destroy'])
async def test_mutation_dispatch_uses_confirmed_card_path(verb, monkeypatch):
    from contextlib import asynccontextmanager
    import trigger_commands
    monkeypatch.setenv('TERVORY_ADMIN_USER_IDS', 'placeholder-founder')
    actor = command.Actor(uuid.UUID(A), 'placeholder-founder', True)
    action = command.PlannedAction(tool='autumbra.enforce.' + verb, arguments={'tenant_id': B})
    card_id = str(uuid.uuid4())
    thread = uuid.uuid4()
    card = {'card_id': card_id, 'summary': action.tool, 'status': 'executing', 'payload': action.model_dump()}
    state = {'cards': {card_id: card}}

    @asynccontextmanager
    async def editing(*args):
        yield None, {}, state

    @asynccontextmanager
    async def acquire():
        yield None

    monkeypatch.setattr(command, 'authorized_actor', AsyncMock(return_value=actor))
    monkeypatch.setattr(command, 'editing', editing)
    monkeypatch.setattr(command, 'db', lambda: SimpleNamespace(acquire=acquire))
    monkeypatch.setattr(command, 'owned', AsyncMock(return_value={'state': state}))
    for name in ('step', 'event', 'refresh_action_receipts'):
        monkeypatch.setattr(command, name, AsyncMock())
    confirmed = AsyncMock(return_value=(200, {'ledger_id': B, 'cost_usd': 0}))
    direct = AsyncMock(side_effect=AssertionError('placeholder direct dispatch forbidden'))
    monkeypatch.setattr(trigger_commands, 'dispatch_confirmed', confirmed)
    monkeypatch.setattr(command, 'dispatch_action', direct)
    result = await command.execute_card(thread, actor, card_id, action)
    assert result['status'] == 'confirmed'
    confirmed.assert_awaited_once_with(action, actor, thread, card_id)
    direct.assert_not_called()


def test_isolated_service_seal():
    from agents.ghost.enforce_api import create_app as create_control
    compose = yaml.safe_load((ROOT / 'agents/ghost/docker-compose.yml').read_text())
    service = compose['services']['enforce-lifecycle']
    assert set(lifecycle.COOLIFY_SETTINGS) <= service['environment'].keys()
    assert service['networks'] == ['gw']
    assert not service.get('ports') and not service.get('expose') and not service.get('volumes')
    assert service['read_only'] and service['cap_drop'] == ['ALL']
    assert service['security_opt'] == ['no-new-privileges:true']
    assert service['mem_limit'] and service['cpus']
    main = yaml.safe_load((ROOT / 'docker-compose.yml').read_text())
    assert 'tervory-enforce-control' not in main['networks']
    for services in (main['services'], compose['services']):
        for name, spec in services.items():
            assert ('AUTUMBRA_LIFECYCLE_KEY' in (spec.get('environment') or {})) == (name in {'tank', 'enforce-lifecycle'})
    for name in ('agent-ghost', 'ghost-browser'):
        assert not set(lifecycle.COOLIFY_SETTINGS) & compose['services'][name]['environment'].keys()
    with TestClient(create_control()) as client:
        assert client.get('/ghost/autumbra/enforce/list').status_code == 401
        assert client.get('/ghost/autumbra/settings').status_code == 404


@pytest.mark.asyncio
@pytest.mark.parametrize('repository', ['Tervory-AI/tervory-tank', 'https://github.com/Tervory-AI/tervory-tank', 'https://github.com/Tervory-AI/tervory-tank.git'])
async def test_same_repository_forms_and_canonical_names(repository):
    api = FakeAPI()
    api.rows = [{**owned(A, 'placeholder-owned'), 'git_repository': repository},
                {'name': lifecycle.PROJECT_PREFIX + '-' + 'a' * 36, 'uuid': 'placeholder-invalid-name'}]
    async with httpx.AsyncClient(transport=httpx.MockTransport(api)) as http:
        service = backend(http)
        assert len(await service.list()) == 1
        assert (await service.create_plan(B))['cap']['current'] == 2
        assert (await service.destroy(lifecycle.plan_destroy(A)))['outcome'] == 'destroyed'


@pytest.mark.asyncio
async def test_lifecycle_separate_hmac_key(monkeypatch):
    import hashlib
    import hmac
    import time

    from agents.ghost.enforce_api import create_app as create_control
    monkeypatch.setenv('AUTUMBRA_LIFECYCLE_KEY', 'placeholder-lifecycle-key')
    monkeypatch.setenv('TANK_KEY_GHOST', 'placeholder-watch-key')
    for setting in lifecycle.COOLIFY_SETTINGS:
        monkeypatch.delenv(setting, raising=False)
    path = '/ghost/autumbra/enforce/plan-create'
    content = json.dumps({'tenant_id': A}).encode()
    timestamp = str(int(time.time()))
    def signed(key, stamp=timestamp, data=content):
        message = f'{stamp}\nPOST\n{path}\n'.encode() + data
        return {'X-Lifecycle-Timestamp': stamp,
                'X-Lifecycle-Signature': hmac.new(key.encode(), message, hashlib.sha256).hexdigest()}
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=create_control()), base_url='http://lifecycle') as client:
        assert (await client.post(path, content=content)).status_code == 401
        assert (await client.post(path, content=content, headers={'X-Tank-Key': 'placeholder-watch-key'})).status_code == 401
        assert (await client.post(path, content=content, headers=signed('placeholder-watch-key'))).status_code == 401
        assert (await client.post(path, content=content, headers=signed('placeholder-lifecycle-key', '1'))).status_code == 401
        assert (await client.post(path, content=content + b' ', headers=signed('placeholder-lifecycle-key'))).status_code == 401
        assert (await client.post(path, content=content, headers=signed('placeholder-lifecycle-key'))).status_code == 200
        async def send(method, url, **kwargs):
            assert url == 'http://enforce-lifecycle:8000' + path
            assert 'X-Tank-Key' not in kwargs['headers']
            return await client.request(method, path, **kwargs)
        monkeypatch.setattr(ghost_routes, 'runtime', lambda: SimpleNamespace(_http=SimpleNamespace(request=send)))
        response = await ghost_routes.call_room('POST', 'ghost', path, body={'tenant_id': A})
        assert response.status_code == 200
        monkeypatch.delenv('AUTUMBRA_LIFECYCLE_KEY')
        assert (await client.post(path, content=content, headers=signed('placeholder-lifecycle-key'))).status_code == 401
