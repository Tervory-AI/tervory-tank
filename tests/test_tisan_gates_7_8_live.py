"""Gates 7+8 at the real ingress: founder endpoints, the tisan-brain service and the pipeline build.

Offline only. Cost/token figures are FAKE FIXTURE values (fixed per Tank call),
never billing. Identity comes from the founder guard, never a body field.
"""
import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock
import uuid

from fastapi import FastAPI
from fastapi.testclient import TestClient
import httpx
import pytest

from chassis.memory import MemoryClient
from agents.tisan import brain_service, builder, gates_memory, memory_api, pipeline
from test_tisan_gates_7_8_memory import (ScopedClient, FAKE_COST_USD, FAKE_TOKENS_IN, FAKE_TOKENS_OUT, PLAN, FakeHermes,
                                         FakeTank, TENANT, OTHER_TENANT, brief)
from test_tisan_gold_sources import setup as setup
from test_tisan_gold_sources import TENANT as GOLD_TENANT
from trigger_signin_fakes import set_founders

@pytest.fixture(autouse=True)
def opt_in_existing_gate_scenarios(monkeypatch):
    monkeypatch.setenv('TISAN_BRAIN_ENABLED', 'true')


ROOT = Path(__file__).resolve().parents[1]
FOUNDER, OTHER_FOUNDER = 'founder-user', 'second-founder'


def memory_client(hermes, transport=None):
    http = httpx.AsyncClient(transport=transport or httpx.MockTransport(hermes.handler))
    return ScopedClient(base_url='http://placeholder-hermes', api_key='placeholder-room', agent='tisan', http=http)


def founders(monkeypatch, key='placeholder-room-key'):
    set_founders(monkeypatch, f'{FOUNDER},{OTHER_FOUNDER}')
    monkeypatch.setenv('TANK_KEY', key)
    return key


def room(hermes, monkeypatch):
    key = founders(monkeypatch)
    spec = importlib.util.spec_from_file_location('tisan_gold_live', ROOT / 'agents/tisan/gold_sources.py')
    gold = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(gold)
    app = FastAPI()
    app.state.memory = memory_client(hermes)

    @app.post('/work')
    async def work(body: dict):
        return {'done': True}

    memory_api.mount(app, gold.founder)
    return SignedClient(app), key


class SignedClient(TestClient):
    """Plays Tank's patched forwarder: signs X-Tervory-User/-Tenant for the exact method, path and body.

    Pass X-Test-Sign: 'none' to send the raw identity headers unsigned, or 'wrong' for a bad signature.
    """

    def __init__(self, app, **kwargs):
        from contextlib import asynccontextmanager
        import os
        import asyncpg
        class RequestPool:
            @asynccontextmanager
            async def acquire(self):
                conn = await asyncpg.connect(os.environ['POOL_SCHEMA_DATABASE_URL'])
                try:
                    await conn.execute('CREATE SCHEMA IF NOT EXISTS agent_tisan')
                    from agents.tisan.gold_sources import SCHEMA
                    await conn.execute(SCHEMA)
                    yield conn
                finally:
                    await conn.close()
        app.state.pool = RequestPool()
        super().__init__(app, **kwargs)

    def request(self, method, url, **kwargs):
        from urllib.parse import urlsplit
        from chassis.user_assertion import sign_assertion, SignedUser, HEADER
        if kwargs.get('json') is not None:
            kwargs['content'] = json.dumps(kwargs.pop('json')).encode()
            if not isinstance(kwargs.get('headers'), list):
                kwargs['headers'] = {**(kwargs.get('headers') or {}), 'Content-Type': 'application/json'}
        kwargs.pop('json', None)
        if isinstance(kwargs.get('headers'), list):
            return super().request(method, url, **kwargs)  # Raw duplicate headers, sent as given.
        headers = dict(kwargs.get('headers') or {})
        mode = headers.pop('X-Test-Sign', 'valid')
        if 'X-Tervory-User' in headers and 'X-Tervory-Tenant' in headers and mode != 'none':
            target = urlsplit(url).path + ('?' + urlsplit(url).query if urlsplit(url).query else '')
            signature = sign_assertion('tisan', SignedUser(headers.get('X-Tervory-Tenant', TENANT),
                headers['X-Tervory-User'], 'founder'), method, target, kwargs.get('content') or b'',
                key=headers.pop('X-Test-Sign-Key', __import__('os').environ['TANK_KEY']))
            headers[HEADER] = signature if mode == 'valid' else 'invalid'
        kwargs['headers'] = headers
        return super().request(method, url, **kwargs)


