"""J4 behavior tests; all payloads and mail transports are local test doubles."""
import copy
import importlib.util
import json
import sys
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from itertools import product
from pathlib import Path
from uuid import UUID, uuid4

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
from pydantic import ValidationError

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('j4_quotes', ROOT / 'agents/tisan/quotes.py')
q = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = q
spec.loader.exec_module(q)
A, B = UUID(int=1), UUID(int=2)
DATA = {'contact': {'email': 'quote@example.invalid'},
        'items': [{'item_id': str(UUID(int=3)), 'quantity': 1}]}


class Pool:
    """SQL boundary double; only tenant-qualified operations are accepted."""
    def __init__(self):
        self.rows, self.events = {}, []
        self.fail_event = False

    def acquire(self):
        return self

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        pass

    @asynccontextmanager
    async def transaction(self):
        before = copy.deepcopy((self.rows, self.events))
        try:
            yield
        except BaseException:
            self.rows, self.events = before
            raise

    async def fetchrow(self, sql, *args):
        sql = ' '.join(sql.split())
        tenant, request = args[:2]
        key = (tenant, request)
        if sql.startswith('INSERT'):
            assert '(tenant_id,id,contact,items,state)' in sql
            self.rows[key] = {'tenant_id': tenant, 'id': request,
                'contact': args[2], 'items': args[3], 'state': 'draft',
                'mail_state': 'pending', 'created_at': datetime.now(timezone.utc)}
        else:
            assert 'WHERE tenant_id=$1 AND id=$2' in sql
            if key not in self.rows:
                return None
            if "SET state=$3" in sql:
                self.rows[key]['state'] = args[2]
            elif "SET mail_state='sending'" in sql:
                row = self.rows[key]
                if row['mail_state'] != 'pending' or row['state'] not in ('submitted', 'acknowledged'):
                    return None
                row['mail_state'] = 'sending'
        return copy.deepcopy(self.rows[key])

    async def fetch(self, sql, tenant, *args):
        assert 'WHERE tenant_id=$1' in sql
        if 'quote_events' in sql:
            return copy.deepcopy([e for e in self.events if e['tenant_id'] == tenant and e['request_id'] == args[0]])
        rows = [r for (t, _), r in self.rows.items() if t == tenant]
        return copy.deepcopy(rows[:args[0]])

    async def execute(self, sql, *args):
        if 'INSERT INTO agent_tisan.quote_events' in sql:
            assert '(tenant_id,request_id,from_state,to_state,actor)' in sql
            if self.fail_event:
                raise RuntimeError('test_event_failure')
            self.events.append(dict(zip(('tenant_id', 'request_id', 'from_state', 'to_state', 'actor'), args),
                happened_at=datetime.now(timezone.utc)))
        else:
            assert 'WHERE tenant_id=$1 AND id=$2' in sql
            self.rows[args[:2]]['mail_state'] = args[2]


async def at_state(store, state):
    row = await store.create(A, 'requester', DATA)
    chain = ['submitted', 'acknowledged', 'quoted']
    if state in ('accepted', 'declined'):
        chain.append(state)
    if state == 'draft':
        return row
    for target in chain:
        row = await store.move(A, row['id'], 'store-actor', target)
        if target == state:
            return row
    raise AssertionError(state)


@pytest.mark.asyncio
@pytest.mark.parametrize('before,after', list(product(q.MOVES, q.MOVES)))
async def test_every_transition_and_refusal(before, after):
    pool = Pool()
    store = q.Quotes(pool)
    row = await at_state(store, before)
    snapshot = copy.deepcopy((pool.rows, pool.events))
    if after in q.MOVES[before]:
        result = await store.move(A, row['id'], 'store-actor', after)
        assert result['state'] == after
        event = (await store.read(A, row['id']))['events'][-1]
        assert event['from_state'] == before and event['to_state'] == after
        assert event['actor'] == 'store-actor' and event['happened_at'].tzinfo is not None
    else:
        with pytest.raises(q.Refused):
            await store.move(A, row['id'], 'store-actor', after)
        assert (pool.rows, pool.events) == snapshot


@pytest.mark.asyncio
async def test_submission_is_approval_and_creation_is_audited():
    store = q.Quotes(Pool())
    row = await store.create(A, 'requester', DATA, submitted=True)
    assert row['state'] == 'submitted'
    events = (await store.read(A, row['id']))['events']
    assert [(e['from_state'], e['to_state'], e['actor']) for e in events] == [
        (None, 'draft', 'requester'), ('draft', 'submitted', 'requester')]
    assert events[0]['happened_at'] <= events[1]['happened_at']


@pytest.mark.asyncio
async def test_other_tenant_cannot_read_list_move_or_email():
    store = q.Quotes(Pool())
    row = await store.create(A, 'requester', DATA, submitted=True)
    assert await store.list(B) == []
    for operation in (store.read(B, row['id']), store.move(B, row['id'], 'other', 'acknowledged'),
                      store.send_acknowledgement(B, row['id'])):
        with pytest.raises(q.Missing):
            await operation
    assert (await store.read(A, row['id']))['state'] == 'submitted'


