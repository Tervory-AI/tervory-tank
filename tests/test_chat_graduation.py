"""Founder graduation bar and chat savings on real Tank SQL and HTTP paths.

Only the paid provider is stubbed. All fixture traffic stays in a disposable DB.
"""
import json
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

import httpx
import pytest

import graduate
import proof
from test_tank_tenant_boundaries import boundary  # noqa: F401


@pytest.mark.asyncio
async def test_graduation_migration_preserves_custom_policies_for_two_tenants(boundary):  # noqa: F811
    b = boundary
    schema = Path('tank/schema.sql').read_text()
    async with b.pool.acquire() as conn:
        await conn.execute("DELETE FROM tank.policy_seeds WHERE name IN ('graduation-99-200-v1','command-exact-cache-v1')")
        for tenant in b.tenants:
            for task, bar, count in [('old', '.97', 30), ('custom-bar', '.98', 30), ('custom-count', '.97', 80)]:
                await conn.execute("""INSERT INTO tank.policy(tenant_id,task_type,model,eval_threshold,min_shadow_samples)
                    VALUES($1,$2,'luna',$3,$4)""", tenant, task, Decimal(bar), count)
            await conn.execute("""INSERT INTO tank.policy(tenant_id,task_type,model,cache_scope,semantic_cache)
                VALUES($1,'command.turn','luna','none',false)""", tenant)
        await conn.execute(schema)
        for tenant in b.tenants:
            for task, bar, count in [('old', '.99', 200), ('custom-bar', '.98', 30), ('custom-count', '.97', 80)]:
                row = await conn.fetchrow('SELECT * FROM tank.policy WHERE tenant_id=$1 AND task_type=$2', tenant, task)
                assert row['eval_threshold'] == Decimal(bar) and row['min_shadow_samples'] == count
            chat = await conn.fetchrow("SELECT * FROM tank.policy WHERE tenant_id=$1 AND task_type='command.turn'", tenant)
            assert chat['cache_scope'] == 'tenant' and not chat['semantic_cache']
            # A deliberate later founder edit must survive another startup.
            await conn.execute("UPDATE tank.policy SET eval_threshold=.97,min_shadow_samples=30 WHERE tenant_id=$1 AND task_type='old'", tenant)
            await conn.execute("INSERT INTO tank.policy(tenant_id,task_type,model) VALUES($1,'new','luna')", tenant)
        await conn.execute(schema)
        for tenant in b.tenants:
            for task, bar, count in [('old', '.97', 30), ('new', '.99', 200)]:
                row = await conn.fetchrow('SELECT * FROM tank.policy WHERE tenant_id=$1 AND task_type=$2', tenant, task)
                assert row['eval_threshold'] == Decimal(bar) and row['min_shadow_samples'] == count


@pytest.mark.parametrize('samples,agreement,reason', [(199, 1, 'too few shadow samples'), (200, .989, 'agreement is below the bar'), (200, .99, None)])
def test_default_bar_and_founder_approval(samples, agreement, reason):
    policy = {'model': 'luna', 'candidate_model': 'flash-lite', 'auto_promote': True}
    evidence = graduate.Evidence(samples=samples, agreement=agreement)
    now = datetime.now(timezone.utc)
    automatic = graduate.apply(policy, evidence, now)
    assert automatic.action == 'hold'
    approved = graduate.promote_if_proven(policy, evidence, now, automatic=False)
    assert approved.reason == reason
    assert approved.action == ('hold' if reason else 'promote')