SIGNING_KEY = 'placeholder-room-key'


def headers(key, user=FOUNDER, tenant=TENANT):
    """What Tank forwards for a signed-in founder: room key, verified user and bound tenant."""
    return {'X-Tank-Key': key, 'X-Tervory-User': user, 'X-Tervory-Admin': user, 'X-Tervory-Tenant': tenant}


def test_every_founder_endpoint_recalls_then_remembers_its_outcome(monkeypatch):
    hermes = FakeHermes()
    client, key = room(hermes, monkeypatch)
    first = client.post('/work', headers=headers(key), json={'tenant_id': TENANT, 'user_id': OTHER_FOUNDER})
    assert first.status_code == 200 and first.headers['X-Tisan-Memory-Recalled'] == '0'
    second = client.post('/work', headers=headers(key), json={'tenant_id': TENANT})
    assert second.headers['X-Tisan-Memory-Recalled'] == '1'
    outcome = [r for r in hermes.rows if r['kind'] == 'tisan.outcome']
    assert [r['meta']['user_id'] for r in outcome] == [FOUNDER, FOUNDER]  # A body user_id is ignored.
    assert outcome[0]['meta'].items() >= {'route': '/work', 'method': 'POST', 'status': 200}.items()
    # Unverified callers get no memory at all.
    before = len(hermes.rows)
    assert 'X-Tisan-Memory-Recalled' not in client.post('/work', headers=headers('wrong'), json={'tenant_id': TENANT}).headers
    assert 'X-Tisan-Memory-Recalled' not in client.post('/work', headers=headers(key, 'stranger'), json={'tenant_id': TENANT}).headers
    assert len(hermes.rows) == before


def test_live_view_edit_forget_and_off_are_per_tenant_and_user(monkeypatch):
    hermes = FakeHermes()
    client, key = room(hermes, monkeypatch)
    for tenant, user in ((TENANT, FOUNDER), (TENANT, OTHER_FOUNDER), (OTHER_TENANT, FOUNDER)):
        client.post('/work', headers=headers(key, user, tenant), json={'tenant_id': tenant})
    view = client.get(f'/memory?tenant_id={TENANT}&user_id={FOUNDER}', headers=headers(key)).json()
    assert view['enabled'] is True and len(view['memories']) == 1 and set(view['remembers']) == set(gates_memory.REMEMBERS)
    ident = view['memories'][0]['id']
    # Another user or tenant cannot touch it.
    assert client.delete(f'/memory/{ident}?tenant_id={TENANT}&user_id={OTHER_FOUNDER}', headers=headers(key, OTHER_FOUNDER)).status_code == 404
    assert client.delete(f'/memory/{ident}?tenant_id={OTHER_TENANT}&user_id={FOUNDER}', headers=headers(key, FOUNDER, OTHER_TENANT)).status_code == 404
    edited = client.post(f'/memory/{ident}', headers=headers(key), json={'tenant_id': TENANT, 'user_id': FOUNDER, 'value': 'corrected'})
    assert edited.status_code == 200
    assert [m['meta']['value'] for m in client.get(f'/memory?tenant_id={TENANT}&user_id={FOUNDER}', headers=headers(key)).json()['memories']] == ['corrected']
    assert client.post('/memory/setting', headers=headers(key), json={'tenant_id': TENANT, 'user_id': FOUNDER, 'enabled': False}).json() == {'enabled': False}
    before = len(hermes.rows)
    assert client.post('/work', headers=headers(key), json={'tenant_id': TENANT}).headers['X-Tisan-Memory-Recalled'] == 'off'
    assert len(hermes.rows) == before  # Off means nothing new is remembered.
    assert client.delete(f'/memory?tenant_id={TENANT}&user_id={FOUNDER}', headers=headers(key)).json() == {'forgotten': 1}
    assert client.get(f'/memory?tenant_id={TENANT}&user_id={OTHER_FOUNDER}', headers=headers(key, OTHER_FOUNDER)).json()['memories']
    assert client.get(f'/memory?tenant_id={OTHER_TENANT}&user_id={FOUNDER}', headers=headers(key, FOUNDER, OTHER_TENANT)).json()['memories']
    assert client.get(f'/memory?tenant_id={TENANT}&user_id=stranger', headers=headers(key, 'stranger')).status_code == 404


