"""The build adapter retains founder authorization, Confirm and room identity."""
from __future__ import annotations

import importlib.util
import json
import sys
import uuid
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

import httpx
import pytest
from fastapi import HTTPException

import command

ROOT = Path(__file__).resolve().parents[1]
TENANT = uuid.UUID('11111111-1111-4111-8111-111111111111')
OTHER = uuid.UUID('22222222-2222-4222-8222-222222222222')


def load_skill():
    spec = importlib.util.spec_from_file_location('tisan_build_skill_test', ROOT / 'tank/skills/tisan.build/1.0.0/run.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def runtime(monkeypatch):
    monkeypatch.setenv('TERVORY_ADMIN_USER_IDS', 'founder')
    monkeypatch.setenv('TANK_KEY_TISAN', 'test-room-key')
    monkeypatch.setitem(sys.modules, 'main', SimpleNamespace(box_region=lambda: 'za'))


def test_build_is_founder_only_even_with_tisan_squad(runtime):
    assert 'tisan.build' in command.allowed_tools(command.Actor(TENANT, 'founder', True))
    actor = command.Actor(TENANT, 'member', False, frozenset({'tisan'}))
    assert 'tisan.build' not in command.allowed_tools(actor)
    with pytest.raises(HTTPException) as exc:
        command.validate_action(command.PlannedAction(tool='tisan.build', arguments={}), actor)
    assert exc.value.status_code == 403


def test_build_routes_to_approved_skill_and_binds_scope(runtime):
    actor = command.Actor(TENANT, 'founder', True)
    arguments = {'name': 'Test site', 'slug': 'test-site', 'brand': {}, 'plan': {'pages': []},
                 'copy': {'home/title': str(uuid.uuid4())}, 'media': {'site/logo/src': '/media/logo.png'}}
    method, path, query, body = command.adapter_request(command.PlannedAction(tool='tisan.build', arguments=arguments), actor)
    assert (method, path, query) == ('POST', '/v1/skala/tisan.build/run', {'tenant_id': str(TENANT)})
    assert body['preview'] is False and body['home_region'] == 'za'
    assert body['input']['media'] == arguments['media']
    for override in ['tenant_id', 'user_id', 'home_region', 'preview', 'model']:
        with pytest.raises(HTTPException):
            command.validate_action(command.PlannedAction(tool='tisan.build', arguments={**arguments, override: 'override'}), actor)


@pytest.mark.asyncio
async def test_build_proposal_is_pending_not_dispatched(runtime, monkeypatch):
    monkeypatch.setattr(command, 'event', AsyncMock())
    monkeypatch.setattr(command, 'step', AsyncMock())
    dispatch = AsyncMock(side_effect=AssertionError('proposal must wait for Confirm'))
    monkeypatch.setattr(command, 'dispatch_action', dispatch)
    state = {'cards': {}}
    action = command.PlannedAction(tool='tisan.build', arguments={'name': 'Test site'})
    card = await command.propose_action(None, {}, state, action, command.Actor(TENANT, 'founder', True))
    assert card['status'] == 'pending' and card['tool'] == 'tisan.build'
    dispatch.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize('foreign', [False, True])
async def test_skill_returns_copy_needed_and_rejects_foreign_job(runtime, foreign):
    job_id = str(uuid.uuid4())
    def respond(request):
        assert request.headers['X-Tervory-Tenant'] == str(TENANT)
        assert request.headers['X-Tervory-Home-Region'] == 'za'
        assert request.headers['X-Tank-Key'] == 'test-room-key'
        if request.method == 'POST':
            body = json.loads(request.content)
            assert body == {'tenant_id': str(TENANT), 'kind': 'build', 'input': {'plan': {}}}
            return httpx.Response(201, json={'id': job_id, 'tenant_id': str(TENANT), 'kind': 'build', 'status': 'queued'})
        assert request.url.params['tenant_id'] == str(TENANT)
        return httpx.Response(200, json={'id': job_id, 'tenant_id': str(OTHER if foreign else TENANT),
                                        'status': 'done', 'result': {'ok': False, 'copy_needed': [{'key': 'home/title'}]}})
    async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as http:
        ctx = SimpleNamespace(tenant_id=TENANT, http=http)
        if foreign:
            with pytest.raises(RuntimeError, match='identity mismatch'):
                await load_skill().run({'plan': {}}, ctx)
        else:
            result = await load_skill().run({'plan': {}}, ctx)
            assert result == {'ok': False, 'job_id': job_id, 'copy_needed': [{'key': 'home/title'}]}


@pytest.mark.asyncio
async def test_packaged_evals_are_deterministic_and_do_not_call_models():
    spec = importlib.util.spec_from_file_location('builder_eval_test', ROOT / 'agents/tisan/builder.py')
    builder = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(builder)
    for line in (ROOT / 'tank/skills/tisan.build/1.0.0/evals/cases.jsonl').read_text().splitlines():
        case = json.loads(line)
        tank = SimpleNamespace(route=AsyncMock(side_effect=AssertionError('eval must not call a model')))
        result = await builder.execute(case['input'], str(TENANT), tank=tank)
        assert result == case['expected']
        tank.route.assert_not_awaited()