@pytest.mark.asyncio
async def test_chat_exact_repeat_has_zero_cost_both_jobs_in_savings_and_tenants_sealed(boundary, monkeypatch):  # noqa: F811
    b = boundary
    from savings_defaults import initialize
    async with b.pool.acquire() as conn:
        await initialize(conn)
        # Offline comparison rates only; real startup refreshes its price book.
        await conn.execute("""INSERT INTO tank.proof_prices(model,family,input_usd,output_usd)
            VALUES('luna','openai',.0000001,.0000001),('sol','openai',.000001,.000001)
            ON CONFLICT(model) DO NOTHING""")
    sent = []

    class Provider:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            pass

        async def post(self, url, **kwargs):
            sent.append(kwargs['json'])
            return httpx.Response(200, headers={'x-litellm-response-cost': '0.000001'},
                json={'choices': [{'message': {'content': 'A local test answer.'}}],
                      'usage': {'prompt_tokens': 1000, 'completion_tokens': 100}}, request=httpx.Request('POST', url))

    monkeypatch.setattr(b.tank.httpx, 'AsyncClient', Provider)
    for index, tenant in enumerate(b.tenants):
        headers = {'X-Tervory-Tenant': str(tenant), 'X-Tervory-User': 'founder-fixture'}
        thread = (await b.client.post('/v1/command/threads', json={}, headers=headers)).json()['thread_id']
        route = f'/v1/command/threads/{thread}/turn'
        for _ in range(2):
            result = await b.client.post(route, json={'text': 'What is the purpose of this task?'}, headers=headers)
            assert result.status_code == 200 and 'event: done' in result.text, result.text
        assert len(sent) == index + 1  # Another tenant must pay its own first call.
        detail = (await b.client.get(f'/v1/command/threads/{thread}', headers=headers)).json()
        assert [r['cost_usd'] for r in detail['receipts']] == [0.000001, 0]
        async with b.pool.acquire() as conn:
            rows = await conn.fetch("""SELECT l.*,t.status,t.tenant_id AS job_tenant FROM tank.ledger l
                JOIN tank.tasks t ON t.id=l.task_id WHERE l.tenant_id=$1 ORDER BY l.ts""", tenant)
            assert len(rows) == 2 and [r['cache_hit'] for r in rows] == [False, True]
            assert all(r['job_tenant'] == tenant and r['status'] == 'done' for r in rows)
        savings = await proof.savings_snapshot(tenant)
        assert savings['total']['work_count'] == savings['total']['jobs_count'] == 2, await proof.savings_rows(tenant, datetime.now(timezone.utc), population='excluded')
        assert savings['total']['free_count'] == 1
        savings_rows = await proof.savings_rows(tenant, datetime.now(timezone.utc))
        assert len(savings_rows['rows']) == 2
    # Equivalent meaning is not an exact match, and must not reuse the answer.
    result = await b.client.post(route, json={'text': 'Tell me the purpose of this task.'}, headers=headers)
    assert 'event: done' in result.text and len(sent) == 3
    # Returning to the original question after an intervening turn keeps history.
    result = await b.client.post(route, json={'text': 'What is the purpose of this task?'}, headers=headers)
    assert 'event: done' in result.text and len(sent) == 4
    assert len(sent[-1]['messages']) > len(sent[0]['messages'])


@pytest.mark.asyncio
@pytest.mark.parametrize('change', ['attachments', 'model', 'tool-result', 'actions', 'user'])
async def test_repeat_context_changes_keep_full_request(change):
    """The cache shortcut cannot erase attachment, action, user or tool changes."""
    from types import SimpleNamespace
    from unittest.mock import AsyncMock
    from uuid import uuid4
    import command
    actor = command.Actor(uuid4(), 'client', False)
    original = [{'role': 'system', 'content': 'tools'}, {'role': 'user', 'content': 'question'}]
    current = [*original, {'role': 'assistant', 'content': 'answer'}, original[-1]]
    first = {'role': 'user', 'content': 'question', 'model': 'auto', 'attachments': []}
    state = {'messages': [first, {'role': 'assistant', 'message_id': str(uuid4()), 'repeatable': True}, dict(first)]}
    conn = SimpleNamespace(fetchval=AsyncMock(return_value=json.dumps({'messages': original})))
    if change in {'model', 'attachments'}:
        state['messages'][-1][change] = 'changed'
    elif change == 'tool-result':
        current = [{'role': 'system', 'content': 'changed'}, *current[1:]]
    elif change == 'actions':
        state['messages'][1]['repeatable'] = False
    else:
        conn.fetchval.return_value = None
    assert await command.repeat_messages(conn, state, actor, current) == current
    if conn.fetchval.called:
        assert conn.fetchval.call_args.args[-2:] == (actor.tenant_id, actor.user_id)