def test_gold_approval_and_rejection_remember_real_section_values(setup):
    client, auth, _ = setup
    client = SignedClient(client.app)
    auth = {**auth, 'X-Tervory-User': auth['X-Tervory-Admin'], 'X-Tervory-Tenant': GOLD_TENANT}
    hermes = FakeHermes()
    client.app.state.memory = memory_client(hermes)
    page = client.get(f'/gold/pages?tenant_id={GOLD_TENANT}', headers=auth).json()[0]
    body = {k: page[k] for k in ('tenant_id', 'page_id', 'frame_hash', 'page_hash')}
    assert client.post('/gold/approve', headers=auth, json=body).status_code == 200
    rejected = client.post('/gold/reject', headers=auth, json={**body, 'reason': 'hero spacing is wrong'})
    assert rejected.status_code == 200 and rejected.json()['memory_id']
    assert client.post('/gold/reject', headers=auth, json={**body, 'reason': ' '}).status_code == 422
    assert client.post('/gold/reject', headers=auth, json={**body, 'frame_hash': 'x', 'reason': 'r'}).status_code == 409
    sections = [r['meta'] for r in hermes.rows if r['kind'] == 'tisan.section']
    assert [s['value']['decision'] for s in sections] == ['approved', 'rejected']
    for value in (s['value'] for s in sections):
        assert value['frame_hash'] == page['frame_hash'] and value['page_hash'] == page['page_hash']
        assert value['figma_file_id'] and value['figma_frame_id'] and all(v not in ('', None) for v in value.values())
    assert sections[1]['value']['reason'] == 'hero spacing is wrong' and sections[0]['subject'] == page['page_id']


def test_quote_create_and_move_remember_real_history(monkeypatch):
    from agents.tisan import quotes
    hermes = FakeHermes()
    key = founders(monkeypatch)
    ident = uuid.uuid4()
    rows = iter([{'id': ident, 'state': 'submitted', 'items': [{'type': 'service', 'description': 'site', 'quantity': 1}]},
                 {'id': ident, 'state': 'quoted', 'quote_amount': '1200.00', 'quote_currency': 'ZAR',
                  'valid_until': '2026-12-01', 'items': [{'type': 'service', 'description': 'site', 'quantity': 1}]}])

    class Store:
        def __init__(self, pool):
            pass

        async def create(self, *args, **kwargs):
            return next(rows)

        async def move(self, *args, **kwargs):
            return next(rows)

    monkeypatch.setattr(quotes, 'Quotes', Store)
    app = FastAPI()
    app.state.memory = memory_client(hermes)
    app.state.pool = None
    spec = importlib.util.spec_from_file_location('tisan_gold_q', ROOT / 'agents/tisan/gold_sources.py')
    gold = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(gold)
    quotes.mount(app, gold.founder)
    client = SignedClient(app)
    data = {'contact': {'name': 'Ada', 'email': 'ada@example.com', 'reply_method': 'email'},
            'items': [{'type': 'service', 'description': 'site', 'quantity': 1}]}
    assert client.post('/quotes', headers=headers(key), json={'tenant_id': TENANT, 'data': data}).status_code == 201
    assert client.post(f'/quotes/{ident}/state', headers=headers(key), json={
        'tenant_id': TENANT, 'state': 'quoted', 'quote_amount': '1200.00', 'quote_currency': 'ZAR',
        'valid_until': '2026-12-01', 'quote_message': 'thanks'}).status_code == 200
    history = [r['meta'] for r in hermes.rows if r['kind'] == 'tisan.quote']
    assert [h['value']['state'] for h in history] == ['submitted', 'quoted']
    assert history[1]['value'].items() >= {'quote_amount': '1200.00', 'quote_currency': 'ZAR', 'valid_until': '2026-12-01'}.items()
    assert all(h['subject'] == str(ident) and h['user_id'] == FOUNDER for h in history)


