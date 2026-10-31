"""Offline acceptance: real command HTTP/SQL, fake worker progress, no model calls."""
import asyncio
import json
import os
import subprocess
from pathlib import Path
import uuid

import pytest

from test_command import api, command_pool, runtime, TENANT, OTHER  # noqa: F401
from test_command_streaming import streaming  # noqa: F401


WORKER = {'x-tank-key': 'dummy-worker-key'}


def frames(response):
    assert response.status_code == 200
    return [json.loads(line[6:]) for line in response.text.splitlines()
            if line.startswith('data: ')]


async def claimed_build(client):
    tid = (await client.post('/v1/command/threads', json={})).json()['thread_id']
    card = (await client.post('/v1/command/build', json={
        'thread_id': tid, 'brief_markdown': 'Offline acceptance build'})).json()
    assert (await client.get('/v1/command/builds/next', headers=WORKER)).json() is None
    confirmed = await client.post(f"/v1/command/cards/{card['card_id']}", json={'action': 'confirm'})
    assert confirmed.status_code == 200
    bid = confirmed.json()['build_id']
    assert (await client.get('/v1/command/builds/next', headers=WORKER)).json()['build_id'] == bid
    return tid, bid


@pytest.mark.asyncio
async def test_returning_viewer_replays_over_page_boundary_and_recovers_last_panel(api):  # noqa: F811 (imported pytest fixture)
    client, _ = api
    tid, bid = await claimed_build(client)
    url = f'/v1/command/threads/{tid}'
    before = frames(await client.get(url + '/events'))
    cursor = before[-1]['seq']
    # Exceed replay's 500-row page using actual HTTP worker contract updates.
    for index in range(503):
        report = await client.post(f'/v1/command/builds/{bid}/progress', headers=WORKER,
                                  json={'status': 'running', 'step_label': f'Offline step {index}'})
        assert report.status_code == 200
    pr = 'https://github.com/Tervory-AI/tervory-tank/pull/123'
    report = await client.post(f'/v1/command/builds/{bid}/progress', headers=WORKER,
        json={'status': 'awaiting_review', 'step_label': 'Offline review', 'pr_url': pr,
              'ci_status': 'passed', 'review_status': 'pending'})
    assert report.status_code == 200
    replay_response = await client.get(url + f'/events?after={cursor}')
    replay = frames(replay_response)
    assert len(replay) == 504
    assert [e['seq'] for e in replay] == list(range(cursor + 1, cursor + 505))
    assert replay[-1]['link'] == pr and replay[-1]['review_status'] == 'pending'
    state = (await client.get(url)).json()
    step = next(s for s in state['steps'] if s['step_id'] == bid)
    assert all(step[key] == replay[-1][key] for key in
               ('status', 'label', 'link', 'ci_status', 'review_status'))
    assert frames(await client.get(url + f"/events?after={replay[-1]['seq']}")) == []
    if os.environ.get('COMMAND_ACCEPTANCE_CLIENTS') == '1':
        decoded = subprocess.run(
            ['node', str(Path(__file__).with_name('consume_replay.cjs'))],
            input=json.dumps({'sse': replay_response.text, 'snapshot': state}),
            text=True, capture_output=True, timeout=30, check=False,
        )
        assert decoded.returncode == 0, decoded.stderr
        assert decoded.stdout.startswith('PASS: 504 actual Tank events')
        print(decoded.stdout.strip())
    for headers in ({'x-tervory-user': 'another-user'}, {'x-tervory-tenant': str(OTHER)},
                    {'x-tervory-home-region': 'za'}):
        denied = await client.get(url + f'/events?after={cursor}', headers=headers)
        assert denied.status_code in (403, 404)
        assert pr not in denied.text and 'Offline step' not in denied.text


@pytest.mark.asyncio
async def test_rejected_worker_receipt_leaves_panel_and_replay_unchanged(api):  # noqa: F811 (imported pytest fixture)
    client, pool = api
    tid, bid = await claimed_build(client)
    url = f'/v1/command/threads/{tid}'
    before = (await client.get(url)).json()
    replay_before = frames(await client.get(url + '/events'))
    foreign_id = uuid.uuid4()
    async with pool.acquire() as conn:
        await conn.execute("INSERT INTO tank.ledger(id,tenant_id,agent,task_type,model,cost_usd) "
                           "VALUES($1,$2,'offline','command.turn','code',0)", foreign_id, OTHER)
    rejected = await client.post(f'/v1/command/builds/{bid}/progress', headers=WORKER,
        json={'status': 'done', 'step_label': 'Must roll back', 'ledger_ids': [str(foreign_id)]})
    assert rejected.status_code == 409
    assert (await client.get(url)).json() == before
    assert frames(await client.get(url + '/events')) == replay_before
    # Rejection must not leave a terminal build or prevent a valid later report.
    valid = await client.post(f'/v1/command/builds/{bid}/progress', headers=WORKER,
                             json={'status': 'running', 'step_label': 'Recovered offline'})
    assert valid.status_code == 200
    assert valid.json()['receipt_status'] == 'pending'
    assert (await client.get(url)).json()['thread']['spent_usd'] is None


