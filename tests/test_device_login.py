"""CLI device sign-in: real local Postgres, real routes, synthetic identities only."""
import uuid

import httpx
import pytest
import pytest_asyncio
from fastapi import FastAPI

import command
import device_login
import personal_tokens as pat
from test_command import command_pool, runtime, TENANT, OTHER  # noqa: F401

WORKSPACE = {'x-tank-key': 'dummy-workspace-key', 'x-tervory-tenant': str(TENANT), 'x-tervory-user': 'client'}


@pytest_asyncio.fixture
async def device(runtime, monkeypatch, command_pool):  # noqa: F811 (imported pytest fixtures)
    monkeypatch.setattr(command, 'db', lambda: command_pool)
    monkeypatch.setenv('TERVORY_WORKSPACE_URL', 'https://workspace.fixture')
    app = FastAPI()
    app.include_router(command.router)
    pat.register(app)
    app.dependency_overrides[command.identity] = pat.identity
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url='http://fixture') as client:
        yield client, command_pool, runtime


async def start(client, name='zenas-laptop'):
    response = await client.post('/v1/command/device/code', json={'device_name': name})
    assert response.status_code == 200 and response.headers['cache-control'] == 'no-store'
    return response.json()


async def approve(client, code, action='approve', headers=WORKSPACE):
    return await client.post(f'/v1/command/device/approval/{code}', json={'action': action}, headers=headers)


@pytest.mark.asyncio
async def test_device_code_approval_poll_issue_and_single_use(device):
    client, pool, _ = device
    grant = await start(client)
    assert grant['device_code'].startswith('tvd1.us-east.')
    assert device_login.USER_CODE.fullmatch(grant['user_code'])
    assert grant['verification_uri_complete'] == (
        f"https://workspace.fixture/cli/device?code={grant['user_code']}&region=us-east")
    poll = {'device_code': grant['device_code']}
    pending = await client.post('/v1/command/device/token', json=poll)
    assert pending.status_code == 400 and pending.json() == {'error': 'authorization_pending'}
    assert (await client.post('/v1/command/device/token', json=poll)).json() == {'error': 'slow_down'}
    # The approval page reads the pending code with the Workspace session only.
    shown = await client.get(f"/v1/command/device/approval/{grant['user_code']}", headers=WORKSPACE)
    assert shown.json()['device_name'] == 'zenas-laptop' and shown.json()['region'] == 'us-east'
    assert (await approve(client, grant['user_code'])).json()['status'] == 'approved'
    issued = await client.post('/v1/command/device/token', json=poll)
    assert issued.status_code == 200, issued.text
    body = issued.json()
    assert body['access_token'].startswith(f'tv1.us-east.{TENANT.hex}.')
    assert body['refresh_token'].startswith(f'tvr1.us-east.{TENANT.hex}.')
    assert body['expires_in'] == 3600 and body['refresh_expires_in'] == 30 * 86400
    # Single use: a replayed device code mints nothing.
    assert (await client.post('/v1/command/device/token', json=poll)).json() == {'error': 'invalid_grant'}
    async with pool.acquire() as conn:
        rows = await conn.fetch('SELECT * FROM tank.personal_tokens')
        auth = await conn.fetchrow('SELECT * FROM tank.device_authorizations')
    assert len(rows) == 1
    row = rows[0]
    assert row['tenant_id'] == TENANT and row['user_id'] == 'client' and row['device_name'] == 'zenas-laptop'
    assert row['token_hash'] == pat.digest(body['access_token'])
    assert row['refresh_hash'] == pat.digest(body['refresh_token'])
    assert row['expires_at'] is not None and row['last_used_at'] is None
    assert auth['status'] == 'consumed' and auth['token_id'] == row['token_id']
    assert auth['device_hash'] == pat.digest(grant['device_code'])
    stored = repr(dict(row)) + repr(dict(auth))
    for secret in (body['access_token'], body['refresh_token'], grant['device_code']):
        assert secret not in stored
    # The issued credential works on the command contract and records use.
    bearer = {'authorization': 'Bearer ' + body['access_token']}
    created = await client.post('/v1/command/threads', json={}, headers=bearer)
    assert created.status_code == 200
    async with pool.acquire() as conn:
        assert await conn.fetchval('SELECT last_used_at FROM tank.personal_tokens') is not None