def brain_transport(tank, monkeypatch):
    """Typed boundary fake: signed ASGI to the real brain, real SQL nonce store.

    Full shared-client/Tank-adapter proof belongs to the canonical assembly.
    """
    monkeypatch.setitem(brain_service._tank, 'client', tank)
    client = SignedClient(brain_service.app)

    async def delegate(actor, run_id, task, payload, recall):
        response = client.post(f'/tasks/plan?tenant_id={actor.tenant_id}&user_id={actor.user_id}',
            headers={**headers(SIGNING_KEY, actor.user_id, actor.tenant_id), 'X-Home-Region': 'us-east'},
            json={'task_key': task, 'input': payload, 'recall': recall, 'run_id': run_id})
        assert response.status_code == 200, response.text
        return response.json()
    monkeypatch.setattr(tank, 'delegate_task', delegate)
    return tank


def test_brain_service_runs_free_steps_before_tank(monkeypatch):
    founders(monkeypatch)
    tank = FakeTank()
    monkeypatch.setitem(brain_service._tank, 'client', tank)
    client = SignedClient(brain_service.app)
    auth = {**headers(SIGNING_KEY), 'X-Home-Region': 'us-east'}
    target = f'/tasks/plan?tenant_id={TENANT}&user_id={FOUNDER}'
    def task(prompt):
        return {'task_key': 'tisan.plan', 'input': {'request': prompt, 'contract': builder.manifest()},
                'recall': [], 'run_id': str(uuid.uuid4())}
    assert client.post(target, headers={**auth, 'X-Tank-Key': 'wrong'}, json=task('x')).status_code == 401
    assert client.post(target, headers={**auth, 'X-Test-Sign': 'none'}, json=task('x')).status_code in (401, 403)
    free = client.post(target, headers=auth, json=task(json.dumps(PLAN))).json()
    assert free['result'] == PLAN and free['receipt']['paid_calls'] == 0 and tank.calls == []
    paid = client.post(target, headers=auth, json=task('one page')).json()
    assert tank.calls == [TENANT] and paid['receipt']['cost_usd'] == FAKE_COST_USD
    assert paid['receipt']['user_id'] == FOUNDER and paid['receipt']['task_type'] == 'tisan.plan'