@pytest.mark.asyncio
@pytest.mark.parametrize('field', ['card', 'card_number', 'cvv', 'bank', 'iban', 'account_number',
                                 'payment', 'financial_details', 'routing_number'])
@pytest.mark.parametrize('location', ['root', 'contact', 'item'])
async def test_financial_fields_refused_before_storage(field, location):
    data = copy.deepcopy(DATA)
    target = {'root': data, 'contact': data['contact'], 'item': data['items'][0]}[location]
    target[field] = 'test-only-rejected-field'
    pool = Pool()
    with pytest.raises(ValidationError):
        await q.Quotes(pool).create(A, 'requester', data, submitted=True)
    assert pool.rows == {} and pool.events == []


@pytest.mark.asyncio
async def test_transaction_rolls_back_if_event_write_fails():
    pool = Pool()
    store = q.Quotes(pool)
    pool.fail_event = True
    with pytest.raises(RuntimeError):
        await store.create(A, 'requester', DATA, submitted=True)
    assert pool.rows == {} and pool.events == []
    pool.fail_event = False
    row = await store.create(A, 'requester', DATA, submitted=True)
    pool.fail_event = True
    with pytest.raises(RuntimeError):
        await store.move(A, row['id'], 'store-actor', 'acknowledged')
    assert (await store.read(A, row['id']))['state'] == 'submitted'


class Mailer:
    def __init__(self, error=None):
        self.letters = []
        self.error = error

    async def send(self, letter):
        self.letters.append(letter)
        if self.error:
            raise self.error


@pytest.mark.asyncio
@pytest.mark.parametrize('wording', [None, '', '{}', '```json\n{}\n```',
    '```json\n{"acknowledgement":{"subject":"", "text":""}}\n```',
    '```json\n{"acknowledgement":{"subject":"test\\nheader", "text":"test"}}\n```'])
async def test_absent_or_invalid_wording_sends_nothing(tmp_path, monkeypatch, wording):
    path = tmp_path / 'QUOTE-EMAILS.md'
    monkeypatch.setattr(q, 'EMAIL_WORDING', path)
    if wording is not None:
        path.write_text(wording)
    store, mailer = q.Quotes(Pool()), Mailer()
    row = await store.create(A, 'requester', DATA, submitted=True)
    before = await store.read(A, row['id'])
    assert await store.send_acknowledgement(A, row['id'], transport=mailer) == {'mail': 'wording_missing'}
    assert mailer.letters == [] and await store.read(A, row['id']) == before


@pytest.mark.asyncio
@pytest.mark.parametrize('error,status', [(None, 'sent'), (ConnectionRefusedError(), 'pending'),
                                         (TimeoutError(), 'uncertain')])
async def test_approved_wording_delivery_is_verbatim_without_state_move(tmp_path, monkeypatch, error, status):
    # Synthetic parser input in tmp_path only; this is not proposed email wording.
    path = tmp_path / 'QUOTE-EMAILS.md'
    letter = {'subject': 'test-subject', 'text': 'test-body'}
    path.write_text('```json\n' + json.dumps({'acknowledgement': letter}) + '\n```')
    monkeypatch.setattr(q, 'EMAIL_WORDING', path)
    pool, mailer = Pool(), Mailer(error)
    store = q.Quotes(pool)
    row = await store.create(A, 'requester', DATA, submitted=True)
    before = (await store.read(A, row['id']))['events']
    assert await store.send_acknowledgement(A, row['id'], transport=mailer) == {'mail': status}
    assert {key: mailer.letters[0][key] for key in letter} == letter
    assert mailer.letters[0]['to'] == DATA['contact']['email']
    after = await store.read(A, row['id'])
    assert after['state'] == 'submitted' and after['events'] == before
    assert after['mail_state'] == status
    if status != 'pending':
        assert await store.send_acknowledgement(A, row['id'], transport=mailer) == {'mail': 'not_pending'}
        assert len(mailer.letters) == 1


@pytest.fixture
def client():
    def guard(key, actor):
        # Boundary double; production mount passes the existing gold founder guard.
        if key != 'test-only':
            raise HTTPException(401)
        if actor != 'test-founder':
            raise HTTPException(404)
    app = FastAPI()
    app.state.pool = Pool()
    q.mount(app, guard)
    return TestClient(app)


HEADERS = {'X-Tank-Key': 'test-only', 'X-Tervory-Admin': 'test-founder'}