@pytest.mark.asyncio
async def test_persisted_pat_cannot_escalate_headers_or_cross_user_and_revokes(api):  # noqa: F811 (imported pytest fixture)
    """CLI-lane auth + A command routes + real local schema; synthetic bearer only."""
    pat = pytest.importorskip('personal_tokens', reason='CLI/PAT lane not on this source tree')
    import command
    client, pool = api
    client._transport.app.dependency_overrides[command.identity] = pat.identity
    # Deliberately non-random test credential. Never accepted by a live service.
    token = f'tv1.us-east.{TENANT.hex}.' + 'x' * 43
    async with pool.acquire() as conn:
        await conn.execute("INSERT INTO tank.personal_tokens(tenant_id,user_id,region,name,token_hash) "
                           "VALUES($1,'offline-client','us-east','offline-only',$2)", TENANT, pat.digest(token))
    headers = {'authorization': 'Bearer ' + token, 'x-tervory-user': 'founder',
               'x-tervory-tenant': str(OTHER), 'x-tervory-role': 'org:admin'}
    created = await client.post('/v1/command/threads', json={}, headers=headers)
    assert created.status_code == 200
    tid = created.json()['thread_id']
    async with pool.acquire() as conn:
        owner = await conn.fetchrow('SELECT tenant_id,user_id FROM tank.command_threads WHERE thread_id=$1', uuid.UUID(tid))
        assert owner['tenant_id'] == TENANT and owner['user_id'] == 'offline-client'
    denied = await client.post('/v1/command/build', headers=headers,
                              json={'thread_id': tid, 'brief_markdown': 'Denied offline build'})
    assert denied.status_code == 403
    assert (await client.get('/v1/command/tools', headers=headers)).json() == []
    # Workspace founder in the same tenant still cannot read this user's thread.
    assert (await client.get(f'/v1/command/threads/{tid}')).status_code == 404
    wrong_box = {**headers, 'authorization': 'Bearer ' + token.replace('us-east', 'za')}
    assert (await client.get('/v1/command/threads', headers=wrong_box)).status_code == 403
    async with pool.acquire() as conn:
        await conn.execute('UPDATE tank.personal_tokens SET revoked_at=now() WHERE tenant_id=$1 AND token_hash=$2',
                           TENANT, pat.digest(token))
    refused = await client.get(f'/v1/command/threads/{tid}', headers=headers)
    assert refused.status_code == 401 and token not in refused.text


@pytest.mark.asyncio
@pytest.mark.skipif(os.environ.get('COMMAND_ACCEPTANCE_CLIENTS') != '1',
                    reason='Requires assembled CLI/Workspace and local-only client dependencies')
async def test_cli_public_adapter_reaches_real_tank_with_cancel_barrier(streaming):  # noqa: F811
    pat = pytest.importorskip('personal_tokens')
    b = streaming
    async with b.pool.acquire() as conn:
        for user, suffix in [('founder', 'f'), ('offline-client', 'c')]:
            token = f'tv1.us-east.{TENANT.hex}.' + suffix * 43
            await conn.execute("INSERT INTO tank.personal_tokens(tenant_id,user_id,region,name,token_hash) "
                               "VALUES($1,$2,'us-east','offline-edge',$3)", TENANT, user, pat.digest(token))
    # The subprocess waits on loopback HTTP; keep the async server loop running.
    decoded = await asyncio.to_thread(subprocess.run,
        ['node', str(Path(__file__).with_name('public_edge.cjs'))],
        input=json.dumps({'origin': str(b.api.base_url).rstrip('/'), 'tenant': str(TENANT)}),
        text=True, capture_output=True, timeout=30, check=False)
    assert decoded.returncode == 0, decoded.stderr
    assert decoded.stdout.startswith('PASS: actual CLI/public PAT adapter/Tank')
    print(decoded.stdout.strip())
    assert b.gateway.calls == []
    async with b.pool.acquire() as conn:
        assert await conn.fetchval('SELECT count(*) FROM tank.command_builds') == 0
        state = json.loads(await conn.fetchval(
            "SELECT state FROM tank.command_threads WHERE tenant_id=$1 AND user_id='founder'", TENANT))
        assert len(state['cards']) == 1
        assert next(iter(state['cards'].values()))['status'] == 'cancelled'