@pytest.mark.asyncio
async def test_pipeline_build_request_memory_brain_tank_receipt_memory(monkeypatch, tmp_path):
    """Real pipeline build callback: trusted actor -> memory -> tisan-brain -> Tank -> receipt -> memory."""
    founders(monkeypatch)
    from agents.tisan import repo_scan
    monkeypatch.setattr(repo_scan, 'attach', AsyncMock(side_effect=lambda result, tenant: result))
    hermes = FakeHermes()
    loader = lambda key, filename: {'builder.py': builder}.get(filename) or __import__('agents.tisan.' + filename[:-3], fromlist=['x'])

    async def run(actor, request='one page with a hero', tenant=TENANT):
        tank = FakeTank()  # A fresh brain process each run: no in-process plan cache.
        brain_service._tank.clear()
        brain_transport(tank, monkeypatch)
        ctx = SimpleNamespace(agent='tisan', tenant_id=tenant, job_id=str(uuid.uuid4()), kind='pipeline',
                              input={}, files=None, tank=tank, memory=memory_client(hermes), browser=None)
        service = pipeline.service(ctx, None, loader, tmp_path)
        built = await service.build(tenant, str(uuid.uuid4()), {**brief(request), 'user_id': OTHER_FOUNDER}, actor)
        return built, len(tank.calls)

    first, first_calls = await run(FOUNDER)
    repeat, repeat_calls = await run(FOUNDER)
    r1, r2 = first['brain_receipt'], repeat['brain_receipt']
    assert (first_calls, r1['paid_calls'], r1['cost_usd'], r1['tokens_in'], r1['tokens_out']) == (
        1, 1, FAKE_COST_USD, FAKE_TOKENS_IN, FAKE_TOKENS_OUT)
    assert r1['source'] == 'tisan-brain' and len(r1['ledger_ids']) == 1 and r1['memory_id']
    assert (repeat_calls, r2['paid_calls'], r2['cost_usd'], r2['tokens_in'], r2['tokens_out']) == (0, 0, 0.0, 0, 0)
    assert r2['source'] == 'memory' and r2['memory_hit'] is True
    print(f'GATES78_LIVE_FAKE_FIXTURE first calls={first_calls} cost_usd={r1["cost_usd"]} tokens_in={r1["tokens_in"]} '
          f'tokens_out={r1["tokens_out"]}; repeat calls={repeat_calls} cost_usd={r2["cost_usd"]} tokens_in={r2["tokens_in"]} '
          f'tokens_out={r2["tokens_out"]} (fake fixture, not billing)')
    result = next(r for r in hermes.rows if r['kind'] == 'tisan.result')
    assert result['meta']['user_id'] == FOUNDER  # Trusted actor; the body's user_id was ignored.
    brand = next(r for r in hermes.rows if r['kind'] == 'tisan.brand')['meta']['value']
    assert brand['colours']['ink'] == '#111111' and brand['fonts'] == {'heading': 'Jost', 'body': 'Inter'}
    _, other_user_calls = await run(OTHER_FOUNDER)
    _, other_tenant_calls = await run(FOUNDER, tenant=OTHER_TENANT)
    _, changed_calls = await run(FOUNDER, request='two pages with a hero')
    assert (other_user_calls, other_tenant_calls, changed_calls) == (1, 1, 1)
    # A direct build without a verified actor never uses (or writes) scoped plan memory.
    rows = len(hermes.rows)
    tank = FakeTank()
    brain_transport(tank, monkeypatch)
    ctx = SimpleNamespace(tenant_id=TENANT, job_id=str(uuid.uuid4()), input={**brief(), 'user_id': FOUNDER},
                          tank=None, memory=memory_client(hermes))
    assert 'brain_receipt' not in await builder.handle(ctx)
    assert hermes.rows[rows:] == []  # No verified owner: no personal build memory.


def raw_headers(items):
    from starlette.datastructures import Headers
    pairs = items.items() if isinstance(items, dict) else items
    return Headers(raw=[(k.lower().encode(), v.encode()) for k, v in pairs])


def snapshot(hermes):
    """Full store snapshot: every row's id, tenant, kind and meta (settings and receipts included)."""
    return json.dumps(sorted(hermes.rows, key=lambda r: r['id']), sort_keys=True)