@pytest.mark.asyncio
async def test_refresh_rotates_expiry_refuses_and_revoke_ends_both(device):
    client, pool, _ = device
    grant = await start(client)
    await approve(client, grant['user_code'])
    first = (await client.post('/v1/command/device/token', json={'device_code': grant['device_code']})).json()
    old = {'authorization': 'Bearer ' + first['access_token']}
    assert (await client.get('/v1/command/tools', headers=old)).status_code == 200
    # Expiry: an access token past expires_at is refused.
    async with pool.acquire() as conn:
        await conn.execute("UPDATE tank.personal_tokens SET expires_at=now()-interval '1 second'")
    expired = await client.get('/v1/command/tools', headers=old)
    assert expired.status_code == 401 and first['access_token'] not in expired.text
    second = (await client.post('/v1/command/device/refresh', json={'refresh_token': first['refresh_token']})).json()
    assert second['access_token'] != first['access_token'] and second['refresh_token'] != first['refresh_token']
    assert second['credential_id'] == first['credential_id']
    new = {'authorization': 'Bearer ' + second['access_token']}
    assert (await client.get('/v1/command/tools', headers=new)).status_code == 200
    # Rotation: the used refresh token is single use.
    reused = await client.post('/v1/command/device/refresh', json={'refresh_token': first['refresh_token']})
    assert reused.status_code == 400 and reused.json() == {'error': 'invalid_grant'}
    # An expired refresh token cannot extend the session.
    async with pool.acquire() as conn:
        await conn.execute("UPDATE tank.personal_tokens SET refresh_expires_at=now()-interval '1 second'")
    stale = await client.post('/v1/command/device/refresh', json={'refresh_token': second['refresh_token']})
    assert stale.json() == {'error': 'invalid_grant'}
    async with pool.acquire() as conn:
        await conn.execute("UPDATE tank.personal_tokens SET refresh_expires_at=now()+interval '1 day'")
    # Revoke with the refresh token ends the access token too (one row).
    assert (await client.post('/v1/command/device/revoke', json={'refresh_token': second['refresh_token']})).json() == {'revoked': True}
    assert (await client.get('/v1/command/tools', headers=new)).status_code == 401
    after = await client.post('/v1/command/device/refresh', json={'refresh_token': second['refresh_token']})
    assert after.json() == {'error': 'invalid_grant'}
    async with pool.acquire() as conn:
        assert await conn.fetchval('SELECT revoked_at FROM tank.personal_tokens') is not None
    # Unknown credentials get the same answer (no existence oracle).
    unknown = f'tvr1.us-east.{TENANT.hex}.' + 'u' * 43
    assert (await client.post('/v1/command/device/revoke', json={'refresh_token': unknown})).json() == {'revoked': True}


@pytest.mark.asyncio
async def test_bearer_self_revoke_and_denial_expiry_and_region(device):
    client, pool, rt = device
    grant = await start(client)
    await approve(client, grant['user_code'])
    access = (await client.post('/v1/command/device/token', json={'device_code': grant['device_code']})).json()['access_token']
    bearer = {'authorization': 'Bearer ' + access}
    assert (await client.post('/v1/command/device/revoke', headers=bearer)).status_code == 200
    assert (await client.get('/v1/command/tools', headers=bearer)).status_code == 401
    denied = await start(client)
    assert (await approve(client, denied['user_code'], 'deny')).json()['status'] == 'denied'
    refused = await client.post('/v1/command/device/token', json={'device_code': denied['device_code']})
    assert refused.json() == {'error': 'access_denied'}
    # A decided code cannot be approved later.
    assert (await approve(client, denied['user_code'])).status_code == 404
    late = await start(client)
    async with pool.acquire() as conn:
        await conn.execute("UPDATE tank.device_authorizations SET expires_at=now()-interval '1 second' WHERE user_code=$1",
                           late['user_code'])
    assert (await approve(client, late['user_code'])).status_code == 404
    assert (await client.post('/v1/command/device/token', json={'device_code': late['device_code']})).json() == {
        'error': 'expired_token'}
    # A code minted for one box is refused by the other.
    wrong = late['device_code'].replace('tvd1.us-east.', 'tvd1.za.')
    assert (await client.post('/v1/command/device/token', json={'device_code': wrong})).json() == {'error': 'invalid_grant'}
    runtime_main = __import__('sys').modules['main']
    runtime_main.box_region = lambda: 'za'
    za = await start(client)
    assert za['device_code'].startswith('tvd1.za.') and za['region'] == 'za'
    assert za['verification_uri_complete'].endswith('&region=za')