def test_api_create_read_list_and_all_store_moves(client):
    response = client.post('/quotes', headers=HEADERS, json={'tenant_id': str(A), 'data': DATA})
    assert response.status_code == 201, response.text
    row = response.json()
    assert row['state'] == 'submitted'
    ref = row['id']
    assert len(client.get(f'/quotes?tenant_id={A}', headers=HEADERS).json()) == 1
    assert client.get(f'/quotes?tenant_id={B}', headers=HEADERS).json() == []
    assert client.get(f'/quotes/{ref}?tenant_id={B}', headers=HEADERS).status_code == 404
    assert client.post(f'/quotes/{ref}/state', headers=HEADERS,
        json={'tenant_id': str(B), 'state': 'acknowledged'}).status_code == 404
    for state in ('acknowledged', 'quoted', 'accepted'):
        response = client.post(f'/quotes/{ref}/state', headers=HEADERS,
            json={'tenant_id': str(A), 'state': state})
        assert response.status_code == 200 and response.json()['state'] == state
    assert client.post(f'/quotes/{ref}/state', headers=HEADERS,
        json={'tenant_id': str(A), 'state': 'declined'}).status_code == 409
    result = client.get(f'/quotes/{ref}?tenant_id={A}', headers=HEADERS).json()
    assert all(e['actor'] == 'test-founder' for e in result['events'])


@pytest.mark.parametrize('headers', [{}, {'X-Tank-Key': 'test-only'}, {'X-Tervory-Admin': 'test-founder'}])
def test_all_api_routes_require_existing_guard(client, headers):
    ref = UUID(int=9)
    for method, url, body in [
        ('POST', '/quotes', {'tenant_id': str(A), 'data': DATA}),
        ('GET', f'/quotes?tenant_id={A}', None),
        ('GET', f'/quotes/{ref}?tenant_id={A}', None),
        ('POST', f'/quotes/{ref}/state', {'tenant_id': str(A), 'state': 'acknowledged'}),
        ('POST', f'/quotes/{ref}/email?tenant_id={A}', None),
    ]:
        assert client.request(method, url, headers=headers, json=body).status_code in (401, 404)


def test_api_refuses_extra_fields_and_invalid_tenants(client):
    body = {'tenant_id': str(A), 'data': DATA, 'bank': {}}
    assert client.post('/quotes', headers=HEADERS, json=body).status_code == 422
    assert client.get('/quotes?tenant_id=invalid', headers=HEADERS).status_code == 422
    assert client.post('/quotes', headers=HEADERS,
        json={'tenant_id': str(A), 'data': {**DATA, 'card': {}}}).status_code == 422
    assert client.get(f'/quotes?tenant_id={A}', headers=HEADERS).json() == []


def test_packaged_paths_and_registration():
    app = (ROOT / 'agents/tisan/app.py').read_text()
    docker = (ROOT / 'agents/tisan/Dockerfile').read_text()
    assert "sys.modules['tisan_gold_sources'].founder" in app
    assert 'agents/tisan/quotes.py agents/tisan/schema.sql /app/' in docker
    assert 'agents/rig/rigbox/reserve.py /app/quote_smtp.py' in docker
    assert q.EMAIL_WORDING == ROOT / 'docs/figma/tisan/QUOTE-EMAILS.md'


@pytest.mark.asyncio
@pytest.mark.parametrize('actor', ['', ' ', 'x' * 257, 'actor\nheader'])
async def test_invalid_actor_is_refused_without_writes(actor):
    pool = Pool()
    with pytest.raises(q.Refused):
        await q.Quotes(pool).create(A, actor, DATA)
    assert pool.rows == {} and pool.events == []


@pytest.mark.asyncio
async def test_unknown_state_and_invalid_list_limits():
    store = q.Quotes(Pool())
    row = await store.create(A, 'requester', DATA)
    with pytest.raises(q.Refused):
        await store.move(A, row['id'], 'actor', 'unknown')
    for limit in (0, 201):
        with pytest.raises(q.Refused):
            await store.list(A, limit)


@pytest.mark.asyncio
@pytest.mark.parametrize('data', [
    {'contact': {'email': 'bad'}, 'items': DATA['items']},
    {'contact': {'email': 'quote@example.invalid\nBcc: victim@example.invalid'}, 'items': DATA['items']},
    {'contact': DATA['contact'], 'items': []},
    {'contact': DATA['contact'], 'items': [{'item_id': 'card-number', 'quantity': 1}]},
    {'contact': DATA['contact'], 'items': [{'item_id': str(UUID(int=3)), 'quantity': 0}]},
    {'contact': DATA['contact'], 'items': [{'item_id': str(UUID(int=3)), 'quantity': True}]},
])
async def test_invalid_contact_and_items_refused_before_storage(data):
    pool = Pool()
    with pytest.raises(ValidationError):
        await q.Quotes(pool).create(A, 'requester', data)
    assert pool.rows == {} and pool.events == []


def test_email_api_missing_wording_preserves_quote(client, tmp_path, monkeypatch):
    monkeypatch.setattr(q, 'EMAIL_WORDING', tmp_path / 'absent.md')
    row = client.post('/quotes', headers=HEADERS, json={'tenant_id': str(A), 'data': DATA}).json()
    assert client.post(f"/quotes/{row['id']}/email?tenant_id={A}", headers=HEADERS).json() == {'mail': 'wording_missing'}
    assert client.get(f"/quotes/{row['id']}?tenant_id={A}", headers=HEADERS).json()['state'] == 'submitted'
