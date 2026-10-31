"""Offline acceptance: real command HTTP/SQL, fake worker progress, no model calls."""
import json
import os
import subprocess
from pathlib import Path
import uuid

import pytest

from test_command import api, command_pool, runtime, TENANT, OTHER  # noqa: F401


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
async def test_returning_viewer_replays_over_page_boundary_and_recovers_last_panel(api):
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
async def test_rejected_worker_receipt_leaves_panel_and_replay_unchanged(api):
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