@pytest.mark.asyncio
async def test_approval_needs_the_workspace_session_not_a_cli_bearer(device):
    client, pool, _ = device
    grant = await start(client)
    for headers in ({}, {'x-tank-key': 'wrong', 'x-tervory-tenant': str(TENANT), 'x-tervory-user': 'client'}):
        assert (await approve(client, grant['user_code'], headers=headers)).status_code == 401
        assert (await client.get(f"/v1/command/device/approval/{grant['user_code']}", headers=headers)).status_code == 401
    # A valid CLI credential cannot approve another device (no self-propagation).
    other = await start(client, 'other')
    await approve(client, other['user_code'])
    access = (await client.post('/v1/command/device/token', json={'device_code': other['device_code']})).json()['access_token']
    assert (await approve(client, grant['user_code'], headers={'authorization': 'Bearer ' + access})).status_code == 401
    # The approving org is the one that owns the credential.
    other_org = {**WORKSPACE, 'x-tervory-tenant': str(OTHER)}
    assert (await approve(client, grant['user_code'], headers=other_org)).status_code == 200
    issued = (await client.post('/v1/command/device/token', json={'device_code': grant['device_code']})).json()
    assert issued['access_token'].startswith(f'tv1.us-east.{OTHER.hex}.')
    for bad in ('ABCD-EFGH', 'bcdf-ghjk', '../x'):
        assert (await client.get(f'/v1/command/device/approval/{bad}', headers=WORKSPACE)).status_code == 404
    assert (await client.post('/v1/command/device/code', json={'device_name': 'x', 'tenant_id': str(TENANT)})).status_code == 422
    assert (await client.post('/v1/command/device/code', json={'device_name': '\x00\x1b'})).status_code == 422


HOMES = 'dummy-za-homes-key'
APPROVER = 'dummy-za-device-approval-key'
APPROVER_WORKSPACE = {**WORKSPACE, 'x-tank-key': APPROVER}
HOMES_WORKSPACE = {**WORKSPACE, 'x-tank-key': HOMES}


@pytest.mark.asyncio
async def test_za_device_approval_key_may_show_approve_and_deny_device_codes(device, monkeypatch):
    """Boston never holds the ZA Workspace key; it approves ZA sign-ins with the dedicated key."""
    client, pool, rt = device
    monkeypatch.setattr(rt, 'box_region', lambda: 'za')
    monkeypatch.setenv('TANK_HOMES_KEY', HOMES)
    monkeypatch.setenv('TANK_DEVICE_APPROVAL_KEY', APPROVER)
    grant = await start(client, 'za-laptop')
    assert grant['region'] == 'za'
    shown = await client.get(f"/v1/command/device/approval/{grant['user_code']}", headers=APPROVER_WORKSPACE)
    assert shown.status_code == 200, shown.text
    assert shown.json()['device_name'] == 'za-laptop' and shown.json()['region'] == 'za'
    assert (await approve(client, grant['user_code'], headers=APPROVER_WORKSPACE)).json()['status'] == 'approved'
    issued = (await client.post('/v1/command/device/token', json={'device_code': grant['device_code']})).json()
    assert issued['access_token'].startswith(f'tv1.za.{TENANT.hex}.')
    async with pool.acquire() as conn:
        row = await conn.fetchrow('SELECT tenant_id,user_id,region FROM tank.personal_tokens')
    assert (row['tenant_id'], row['user_id'], row['region']) == (TENANT, 'client', 'za')
    denied = await start(client)
    assert (await approve(client, denied['user_code'], 'deny', headers=APPROVER_WORKSPACE)).json()['status'] == 'denied'
    # The full ZA Workspace key keeps working too.
    plain = await start(client)
    assert (await approve(client, plain['user_code'])).json()['status'] == 'approved'