async def device_login_edge(b, region, za_key=None):
    async with b.pool.acquire() as conn:
        # Tank prices the pinned turn's Auto comparison from the policy model's live price row.
        await conn.execute("INSERT INTO tank.proof_prices(model,family,input_usd,output_usd) "
                           "VALUES('luna','openai/gpt',0.000001,0.000004) ON CONFLICT(model) DO NOTHING")
    decoded = await asyncio.to_thread(subprocess.run,
        ['node', str(Path(__file__).with_name('device_edge.cjs'))],
        input=json.dumps({'origin': str(b.api.base_url).rstrip('/'), 'tenant': str(TENANT), 'region': region,
                          'pin': 'fixture-pin', **({'za_key': za_key} if za_key else {})}),
        text=True, capture_output=True, timeout=60, check=False)
    assert decoded.returncode == 0, decoded.stderr
    assert decoded.stdout.startswith(f'PASS: CLI device login {region}')
    print(decoded.stdout.splitlines()[0])
    thread = uuid.UUID(json.loads(decoded.stdout.splitlines()[1])['thread'])
    async with b.pool.acquire() as conn:
        token = await conn.fetchrow("SELECT * FROM tank.personal_tokens WHERE tenant_id=$1", TENANT)
        auth = await conn.fetchrow("SELECT * FROM tank.device_authorizations")
        owner = await conn.fetchval("SELECT user_id FROM tank.command_threads WHERE thread_id=$1", thread)
        ledger = await conn.fetchrow("SELECT * FROM tank.ledger WHERE tenant_id=$1 ORDER BY ts DESC LIMIT 1", TENANT)
        state = json.loads(await conn.fetchval("SELECT state FROM tank.command_threads WHERE thread_id=$1", thread))
    # One org-scoped credential for the approving user, used, rotated, then revoked.
    assert (token['region'], token['user_id'], token['device_name']) == (region, 'offline-client', f'acceptance-{region}')
    assert token['last_used_at'] is not None and token['revoked_at'] is not None
    assert token['expires_at'] is not None and token['refresh_hash'] is not None
    assert (auth['status'], auth['token_id'], auth['tenant_id']) == ('consumed', token['token_id'], TENANT)
    assert owner == 'offline-client'  # identity came from the credential row, not headers
    assert ledger['region'] == region and ledger['cost_usd'] is not None
    receipt = next(r for receipts in state['receipts'].values() for r in receipts) if isinstance(state['receipts'], dict) \
        else state['receipts'][0]
    assert receipt['ledger_id'] == str(ledger['id'])
    assert (receipt['requested_model'], receipt['auto_model'], receipt['auto_cost_status']) == ('fixture-pin', 'luna', 'priced')
    assert receipt['auto_cost_usd'] is not None


@pytest.mark.asyncio
@pytest.mark.skipif(os.environ.get('COMMAND_ACCEPTANCE_CLIENTS') != '1',
                    reason='Requires assembled CLI/Workspace and local-only client dependencies')
async def test_cli_device_login_through_workspace_with_automated_approval(streaming):  # noqa: F811
    await device_login_edge(streaming, 'us-east')


@pytest.mark.asyncio
@pytest.mark.skipif(os.environ.get('COMMAND_ACCEPTANCE_CLIENTS') != '1',
                    reason='Requires assembled CLI/Workspace and local-only client dependencies')
async def test_za_cli_talks_straight_to_tank_with_device_login(streaming, monkeypatch):  # noqa: F811
    """B: za.tervory.com is Tank only (no Workspace). Approval still happens on the
    one Workspace, which records it on the ZA Tank via TANK_URL_ZA/TANK_API_KEY_ZA.
    As in production, Boston's TANK_API_KEY_ZA is the ZA Tank's narrow TANK_HOMES_KEY
    (it cannot approve); approvals use the dedicated TANK_DEVICE_APPROVAL_KEY."""
    monkeypatch.setenv('TANK_REGION', 'za')
    monkeypatch.setenv('TANK_HOMES_KEY', 'dummy-za-homes-key')
    monkeypatch.setenv('TANK_DEVICE_APPROVAL_KEY', 'dummy-za-device-approval-key')
    # A ZA Tank process reads TANK_REGION=za at import; mirror that for the ledger.
    monkeypatch.setattr(streaming.tank, 'DEFAULT_REGION', 'za')
    await device_login_edge(streaming, 'za', za_key='dummy-za-device-approval-key')