def owned(monkeypatch):
    """One record and one setting for (TENANT, FOUNDER), plus rows for the other user and other tenant."""
    hermes = FakeHermes()
    client, key = room(hermes, monkeypatch)
    for tenant, user in ((TENANT, FOUNDER), (TENANT, OTHER_FOUNDER), (OTHER_TENANT, FOUNDER)):
        client.post('/work', headers=headers(key, user, tenant), json={'tenant_id': tenant})
    client.post('/memory/setting', headers=headers(key), json={'tenant_id': TENANT, 'user_id': FOUNDER, 'enabled': True})
    ident = next(r['id'] for r in hermes.rows if r['kind'] == 'tisan.outcome' and r['tenant_id'] == TENANT
                 and r['meta']['user_id'] == FOUNDER)
    return hermes, client, key, ident


# Each control x (other user in the same tenant, the owner signed into another tenant).
CALLERS = {'other-user-same-tenant': (OTHER_FOUNDER, TENANT), 'other-tenant': (FOUNDER, OTHER_TENANT)}


def control(client, key, action, ident, user, tenant):
    """Call one real control as (user, tenant) against the owner's record and scope (TENANT, FOUNDER)."""
    auth = headers(key, user, tenant)
    if action == 'view':
        return client.get(f'/memory?tenant_id={TENANT}&user_id={FOUNDER}', headers=auth)
    if action == 'edit':
        return client.post(f'/memory/{ident}', headers=auth, json={'tenant_id': TENANT, 'user_id': FOUNDER, 'value': 'hijacked'})
    if action == 'forget':
        return client.delete(f'/memory/{ident}?tenant_id={TENANT}&user_id={FOUNDER}', headers=auth)
    return client.post('/memory/setting', headers=auth, json={'tenant_id': TENANT, 'user_id': FOUNDER, 'enabled': False})


@pytest.mark.parametrize('caller', sorted(CALLERS))
@pytest.mark.parametrize('action', ['view', 'edit', 'forget', 'off'])
def test_each_control_refuses_a_mismatched_caller_and_changes_nothing(monkeypatch, action, caller):
    hermes, client, key, ident = owned(monkeypatch)
    before = snapshot(hermes)
    user, tenant = CALLERS[caller]
    response = control(client, key, action, ident, user, tenant)
    assert response.status_code == 404 and 'memories' not in response.text and 'hijacked' not in response.text
    assert snapshot(hermes) == before
    # The owner's own call through the same handler still works afterwards.
    own = control(client, key, 'view', ident, FOUNDER, TENANT)
    assert own.status_code == 200 and ident in own.text


@pytest.mark.parametrize('variant', ['admin-only', 'user-admin-differ', 'no-tenant-binding', 'two-users',
                                     'body-user-selector', 'not-a-founder', 'wrong-room-key', 'unsigned',
                                     'wrong-signature', 'signed-with-another-key'])
def test_admin_header_or_body_selector_is_not_a_signed_in_user(monkeypatch, variant):
    hermes, client, key, ident = owned(monkeypatch)
    before = snapshot(hermes)
    auth = headers(key)
    body = {'tenant_id': TENANT, 'user_id': FOUNDER, 'value': 'hijacked'}
    if variant == 'admin-only':
        auth.pop('X-Tervory-User')
    elif variant == 'user-admin-differ':
        auth['X-Tervory-Admin'] = OTHER_FOUNDER
    elif variant == 'no-tenant-binding':
        auth.pop('X-Tervory-Tenant')
    elif variant == 'two-users':
        auth = list(auth.items()) + [('X-Tervory-User', OTHER_FOUNDER)]
    elif variant == 'body-user-selector':
        auth = headers(key, OTHER_FOUNDER)  # Signed in as another user, selecting the owner in the body.
    elif variant == 'not-a-founder':
        auth = headers(key, 'stranger')
    elif variant == 'unsigned':
        auth['X-Test-Sign'] = 'none'  # Raw X-Tervory-User/-Tenant/-Admin with the valid room key.
    elif variant == 'wrong-signature':
        auth['X-Test-Sign'] = 'wrong'
    elif variant == 'signed-with-another-key':
        auth['X-Test-Sign-Key'] = 'not-the-room-key'
    else:
        auth = headers('wrong-key')
    if isinstance(auth, list):
        response = client.post(f'/memory/{ident}', headers=auth, content=json.dumps(body).encode())
    else:
        response = client.post(f'/memory/{ident}', headers=auth, json=body)
    assert response.status_code in (401, 404, 422) and 'hijacked' not in json.dumps(hermes.rows)
    assert snapshot(hermes) == before