@pytest.mark.asyncio
async def test_za_homes_key_cannot_approve_device_codes(device, monkeypatch):
    """Least privilege: the ZA homes key (Boston's TANK_API_KEY_ZA) is not widened."""
    client, pool, rt = device
    monkeypatch.setattr(rt, 'box_region', lambda: 'za')
    monkeypatch.setenv('TANK_HOMES_KEY', HOMES)
    monkeypatch.setenv('TANK_DEVICE_APPROVAL_KEY', APPROVER)
    grant = await start(client)
    assert (await client.get(f"/v1/command/device/approval/{grant['user_code']}", headers=HOMES_WORKSPACE)).status_code == 401
    assert (await approve(client, grant['user_code'], headers=HOMES_WORKSPACE)).status_code == 401
    # A dedicated key configured equal to the homes key is refused outright (no scope blur).
    monkeypatch.setenv('TANK_DEVICE_APPROVAL_KEY', HOMES)
    assert (await approve(client, grant['user_code'], headers=HOMES_WORKSPACE)).status_code == 401
    async with pool.acquire() as conn:
        assert await conn.fetchval("SELECT status FROM tank.device_authorizations WHERE user_code=$1",
                                   grant['user_code']) == 'pending'


@pytest.mark.asyncio
async def test_za_device_approval_key_still_needs_user_and_tenant_and_reaches_nothing_else(device, monkeypatch):
    client, pool, rt = device
    monkeypatch.setattr(rt, 'box_region', lambda: 'za')
    monkeypatch.setenv('TANK_DEVICE_APPROVAL_KEY', APPROVER)
    grant = await start(client)
    code = grant['user_code']
    # User and tenant are still required and checked.
    no_user = {k: v for k, v in APPROVER_WORKSPACE.items() if k != 'x-tervory-user'}
    assert (await approve(client, code, headers=no_user)).status_code == 401
    assert (await client.get(f'/v1/command/device/approval/{code}', headers=no_user)).status_code == 401
    assert (await approve(client, code, headers={**APPROVER_WORKSPACE, 'x-tervory-tenant': 'not-a-uuid'})).status_code == 422
    assert (await approve(client, code, headers={**APPROVER_WORKSPACE, 'x-tervory-home-region': 'us-east'})).status_code == 403
    # A near-miss key is not the approval key.
    assert (await approve(client, code, headers={**APPROVER_WORKSPACE, 'x-tank-key': APPROVER + 'x'})).status_code == 401
    # Outside the two approval routes the approval key is refused.
    for method, path, body in (('GET', '/v1/command/tools', None), ('GET', '/v1/command/threads', None),
                               ('POST', '/v1/command/threads', {}), ('POST', '/v1/personal-tokens', {'name': 'x'})):
        # (Listing and revoking the user's own sign-ins is allowed: see the B3 tests below.)
        response = await client.request(method, path, json=body, headers=APPROVER_WORKSPACE)
        assert response.status_code == 401, (method, path, response.status_code)
    # Not on a us-east box, and not when TANK_DEVICE_APPROVAL_KEY is unset.
    monkeypatch.setattr(rt, 'box_region', lambda: 'us-east')
    us = await start(client)
    assert (await approve(client, us['user_code'], headers=APPROVER_WORKSPACE)).status_code == 401
    assert (await client.get(f"/v1/command/device/approval/{us['user_code']}", headers=APPROVER_WORKSPACE)).status_code == 401
    monkeypatch.setattr(rt, 'box_region', lambda: 'za')
    monkeypatch.setenv('TANK_DEVICE_APPROVAL_KEY', '')
    assert (await approve(client, code, headers=APPROVER_WORKSPACE)).status_code == 401
    async with pool.acquire() as conn:
        assert await conn.fetchval("SELECT status FROM tank.device_authorizations WHERE user_code=$1", code) == 'pending'
        assert await conn.fetchval('SELECT count(*) FROM tank.personal_tokens') == 0


