"""Tisan-only real-ingress assertions shared by the owned scenario matrix."""
import asyncio
import json
import httpx
from tisan_fixture import KEY, USER_A, USER_B, FIXTURE_COST, FIXTURE_INPUT, FIXTURE_OUTPUT, corrected_plan


async def assert_foreign_state(tisan, other_tenant):
    await tisan.plan('placeholder private owner brief')
    owner = await tisan.view()
    row = next(r for r in owner['memories'] if r['kind'] == 'tisan.result')
    tenant = tisan.stack.other_tenant if other_tenant else tisan.stack.tenant
    other = await tisan.view(USER_B, tenant)
    assert row['id'] not in {r['id'] for r in other['memories']}
    before = await tisan.records()
    for method, body in (('POST', {'value': {'placeholder': 'foreign mutation'}}), ('DELETE', None)):
        denied = await tisan.control(method, '/' + row['id'], user=USER_B, tenant=tenant, body=body)
        assert denied.status_code in (401, 403, 404)
    # No personal publishing route can be invented by guessing a memory URL.
    denied = await tisan.control('POST', '/' + row['id'] + '/publish', user=USER_B, tenant=tenant, body={})
    assert denied.status_code in (401, 403, 404, 405)
    assert await tisan.records() == before


async def assert_rejected_assertion(tisan, fault):
    import time
    from product_identity import sign, User, HEADER
    await tisan.view()
    actor = User(tisan.stack.tenant, USER_A, 'founder')
    target = '/memory?tenant_id=' + tisan.stack.tenant + '&user_id=' + USER_A
    key, audience, method, body = KEY, 'tisan', 'GET', b''
    now = int(time.time())
    if fault == 'key': key = 'placeholder-wrong-key'
    if fault == 'audience': audience = 'opli'
    if fault == 'tenant': actor = User(tisan.stack.other_tenant, USER_A, 'founder')
    if fault == 'method': method = 'POST'
    if fault == 'target': target += '&placeholder=changed'
    if fault == 'body': body = b'placeholder-tampered-body'
    if fault == 'expired': now -= 61
    if fault == 'future': now += 60
    assertion = '' if fault == 'missing' else sign(audience, actor, method, target, body, key=key, now=now)
    real_target = '/memory?tenant_id=' + tisan.stack.tenant + '&user_id=' + USER_A
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=tisan.room), base_url='http://agent-tisan:8000') as raw:
        denied = await raw.get(real_target, headers={'X-Tank-Key': KEY, HEADER: assertion})
        assert denied.status_code in (401, 403, 404)


async def assert_replay_wall(tisan):
    from product_identity import sign, User, HEADER
    await tisan.plan()
    target = '/memory?tenant_id=' + tisan.stack.tenant + '&user_id=' + USER_A
    assertion = sign('tisan', User(tisan.stack.tenant, USER_A, 'founder'), 'DELETE', target, b'', key=KEY)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=tisan.room), base_url='http://agent-tisan:8000') as raw:
        responses = await asyncio.gather(*(raw.delete(target, headers={'X-Tank-Key': KEY, HEADER: assertion}) for _ in range(2)))
        assert sorted(r.status_code == 200 for r in responses) == [False, True]
        # Recreate verifier instances, retaining the real PostgreSQL nonce rows.
        tisan.runtime.app.app.state.product_nonce_stores = {}
        replay = await raw.delete(target, headers={'X-Tank-Key': KEY, HEADER: assertion})
        assert replay.status_code in (401, 403, 404)
    assert not [r for r in await tisan.records() if r['kind'] != 'tisan.memory_setting' and r['meta'].get('user_id') == USER_A]



async def assert_owner_task(tisan):
    first = await tisan.plan()
    rows = (await tisan.view())['memories']
    result = next(row for row in rows if row['kind'] == 'tisan.result')
    assert result['meta']['result'] and result['meta']['receipt']['ledger_ids']
    edited = corrected_plan(result['meta']['result'])
    await tisan.correct(result['id'], edited)
    repeat = await tisan.plan()
    assert repeat['brain_receipt']['answered_from_memory'] is True
    assert repeat['brain_receipt']['paid_calls'] == 0
    assert repeat['copy_needed'] != first['copy_needed']
    shared_before = [r for r in (await tisan.view(USER_B))['memories'] if not r['meta'].get('user_id')]
    deleted = await tisan.control('DELETE')
    assert deleted.status_code == 200 and deleted.json()['forgotten'] > 0
    assert shared_before == [r for r in (await tisan.view(USER_B))['memories'] if not r['meta'].get('user_id')]
    assert not [row for row in (await tisan.view())['memories'] if row['kind'] != 'tisan.memory_setting' and row['meta'].get('user_id') == USER_A]


async def assert_fixture_spend(tisan, record_property):
    first = await tisan.plan()
    one = await tisan.counts()
    repeat = await tisan.plan()
    two = await tisan.counts()
    receipt = repeat['brain_receipt']
    assert receipt['answered_from_memory'] and receipt['paid_calls'] == 0
    assert receipt['cost_usd'] == receipt['tokens_in'] == receipt['tokens_out'] == 0
    assert receipt['would_have_cost_usd'] == first['brain_receipt']['cost_usd'] == FIXTURE_COST
    assert one == two == {'provider_calls': 1, 'cost': FIXTURE_COST, 'tokens': FIXTURE_INPUT + FIXTURE_OUTPUT}
    await tisan.plan('placeholder changed meaningful brief')
    three = await tisan.counts()
    assert three == {'provider_calls': 2, 'cost': 2 * FIXTURE_COST, 'tokens': 2 * (FIXTURE_INPUT + FIXTURE_OUTPUT)}
    record_property('tisan_fixture_spend', json.dumps({'first': one, 'exact_repeat_increment': {'provider_calls': 0, 'cost': 0, 'tokens': 0}, 'changed_cumulative': three}))