@pytest.mark.asyncio
async def test_signed_assertion_is_bound_to_request_tenant_user_and_time(monkeypatch):
    from chassis.user_assertion import sign_assertion, verify_assertion, SignedUser
    import time
    stamp = int(time.time())
    body, target = b'{"tenant_id":"x"}', '/pipeline/start?mode=plan'
    token = sign_assertion('tisan', SignedUser(TENANT, FOUNDER, 'founder'), 'POST', target, body,
                           key=SIGNING_KEY, now=stamp)
    claimed = set()
    async def claim(tenant, nonce, expiry):
        if (tenant, nonce) in claimed:
            return False
        claimed.add((tenant, nonce))
        return True
    base = dict(key=SIGNING_KEY, product='tisan', tenant_id=TENANT, method='POST', target=target,
                body=body, consume_nonce=claim, now=stamp)
    for changes in ({'body': body+b' '}, {'target': '/memory'}, {'target': target+'&extra=1'},
                    {'tenant_id': OTHER_TENANT}, {'now': stamp+60}, {'now': stamp-1},
                    {'key': 'placeholder-other-key'}, {'product': 'opli'}, {'method': 'GET'}):
        with pytest.raises(PermissionError):
            await verify_assertion(token, **{**base, **changes})
    actor = await verify_assertion(token, **base)
    assert (actor.tenant_id, actor.user_id, actor.role) == (TENANT, FOUNDER, 'founder')
    with pytest.raises(PermissionError):
        await verify_assertion(token, **base)


def test_tank_patch_signs_the_verified_actor_and_applies_to_tank_source(tmp_path, monkeypatch):
    """Current-core proposal uses the shipped signer; obsolete patches stay unapplied."""
    import subprocess
    import os
    core = Path(os.environ['TISAN_CHECK_CORE'])
    for name in ('tank/tisan_requests.py', 'tank/agent_tasks.py', 'tank/task_contract.py',
                 'agents/_chassis/chassis/tank.py', 'agents/_chassis/chassis/task_contract.py',
                 'tests/registry_frozen.golden'):
        dest = tmp_path / name
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes((core / name).read_bytes())
    patch = ROOT / 'tank-patches/gates78-current-core-ingress.patch'
    subprocess.run(['git', 'apply', '--check', str(patch)], cwd=tmp_path, check=True)
    subprocess.run(['git', 'apply', str(patch)], cwd=tmp_path, check=True)
    text = (tmp_path / 'tank/tisan_requests.py').read_text()
    assert "@__import__('product_identity').bind_actor" in text
    assert "scope = {'tenant_id': str(actor.tenant_id), 'user_id': actor.user_id}" in text
    assert 'identity_headers' not in text


def _seeded_counting(monkeypatch):
    """Owner, other-user and other-tenant rows seeded directly; every Hermes request is counted."""
    hermes = FakeHermes()
    for tenant, user in ((TENANT, FOUNDER), (TENANT, OTHER_FOUNDER), (OTHER_TENANT, FOUNDER)):
        hermes.rows.append({'id': str(uuid.uuid4()), 'tenant_id': tenant, 'text': 't', 'claim': 't',
                            'kind': 'tisan.section', 'meta': {'user_id': user, 'subject': 's', 'value': 'v', 'seq': 1}})
    seen = []
    original = hermes.handler
    hermes.handler = lambda request: (seen.append(request.url.path), original(request))[1]
    client, key = room(hermes, monkeypatch)
    return hermes, client, key, hermes.rows[0]['id'], seen