@pytest.mark.asyncio
async def test_za_device_approval_key_never_approves_for_a_founder(device, monkeypatch):
    """Review of #506, should-fix 1: the Boston-held approval key cannot mint a founder credential."""
    client, pool, rt = device
    monkeypatch.setattr(rt, 'box_region', lambda: 'za')
    monkeypatch.setenv('TANK_DEVICE_APPROVAL_KEY', APPROVER)
    monkeypatch.setenv('TERVORY_ADMIN_USER_IDS', ' founder , second-founder ')
    grant = await start(client)
    code = grant['user_code']
    for user in ('founder', 'second-founder'):
        as_founder = {**APPROVER_WORKSPACE, 'x-tervory-user': user, 'x-tervory-role': 'org:admin'}
        shown = await client.get(f'/v1/command/device/approval/{code}', headers=as_founder)
        assert shown.status_code == 403 and 'device_name' not in shown.text
        assert (await approve(client, code, headers=as_founder)).status_code == 403
        assert (await approve(client, code, 'deny', headers=as_founder)).status_code == 403
    assert (await client.post('/v1/command/device/token', json={'device_code': grant['device_code']})).json() == {
        'error': 'authorization_pending'}
    async with pool.acquire() as conn:
        assert await conn.fetchval("SELECT status FROM tank.device_authorizations WHERE user_code=$1", code) == 'pending'
        assert await conn.fetchval('SELECT count(*) FROM tank.personal_tokens') == 0
    # The ZA Workspace key path is unchanged for the founder; an ordinary member still
    # approves with the dedicated key, and the credential carries no admin role.
    assert (await approve(client, code, headers={**APPROVER_WORKSPACE, 'x-tervory-role': 'org:admin'})).json()['status'] == 'approved'
    issued = (await client.post('/v1/command/device/token', json={'device_code': grant['device_code']})).json()
    actor = await pat.identity(__import__('test_personal_tokens').request(issued['access_token'], path='/v1/command/threads'))
    assert actor.user_id == 'client' and not actor.founder and not actor.tenant_admin


async def signed_in(client, name, headers=WORKSPACE):
    grant = await start(client, name)
    assert (await approve(client, grant['user_code'], headers=headers)).status_code == 200
    return (await client.post('/v1/command/device/token', json={'device_code': grant['device_code']})).json()


@pytest.mark.asyncio
@pytest.mark.parametrize('box', ['us-east', 'za'])
async def test_cli_sign_ins_are_listed_and_revoked_by_their_owner_only(device, monkeypatch, box):
    """Review of #506, B3: the Workspace 'CLI sign-ins' page lists and revokes the signed-in
    user's own CLI credentials, per region (us-east: Workspace key; ZA: the dedicated key)."""
    client, pool, rt = device
    monkeypatch.setattr(rt, 'box_region', lambda: box)
    monkeypatch.setenv('TANK_HOMES_KEY', HOMES)
    monkeypatch.setenv('TANK_DEVICE_APPROVAL_KEY', APPROVER)
    key = WORKSPACE if box == 'us-east' else APPROVER_WORKSPACE
    other = {**key, 'x-tervory-user': 'someone-else'}
    other_tenant = {**key, 'x-tervory-tenant': str(OTHER)}
    mine = await signed_in(client, 'stolen-by-phisher', key)
    theirs = await signed_in(client, 'their-laptop', other)
    bearer = {'authorization': 'Bearer ' + mine['access_token']}
    assert (await client.get('/v1/command/tools', headers=bearer)).status_code == 200
    listed = await client.get('/v1/personal-tokens', headers=key)
    assert listed.status_code == 200 and listed.headers['cache-control'] == 'no-store'
    rows = listed.json()
    assert [r['device_name'] for r in rows] == ['stolen-by-phisher']
    row = rows[0]
    assert row['region'] == box and row['created_at'] and row['last_used_at'] and row['refresh_expires_at']
    assert row['revoked_at'] is None and row['token_id'] == mine['credential_id']
    for secret in (mine['access_token'], mine['refresh_token'], 'token_hash', 'refresh_hash', 'their-laptop'):
        assert secret not in listed.text
    assert (await client.get('/v1/personal-tokens', headers=other_tenant)).json() == []
    # Neither another user nor another tenant can revoke it, and the answer is the same as unknown.
    for headers in (other, other_tenant):
        assert (await client.delete(f"/v1/personal-tokens/{mine['credential_id']}", headers=headers)).status_code == 404
    assert (await client.get('/v1/command/tools', headers=bearer)).status_code == 200
    # Revoke: the access token and the refresh token both stop at once.
    revoked = await client.delete(f"/v1/personal-tokens/{mine['credential_id']}", headers=key)
    assert revoked.status_code == 204
    assert (await client.get('/v1/command/tools', headers=bearer)).status_code == 401
    assert (await client.post('/v1/command/device/refresh', json={'refresh_token': mine['refresh_token']})).json() == {
        'error': 'invalid_grant'}
    assert (await client.get('/v1/personal-tokens', headers=key)).json()[0]['revoked_at'] is not None
    # The other user's sign-in is untouched.
    assert (await client.get('/v1/command/tools', headers={'authorization': 'Bearer ' + theirs['access_token']})).status_code == 200
    # A CLI token can never list or revoke sign-ins.
    theirs_bearer = {'authorization': 'Bearer ' + theirs['access_token']}
    assert (await client.get('/v1/personal-tokens', headers=theirs_bearer)).status_code in {401, 404}
    assert (await client.delete(f"/v1/personal-tokens/{theirs['credential_id']}", headers=theirs_bearer)).status_code in {401, 404}


