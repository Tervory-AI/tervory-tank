"""J4 designed fields: real founder routes against disposable PostgreSQL only."""
from trigger_signin_fakes import set_founders
import copy
import json
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from uuid import UUID

import asyncpg
import httpx
import pytest
import pytest_asyncio
from fastapi import FastAPI

from test_tisan_quotes import A, B, DATA, ROOT, q, quote_fields
from test_tisan_quotes_postgres import database as database
from chassis.tenant_db import bind_tenant_endpoints, tenant_scope
from agents.tisan import gold_sources

HEADERS = {'X-Tank-Key': 'placeholder-room-key', 'X-Tervory-Admin': 'placeholder-founder'}
OMIT = object()


def text(length):
    return ('placeholder' * (length // 11 + 1))[:length]


def designed():
    data = copy.deepcopy(DATA)
    data['contact'].update(phone='+1 (234) 567-890', company='placeholder company', reply_method='phone')
    data['items'][0].update(notes='placeholder product notes')
    data['items'].append({'type': 'service', 'description': 'placeholder service',
                          'quantity': 2, 'notes': 'placeholder service notes'})
    return data


@pytest_asyncio.fixture
async def api(database, monkeypatch):
    store, admin, raw = database
    monkeypatch.setenv('TANK_KEY', HEADERS['X-Tank-Key'])
    set_founders(monkeypatch, HEADERS['X-Tervory-Admin'])
    app = FastAPI()
    app.state.pool = store.pool
    q.mount(app, gold_sources.founder)  # The actual existing founder/room-key guard.
    bind_tenant_endpoints(app)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url='http://placeholder-room') as client:
        yield client, store, admin, app


async def create(api, data=None):
    client, _, _, _ = api
    return await client.post('/quotes', headers=HEADERS,
                             json={'tenant_id': str(A), 'data': designed() if data is None else data})


async def acknowledged(api):
    client, _, _, _ = api
    response = await create(api)
    assert response.status_code == 201, response.text
    ref = response.json()['id']
    response = await client.post(f'/quotes/{ref}/state', headers=HEADERS,
                                json={'tenant_id': str(A), 'state': 'acknowledged'})
    assert response.status_code == 200, response.text
    return ref


REQUEST_CASES = [
    ('contact.name', text(1), True), ('contact.name', text(120), True),
    ('contact.name', '', False), ('contact.name', text(121), False), ('contact.name', ' ', False),
    ('contact.email', 'placeholder@' + 'p' * 234 + '.invalid', True),
    ('contact.email', 'placeholder@' + 'p' * 235 + '.invalid', False),
    ('contact.email', 'placeholder-invalid', False), ('contact.email', '', False),
    ('contact.phone', '1' * 40, True), ('contact.phone', '1' * 41, False),
    ('contact.phone', '+1 (234) 567-890', True), ('contact.phone', 'placeholder', False),
    ('contact.phone', '+()', False), ('contact.phone', '123\n456', False),
    ('contact.company', '', True), ('contact.company', text(120), True), ('contact.company', text(121), False),
    ('contact.company', None, True),
    ('contact.reply_method', 'email', True), ('contact.reply_method', 'phone', True),
    ('contact.reply_method', 'placeholder', False), ('contact.reply_method', OMIT, False),
    ('item.type', 'product', True), ('item.type', 'service', True), ('item.type', 'placeholder', False),
    ('item.type', OMIT, False),
    ('item.description', text(1), True), ('item.description', text(240), True),
    ('item.description', '', False), ('item.description', text(241), False),
    ('item.quantity', 1, True), ('item.quantity', 10000, True), ('item.quantity', 0, False),
    ('item.quantity', 10001, False), ('item.quantity', 1.5, False), ('item.quantity', True, False),
    ('item.quantity', '1', False),
    ('item.notes', '', True), ('item.notes', text(2000), True), ('item.notes', text(2001), False),
    ('item.notes', None, True),
    ('item.item_id', OMIT, True), ('item.item_id', None, True),
    ('item.item_id', str(UUID(int=3)), True), ('item.item_id', 'placeholder-invalid-id', False),
]


@pytest.mark.asyncio
@pytest.mark.parametrize('path,value,valid', REQUEST_CASES,
                         ids=[f'placeholder-boundary-{i}' for i in range(len(REQUEST_CASES))])
async def test_request_field_edges_are_enforced_before_postgres_writes(api, path, value, valid):
    data = designed()
    section, key = path.split('.')
    target = data['contact'] if section == 'contact' else data['items'][0]
    if value is OMIT:
        target.pop(key, None)
    else:
        target[key] = value
    response = await create(api, data)
    assert response.status_code == (201 if valid else 422), response.text
    assert await api[2].fetchval('SELECT count(*) FROM agent_tisan.quote_requests') == int(valid)
    if valid:
        stored = json.loads(await api[2].fetchval('SELECT contact FROM agent_tisan.quote_requests'))
        assert stored == data['contact']
        assert json.loads(await api[2].fetchval('SELECT items FROM agent_tisan.quote_requests')) == data['items']


@pytest.mark.asyncio
@pytest.mark.parametrize('method,phone,valid', [
    ('email', OMIT, True), ('email', None, True), ('email', '', True),
    ('phone', OMIT, False), ('phone', None, False), ('phone', '', False),
    ('phone', '123', True),
])
async def test_phone_is_required_only_for_phone_reply(api, method, phone, valid):
    data = designed()
    data['contact']['reply_method'] = method
    if phone is OMIT:
        data['contact'].pop('phone')
    else:
        data['contact']['phone'] = phone
    assert (await create(api, data)).status_code == (201 if valid else 422)


@pytest.mark.asyncio
@pytest.mark.parametrize('count,valid', [(0, False), (1, True), (100, True), (101, False)])
async def test_item_count_edges(api, count, valid):
    data = designed()
    data['items'] = [copy.deepcopy(data['items'][0]) for _ in range(count)]
    assert (await create(api, data)).status_code == (201 if valid else 422)


QUOTE_CASES = [
    ('quote_amount', '0.01', True), ('quote_amount', '9007199254740993.01', True),
    ('quote_amount', '0', False), ('quote_amount', '-0.01', False),
    ('quote_amount', '0.001', False), ('quote_amount', '1.230', False),
    ('quote_amount', 'NaN', False), ('quote_amount', 'Infinity', False), ('quote_amount', True, False),
    ('quote_currency', 'USD', True), ('quote_currency', 'usd', True),
    ('quote_currency', 'US', False), ('quote_currency', 'USDD', False),
    ('quote_currency', '123', False), ('quote_currency', ' USD', False),
    ('quote_message', text(1), True), ('quote_message', text(2000), True),
    ('quote_message', '', False), ('quote_message', text(2001), False), ('quote_message', '\n', False),
    ('valid_until', (datetime.now(timezone.utc) + timedelta(days=1)).isoformat(), True),
    ('valid_until', (datetime.now(timezone.utc) - timedelta(seconds=1)).isoformat(), False),
    ('valid_until', (datetime.now(timezone.utc) + timedelta(days=1)).replace(tzinfo=None).isoformat(), False),
    ('valid_until', 9999999999, False),
] + [(field, OMIT, False) for field in q._QUOTE_FIELDS] + [(field, None, False) for field in q._QUOTE_FIELDS]


@pytest.mark.asyncio
@pytest.mark.parametrize('field,value,valid', QUOTE_CASES,
                         ids=[f'placeholder-quote-boundary-{i}' for i in range(len(QUOTE_CASES))])
async def test_quote_edges_and_complete_snapshot_at_transition(api, field, value, valid):
    ref = await acknowledged(api)
    quote = quote_fields()
    if value is OMIT:
        quote.pop(field)
    else:
        quote[field] = value
    response = await api[0].post(f'/quotes/{ref}/state', headers=HEADERS,
                                json={'tenant_id': str(A), 'state': 'quoted', **quote})
    assert response.status_code == (200 if valid else 409), response.text
    row = await api[2].fetchrow('SELECT * FROM agent_tisan.quote_requests WHERE tenant_id=$1 AND id=$2', A, UUID(ref))
    assert row['state'] == ('quoted' if valid else 'acknowledged')
    assert (row['quote_amount'] is not None) == valid
    if valid:
        assert Decimal(response.json()['quote_amount']) == Decimal(quote['quote_amount'])
        assert row['quote_currency'] == str(quote['quote_currency']).upper()
        assert row['valid_until'].tzinfo is not None


@pytest.mark.asyncio
@pytest.mark.parametrize('state', ['draft', 'submitted', 'acknowledged', 'accepted', 'declined'])
@pytest.mark.parametrize('field', q._QUOTE_FIELDS)
async def test_any_quote_field_on_other_moves_is_409_even_if_null(api, state, field):
    ref = await acknowledged(api)
    response = await api[0].post(f'/quotes/{ref}/state', headers=HEADERS,
                                json={'tenant_id': str(A), 'state': state, field: None})
    assert response.status_code == 409
    assert await api[2].fetchval('SELECT state FROM agent_tisan.quote_requests WHERE tenant_id=$1 AND id=$2', A, UUID(ref)) == 'acknowledged'


@pytest.mark.asyncio
async def test_founder_routes_complete_designed_request_to_accepted_with_real_history(api, monkeypatch):
    client, _, admin, _ = api
    from agents.rig.rigbox.reserve import SmtpMailer
    def no_mail(_cls):
        pytest.fail('unapproved wording must stop before SMTP configuration')
    monkeypatch.setattr(SmtpMailer, 'from_env', classmethod(no_mail))
    assert not (ROOT / 'docs/figma/tisan/QUOTE-EMAILS.md').exists()
    assert q.approved_letter() is None
    response = await create(api)
    assert response.status_code == 201
    ref = response.json()['id']
    assert (await client.get(f'/quotes/{ref}?tenant_id={A}')).status_code == 401
    assert (await client.get(f'/quotes/{ref}?tenant_id={A}', headers={**HEADERS, 'X-Tervory-Admin': 'placeholder-not-founder'})).status_code == 404
    assert (await client.get(f'/quotes/{ref}?tenant_id={B}', headers=HEADERS)).status_code == 404
    assert (await client.post(f'/quotes/{ref}/email?tenant_id={A}', headers=HEADERS)).json() == {'mail': 'wording_missing'}
    quote = quote_fields()
    for state in ('acknowledged', 'quoted', 'accepted'):
        response = await client.post(f'/quotes/{ref}/state', headers=HEADERS,
                                     json={'tenant_id': str(A), 'state': state, **(quote if state == 'quoted' else {})})
        assert response.status_code == 200, response.text
    response = await client.get(f'/quotes/{ref}?tenant_id={A}', headers=HEADERS)
    result = response.json()
    contact = json.loads(result['contact']) if isinstance(result['contact'], str) else result['contact']
    items = json.loads(result['items']) if isinstance(result['items'], str) else result['items']
    assert contact == designed()['contact'] and items == designed()['items']
    assert Decimal(str(result['quote_amount'])) == Decimal(quote['quote_amount'])
    assert result['quote_message'] == quote['quote_message'] and result['quote_currency'] == 'USD'
    assert [event['to_state'] for event in result['events']] == ['draft', 'submitted', 'acknowledged', 'quoted', 'accepted']
    assert all(datetime.fromisoformat(event['happened_at']).tzinfo is not None for event in result['events'])
    assert all(event['actor'] == HEADERS['X-Tervory-Admin'] for event in result['events'])
    assert result['mail_state'] == 'pending'
    for state in q.MOVES:
        assert (await client.post(f'/quotes/{ref}/state', headers=HEADERS,
                json={'tenant_id': str(A), 'state': state})).status_code == 409
    assert await admin.fetchval('SELECT count(*) FROM agent_tisan.quote_events') == 5
    with tenant_scope(B):
        async with api[1].pool.acquire() as conn:
            assert await conn.fetchval('SELECT count(*) FROM agent_tisan.quote_requests') == 0
            assert await conn.fetchval('SELECT count(*) FROM agent_tisan.quote_events') == 0


@pytest.mark.asyncio
@pytest.mark.parametrize('field', q._QUOTE_FIELDS)
async def test_snapshot_cannot_change_in_api_or_direct_sql(api, field):
    ref = await acknowledged(api)
    quote = quote_fields()
    assert (await api[0].post(f'/quotes/{ref}/state', headers=HEADERS,
        json={'tenant_id': str(A), 'state': 'quoted', **quote})).status_code == 200
    before = await api[2].fetchrow('SELECT * FROM agent_tisan.quote_requests WHERE tenant_id=$1 AND id=$2', A, UUID(ref))
    assert (await api[0].post(f'/quotes/{ref}/state', headers=HEADERS,
        json={'tenant_id': str(A), 'state': 'quoted', **quote})).status_code == 409
    values = {key: before[key] for key in q._QUOTE_FIELDS}
    values[field] = None
    with pytest.raises(asyncpg.CheckViolationError):
        await api[2].execute('''UPDATE agent_tisan.quote_requests
            SET quote_amount=$3,quote_currency=$4,valid_until=$5,quote_message=$6
            WHERE tenant_id=$1 AND id=$2''', A, UUID(ref), *(values[key] for key in q._QUOTE_FIELDS))
    after = await api[2].fetchrow('SELECT * FROM agent_tisan.quote_requests WHERE tenant_id=$1 AND id=$2', A, UUID(ref))
    assert dict(after) == dict(before)


@pytest.mark.asyncio
@pytest.mark.parametrize('state', ['submitted', 'quoted'])
async def test_legacy_request_reads_without_fabricating_missing_fields(api, state):
    ref = UUID(int=123)
    old_contact = {'email': 'placeholder-legacy@example.invalid'}
    old_items = [{'item_id': str(UUID(int=3)), 'quantity': 1}]
    await api[2].execute('''INSERT INTO agent_tisan.quote_requests (tenant_id,id,contact,items,state)
        VALUES ($1,$2,$3::jsonb,$4::jsonb,$5)''', A, ref, json.dumps(old_contact), json.dumps(old_items), state)
    response = await api[0].get(f'/quotes/{ref}?tenant_id={A}', headers=HEADERS)
    assert response.status_code == 200
    row = response.json()
    assert json.loads(row['contact']) == old_contact and json.loads(row['items']) == old_items
    assert all(field not in row for field in q._QUOTE_FIELDS)
    rows = (await api[0].get(f'/quotes?tenant_id={A}', headers=HEADERS)).json()
    assert all(field not in rows[0] for field in q._QUOTE_FIELDS)
    assert (await api[0].get(f'/quotes/{ref}?tenant_id={B}', headers=HEADERS)).status_code == 404


@pytest.mark.asyncio
async def test_actual_quote_lifespan_reapplies_new_schema_as_room_owner(api):
    from chassis.roles import apply_roles
    await apply_roles(api[2], {'AGENT_DB_PASSWORD_TISAN': 'placeholder-local-test-password'})
    async with api[3].router.lifespan_context(api[3]):
        columns = await api[2].fetch('''SELECT column_name FROM information_schema.columns
            WHERE table_schema='agent_tisan' AND table_name='quote_requests'
            AND column_name IN ('quote_amount','quote_currency','valid_until','quote_message')''')
        assert {row['column_name'] for row in columns} == set(q._QUOTE_FIELDS)
    async with api[3].router.lifespan_context(api[3]):
        pass


@pytest.mark.asyncio
@pytest.mark.parametrize('path', ['contact.name', 'contact.company', 'item.description', 'item.notes', 'quote_message'])
@pytest.mark.parametrize('control', ['\x00', '\x01', '\r', '\x1f', '\x7f', '\x85', '\x9f'])
async def test_control_characters_are_422_before_database_writes(api, path, control):
    value = 'placeholder' + control + 'text'
    if path == 'quote_message':
        ref = await acknowledged(api)
        response = await api[0].post(f'/quotes/{ref}/state', headers=HEADERS,
            json={'tenant_id': str(A), 'state': 'quoted', **quote_fields(), 'quote_message': value})
        assert await api[2].fetchval('SELECT count(*) FROM agent_tisan.quote_requests WHERE quote_amount IS NOT NULL') == 0
    else:
        data = designed()
        section, field = path.split('.')
        target = data['contact'] if section == 'contact' else data['items'][0]
        target[field] = value
        response = await create(api, data)
        assert await api[2].fetchval('SELECT count(*) FROM agent_tisan.quote_requests') == 0
    assert response.status_code == 422, response.text


@pytest.mark.asyncio
@pytest.mark.parametrize('control', ['\n', '\t'])
async def test_newline_and_tab_remain_valid_text(api, control):
    data = designed()
    for field in ('name', 'company'):
        data['contact'][field] = 'placeholder' + control + 'text'
    for field in ('description', 'notes'):
        data['items'][0][field] = 'placeholder' + control + 'text'
    response = await create(api, data)
    assert response.status_code == 201, response.text
    ref = response.json()['id']
    assert (await api[0].post(f'/quotes/{ref}/state', headers=HEADERS,
        json={'tenant_id': str(A), 'state': 'acknowledged'})).status_code == 200
    assert (await api[0].post(f'/quotes/{ref}/state', headers=HEADERS,
        json={'tenant_id': str(A), 'state': 'quoted', **quote_fields(),
              'quote_message': 'placeholder' + control + 'text'})).status_code == 200


@pytest.mark.asyncio
@pytest.mark.parametrize('amount,valid', [('9999999999999999.99', True), ('10000000000000000', False), ('10000000000000000.00', False)])
async def test_decimal_precision_bound_at_api_and_database(api, amount, valid):
    ref = await acknowledged(api)
    quote = {**quote_fields(), 'quote_amount': amount}
    response = await api[0].post(f'/quotes/{ref}/state', headers=HEADERS,
        json={'tenant_id': str(A), 'state': 'quoted', **quote})
    assert response.status_code == (200 if valid else 409), response.text
    if valid:
        assert response.json()['quote_amount'] == amount
    else:
        with pytest.raises(asyncpg.CheckViolationError):
            await api[2].execute('''UPDATE agent_tisan.quote_requests SET state='quoted',
                quote_amount=$3,quote_currency=$4,valid_until=$5,quote_message=$6
                WHERE tenant_id=$1 AND id=$2''', A, UUID(ref), Decimal(amount), 'USD',
                datetime.now(timezone.utc) + timedelta(days=1), 'placeholder quote')
        assert await api[2].fetchval('SELECT state FROM agent_tisan.quote_requests WHERE tenant_id=$1 AND id=$2', A, UUID(ref)) == 'acknowledged'


@pytest.mark.asyncio
async def test_unicode_uppercase_expansion_is_not_a_currency_code(api):
    ref = await acknowledged(api)
    assert (await api[0].post(f'/quotes/{ref}/state', headers=HEADERS,
        json={'tenant_id': str(A), 'state': 'quoted', **quote_fields(), 'quote_currency': 'ßd'})).status_code == 409


@pytest.mark.asyncio
async def test_database_check_refusal_is_409_and_rolls_back_quote_and_event(api):
    ref = await acknowledged(api)
    await api[2].execute("ALTER TABLE agent_tisan.quote_requests ADD CONSTRAINT placeholder_no_quote CHECK (state <> 'quoted')")
    response = await api[0].post(f'/quotes/{ref}/state', headers=HEADERS,
        json={'tenant_id': str(A), 'state': 'quoted', **quote_fields()})
    assert response.status_code == 409
    row = await api[2].fetchrow('SELECT state,quote_amount FROM agent_tisan.quote_requests WHERE tenant_id=$1 AND id=$2', A, UUID(ref))
    assert row['state'] == 'acknowledged' and row['quote_amount'] is None
    assert await api[2].fetchval('SELECT count(*) FROM agent_tisan.quote_events') == 3


@pytest.mark.asyncio
@pytest.mark.parametrize('terminal,target', [(final, target) for final in ('accepted', 'declined') for target in q.MOVES if target != final])
async def test_database_trigger_refuses_all_state_changes_after_a_final_decision(api, terminal, target):
    ref = await acknowledged(api)
    for state in ('quoted', terminal):
        response = await api[0].post(f'/quotes/{ref}/state', headers=HEADERS,
            json={'tenant_id': str(A), 'state': state, **(quote_fields() if state == 'quoted' else {})})
        assert response.status_code == 200, response.text
    with pytest.raises(asyncpg.CheckViolationError):
        await api[2].execute('UPDATE agent_tisan.quote_requests SET state=$3 WHERE tenant_id=$1 AND id=$2', A, UUID(ref), target)
    assert await api[2].fetchval('SELECT state FROM agent_tisan.quote_requests WHERE tenant_id=$1 AND id=$2', A, UUID(ref)) == terminal