@pytest.mark.parametrize('caller', sorted(CALLERS))
@pytest.mark.parametrize('action', ['view', 'edit', 'forget', 'off'])
def test_refusal_happens_before_any_memory_request(monkeypatch, action, caller):
    """Independent of seeding through memory: a mismatched caller makes ZERO Hermes requests."""
    hermes, client, key, ident, seen = _seeded_counting(monkeypatch)
    before = snapshot(hermes)
    response = control(client, key, action, ident, *CALLERS[caller])
    assert response.status_code == 404 and 'hijacked' not in response.text
    assert seen == [] and snapshot(hermes) == before


@pytest.mark.parametrize('variant', ['unsigned', 'wrong-signature', 'signed-with-another-key', 'admin-only',
                                     'body-user-selector', 'wrong-room-key'])
def test_unverified_identity_makes_no_memory_request(monkeypatch, variant):
    hermes, client, key, ident, seen = _seeded_counting(monkeypatch)
    before = snapshot(hermes)
    auth = headers(key)
    if variant == 'unsigned':
        auth['X-Test-Sign'] = 'none'
    elif variant == 'wrong-signature':
        auth['X-Test-Sign'] = 'wrong'
    elif variant == 'signed-with-another-key':
        auth['X-Test-Sign-Key'] = 'not-the-room-key'
    elif variant == 'admin-only':
        auth.pop('X-Tervory-User')
    elif variant == 'body-user-selector':
        auth = headers(key, OTHER_FOUNDER)
    else:
        auth = headers('wrong-key')
    response = client.get(f'/memory?tenant_id={TENANT}&user_id={FOUNDER}', headers=auth)
    assert response.status_code in (401, 404, 422)
    assert seen == [] and snapshot(hermes) == before


def test_own_signed_control_fails_closed_until_shared_contract_exists(monkeypatch):
    """CURRENT source: the verified owner reaches the handler, which refuses explicitly (503) without reading."""
    import inspect
    hermes, client, key, ident, seen = _seeded_counting(monkeypatch)
    http = httpx.AsyncClient(transport=httpx.MockTransport(hermes.handler))
    client.app.state.memory = MemoryClient(base_url='http://placeholder-hermes', api_key='placeholder-room',
                                           agent='tisan', http=http)  # the REAL shared client, as production
    response = client.get(f'/memory?tenant_id={TENANT}&user_id={FOUNDER}', headers=headers(key))
    if 'user_id' in inspect.signature(MemoryClient.records).parameters:
        assert response.status_code == 200
    else:
        assert response.status_code == 503 and 'shared user-scoped memory contract missing' in response.text
        assert seen == []


@pytest.mark.asyncio
async def test_unintegrated_typed_client_refuses_tisan_without_tiger_authorization(monkeypatch):
    """Current main is intentionally Tiger-only until Head reviews our adapter patch."""
    import os
    spec = importlib.util.spec_from_file_location('chassis.tisan_unreviewed_client',
        Path(os.environ['TISAN_CHECK_CORE']) / 'agents/_chassis/chassis/tank.py')
    baseline = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(baseline)
    from chassis.user_assertion import SignedUser
    async def never(request):
        raise AssertionError('Missing adapter must fail before any HTTP dispatch')
    async with httpx.AsyncClient(transport=httpx.MockTransport(never)) as http:
        tank = baseline.TankClient('http://placeholder-tank', SIGNING_KEY, 'tisan', http)
        with pytest.raises(ValueError, match='Room task client unavailable'):
            await tank.delegate_task(SignedUser(TENANT, FOUNDER, 'founder'), str(uuid.uuid4()),
                                     'tisan.plan', {'request': 'one page', 'contract': builder.manifest()}, [])
