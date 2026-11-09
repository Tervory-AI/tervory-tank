"""New legal leaves enter the shipped signed Tank proxy and room handlers."""
from uuid import UUID, uuid4

import pytest

import command
from zenas_harness import USER_A, zenas as _zenas

zenas = _zenas


@pytest.mark.asyncio
async def test_new_command_leaves_reach_shipped_handlers_with_signed_identity(zenas):
    owner = command.Actor(UUID(zenas.stack.tenant), USER_A, False, frozenset({'zenas'}))
    # The existing plain-language task is standard/off-peak in production.
    # Only this disposable fixture selects its external fake provider urgently.
    import paid_steps
    task = 'zenas.plain_language'
    step = paid_steps.model_step(task, 'llama-small', agent='zenas')
    async with zenas.stack.records.pool.acquire() as conn:
        await conn.execute("INSERT INTO tank.policy(task_type,tenant_id,model,priority,cache_scope,system_prompt) VALUES($1,$2,'llama-small','urgent','none','placeholder legal fixture')", task, owner.tenant_id)
        await paid_steps.register(conn, step, 'zenas', 'model', 'placeholder fixture', task=task, model='llama-small')
        await conn.execute("INSERT INTO tank.paid_step_settings(tenant_id,step_id,mode,updated_by) VALUES($1,$2,'auto','placeholder-admin') ON CONFLICT DO NOTHING", owner.tenant_id, step)
    samples = {
        'zenas.receipts': ({}, 200),
        'zenas.retrieve': ({'jurisdiction': 'us', 'query': zenas.body['question']}, 200),
        'zenas.apply': ({'card_id': str(uuid4())}, 422),
        'zenas.compose': ({'card_id': str(uuid4())}, 422),
        'zenas.plain': ({'text': 'Written notice is required.', 'jurisdiction': 'us'}, 200),
    }
    for tool, (args, expected) in samples.items():
        method, path, params, body = command.adapter_request(command.PlannedAction(tool=tool, arguments=args), owner)
        assert params == {'tenant_id': zenas.stack.tenant, 'home_region': 'us-east'}
        before = len(zenas.model.calls)
        response = await zenas.request(method, path.removeprefix('/v1/zenas'), body=body)
        assert response.status_code == expected, (tool, response.text)
        if expected == 422:
            assert response.json()['detail']
            assert not response.json().get('ok', False)
            assert len(zenas.model.calls) == before, 'Unknown legal card must never cause a model call'
        if tool == 'zenas.receipts':
            assert response.json() == {'receipts': []}
