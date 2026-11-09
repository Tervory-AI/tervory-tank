"""Real typed Tisan dispatch and refusal evidence on the proposed Tank adapter."""
import copy
import json
import uuid

import httpx
from chassis.user_assertion import HEADER, SignedUser, sign_assertion
from tisan_fixture import KEY, USER_A, USER_B


async def assert_task_boundary(tisan):
    import main
    from chassis.task_contract import check_receipt
    first = await tisan.plan('placeholder typed adapter boundary')
    paths = [event[:2] for event in tisan.events]
    assert ('placeholder-tank', '/v1/agents/tisan/delegate') in paths
    assert ('tisan-brain', '/tasks/plan') in paths
    assert not any('tiger' in str(event) for event in tisan.events)
    receipt = first['brain_receipt']
    assert receipt['tenant_id'] == tisan.stack.tenant and receipt['user_id'] == USER_A
    assert receipt['region'] == 'us-east' and receipt['task_type'] == 'tisan.plan'
    # Preserve real costs/ledger evidence while exercising every typed scope guard.
    for field, wrong in [('tenant_id', tisan.stack.other_tenant), ('user_id', USER_B),
                         ('run_id', str(uuid.uuid4())), ('task_type', 'agent.tiger.think'),
                         ('room', 'tiger'), ('paid_calls', 99), ('ledger_ids', ['invalid']),
                         ('cost_usd', -1), ('tokens_in', -1)]:
        data = {'receipt': {**copy.deepcopy(receipt), field: wrong}}
        try:
            check_receipt(data, tisan.stack.tenant, USER_A, receipt['run_id'], 'tisan')
        except (ValueError, TypeError, KeyError):
            pass
        else:
            raise AssertionError('Receipt guard accepted ' + field)
    before = len(tisan.provider_calls)
    target = '/v1/agents/tisan/delegate'
    body = {'tenant_id': tisan.stack.tenant, 'user_id': USER_A, 'run_id': str(uuid.uuid4()),
            'task_key': 'tisan.plan', 'input': {'request': 'placeholder boundary task',
            'contract': tisan.runtime.builder.manifest()}, 'recall': []}
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=main.app), base_url='http://placeholder-tank') as http:
        async def attempt(*, key=KEY, product='tisan', user=USER_A, region='us-east', change=None, signed=True):
            content = json.dumps({**body, **(change or {})}).encode()
            actor = SignedUser(tisan.stack.tenant, user, 'member')
            headers = {'X-Tank-Key': key, 'Content-Type': 'application/json', 'X-Home-Region': region}
            if signed:
                headers[HEADER] = sign_assertion(product, actor, 'POST', target, content, key=key)
            return await http.post(target, content=content, headers=headers)
        assert (await attempt(key='placeholder-tiger-key')).status_code == 401
        assert (await attempt(product='tiger')).status_code == 401
        assert (await attempt(signed=False)).status_code == 401
        assert (await attempt(user=USER_B)).status_code == 403
        assert (await attempt(region='za')).status_code == 403
        assert (await attempt(change={'task_key': 'tiger.margin'})).status_code == 422
        with tisan.monkeypatch.context() as patch:
            patch.setenv('TISAN_BRAIN_ENABLED', 'false')
            assert (await attempt()).status_code == 409
        with tisan.monkeypatch.context() as patch:
            patch.setenv('TISAN_BRAIN_URL', 'http://placeholder-foreign:8001')
            assert (await attempt()).status_code == 503
    assert len(tisan.provider_calls) == before
