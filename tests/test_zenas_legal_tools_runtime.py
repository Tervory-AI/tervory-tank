"""Exercise shipped Zenas command leaves; no product patch overlay."""
import json
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import UUID, uuid4

import pytest
from fastapi import HTTPException

import command
from command_tools import zenas

TENANT = UUID('11111111-1111-4111-8111-111111111111')
TOOLS = {'zenas.receipts': {}, 'zenas.retrieve': {'jurisdiction': 'za', 'query': 'written notice'},
         'zenas.apply': {'card_id': str(uuid4())}, 'zenas.compose': {'card_id': str(uuid4())},
         'zenas.plain': {'text': 'Written notice is required.', 'jurisdiction': 'za'}}


def actor():
    return command.Actor(TENANT, 'placeholder-legal-owner', False, frozenset({'zenas'}))


@pytest.mark.asyncio
@pytest.mark.parametrize('tool,args', TOOLS.items())
async def test_shipped_planner_and_adapter_bind_verified_scope(monkeypatch, tool, args):
    import trigger_routes
    owner = actor()
    monkeypatch.setattr(command, 'authorized_actor', AsyncMock(return_value=owner))
    recorded = AsyncMock(return_value=uuid4())
    monkeypatch.setattr(trigger_routes, 'code_receipt', recorded)
    plan = await zenas.code_plan(owner, [{'role': 'user', 'content': tool+' '+json.dumps(args)}], None)
    action = command.PlannedAction(**json.loads(plan.content)['actions'][0])
    monkeypatch.setitem(__import__('sys').modules, 'main', SimpleNamespace(box_region=lambda: 'za'))
    method, path, params, body = command.adapter_request(action, owner)
    assert path.startswith('/v1/zenas/') and '/moot' not in path
    assert params == {'tenant_id': str(TENANT), 'home_region': 'za'}
    if method == 'GET':
        assert body is None
    else:
        assert body['tenant_id'] == str(TENANT) and body['home_region'] == 'za'
        assert not {'user_id', 'founder', 'provider', 'model'} & body.keys()
    recorded.assert_awaited_once_with(TENANT, 'command.turn', task_id=None, agent='zenas')
    assert command.ADAPTERS[tool].paid == (tool in {'zenas.apply', 'zenas.compose', 'zenas.plain'})


@pytest.mark.parametrize('field', ['tenant_id', 'user_id', 'home_region', 'founder', 'provider', 'model', 'paid_run_id'])
@pytest.mark.parametrize('tool,args', TOOLS.items())
def test_no_caller_identity_or_paid_override(field, tool, args):
    with pytest.raises(HTTPException) as denied:
        command.validate_action(command.PlannedAction(tool=tool, arguments={**args, field: 'foreign'}), actor())
    assert denied.value.status_code == 422


@pytest.mark.asyncio
async def test_denied_identity_and_moot_do_not_make_legal_plans(monkeypatch):
    denied = AsyncMock(side_effect=HTTPException(401, 'not_signed_in'))
    monkeypatch.setattr(command, 'authorized_actor', denied)
    with pytest.raises(HTTPException) as error:
        await zenas.code_plan(actor(), [{'role': 'user', 'content': 'zenas.receipts {}'}], None)
    assert error.value.status_code == 401
    for text in ['moot.command {}', 'zenas.moot.command {}']:
        assert await zenas.code_plan(actor(), [{'role': 'user', 'content': text}], None) is None
    outsider = command.Actor(TENANT, 'placeholder-outsider', False)
    for tool, args in TOOLS.items():
        with pytest.raises(HTTPException) as error:
            command.validate_action(command.PlannedAction(tool=tool, arguments=args), outsider)
        assert error.value.status_code == 403