@pytest.mark.asyncio
async def test_za_sign_in_key_lists_and_revokes_only_never_mints_and_never_for_founders(device, monkeypatch):
    client, pool, rt = device
    monkeypatch.setattr(rt, 'box_region', lambda: 'za')
    monkeypatch.setenv('TANK_HOMES_KEY', HOMES)
    monkeypatch.setenv('TANK_DEVICE_APPROVAL_KEY', APPROVER)
    founder = {**APPROVER_WORKSPACE, 'x-tervory-user': 'founder'}
    target = uuid.uuid4()
    assert (await client.get('/v1/personal-tokens', headers=founder)).status_code == 403
    assert (await client.delete(f'/v1/personal-tokens/{target}', headers=founder)).status_code == 403
    # Minting stays Workspace-key only; the homes key and a near-miss key reach nothing.
    assert (await client.post('/v1/personal-tokens', json={'name': 'x'}, headers=APPROVER_WORKSPACE)).status_code == 401
    for headers in (HOMES_WORKSPACE, {**APPROVER_WORKSPACE, 'x-tank-key': APPROVER + 'x'}):
        assert (await client.get('/v1/personal-tokens', headers=headers)).status_code == 401
        assert (await client.delete(f'/v1/personal-tokens/{target}', headers=headers)).status_code == 401
    no_user = {k: v for k, v in APPROVER_WORKSPACE.items() if k != 'x-tervory-user'}
    assert (await client.get('/v1/personal-tokens', headers=no_user)).status_code == 401
    # Only on a ZA box.
    monkeypatch.setattr(rt, 'box_region', lambda: 'us-east')
    assert (await client.get('/v1/personal-tokens', headers=APPROVER_WORKSPACE)).status_code == 401
    async with pool.acquire() as conn:
        assert await conn.fetchval('SELECT count(*) FROM tank.personal_tokens') == 0


def test_device_schema_is_additive_and_hash_only():
    from pathlib import Path
    sql = Path('tank/schema.sql').read_text()
    section = sql[sql.index('-- CLI device sign-in'):]
    for statement in ('ADD COLUMN IF NOT EXISTS device_name', 'ADD COLUMN IF NOT EXISTS expires_at',
                      'ADD COLUMN IF NOT EXISTS last_used_at', 'ADD COLUMN IF NOT EXISTS refresh_hash',
                      'ADD COLUMN IF NOT EXISTS refresh_expires_at',
                      'CREATE TABLE IF NOT EXISTS tank.device_authorizations'):
        assert statement in section
    assert 'DROP ' not in section and 'RENAME' not in section
    assert 'device_code text' not in section and 'access_token' not in section
