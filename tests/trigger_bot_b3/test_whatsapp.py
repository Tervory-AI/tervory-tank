"""B3 offline proof: actual shared engine, native SQL, vault and fake Cloud API."""
import asyncio
import base64
import hashlib
import hmac
import json
import sys
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import UUID, uuid4
from zoneinfo import ZoneInfo

import asyncpg
import httpx
import pytest
import pytest_asyncio
from fastapi import FastAPI

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tests/trigger_bot_b1'))
from test_database import A, B, DDL
from test_database import database as database  # noqa: PLC0414 -- shared isolated PostgreSQL fixture
from trigger_bot import Bot
from trigger_bot_grounding import Passage
from vault import open_seal
import trigger_bot
import trigger_bot_api as api
import trigger_whatsapp as wa

CLIENT = httpx.AsyncClient
PHONE = 'placeholder-phone'
TOKEN = 'placeholder-whatsapp-token'
SECRET = 'placeholder-whatsapp-app-secret'
VERIFY = 'placeholder-whatsapp-verify-token'
POINT = UUID(int=44)
STAMP = datetime(2026, 11, 3, 12, tzinfo=timezone.utc)


def message(*, sender=None, ident=None, stamp=None, text='placeholder question', kind='text'):
    return {'from': sender or 'placeholder-sender-' + str(uuid4()), 'id': ident or 'placeholder-event-' + str(uuid4()),
            'timestamp': str(int((stamp or STAMP).timestamp())), 'type': kind, 'text': {'body': text}}


def payload(phone=PHONE, incoming=None):
    return {'object': 'whatsapp_business_account', 'entry': [{'changes': [{'field': 'messages', 'value': {
        'messaging_product': 'whatsapp', 'metadata': {'phone_number_id': phone},
        'contacts': [{'profile': {'name': 'placeholder forbidden metadata'}, 'wa_id': 'placeholder forbidden metadata'}],
        'messages': [incoming or message()]}}]}]}


class FakeCloud:
    def __init__(self):
        self.calls, self.mode = [], None

    async def __call__(self, request):
        assert request.url == wa.GRAPH + PHONE + '/messages'
        assert TOKEN not in str(request.url)
        assert request.headers['authorization'] == 'Bearer ' + TOKEN
        body = json.loads(request.content)
        assert body['type'] == 'text' and 'template' not in body
        assert body['messaging_product'] == 'whatsapp' and body['recipient_type'] == 'individual'
        assert len(body['text']['body']) <= 2000
        assert await self.pool.fetchval('SELECT sum(count) FROM tank.trigger_whatsapp_months WHERE tenant_id=$1', A) >= 1
        assert await self.pool.fetchval("SELECT count(*) FROM tank.trigger_whatsapp_events WHERE tenant_id=$1 AND state='sending'", A) >= 1
        self.calls.append(body)
        if self.mode == 'crash':
            raise asyncio.CancelledError('placeholder crash after send')
        if self.mode == 'timeout':
            raise httpx.ReadTimeout('placeholder timeout ' + TOKEN)
        return httpx.Response(self.mode if isinstance(self.mode, int) else 200,
                              json={'messages': [{'id': 'placeholder-outgoing-id'}]})


@pytest_asyncio.fixture
async def b3(database, monkeypatch):
    runtime = SimpleNamespace(pool=lambda: database, box_region=lambda: 'us-east', _admin_pool=None)
    monkeypatch.setitem(sys.modules, 'main', runtime)
    monkeypatch.setenv('TANK_VAULT_KEY', base64.urlsafe_b64encode(b'placeholder-whatsapp-vault-key'.ljust(32, b'0')).decode())
    monkeypatch.setenv('TRIGGER_WHATSAPP_BINDINGS', json.dumps({PHONE: {
        'tenant_id': str(A), 'token_env': 'TRIGGER_WHATSAPP_TOKEN_PLACEHOLDER', 'timezone': 'Africa/Johannesburg'}}))
    monkeypatch.setenv('TRIGGER_WHATSAPP_TOKEN_PLACEHOLDER', TOKEN)
    monkeypatch.setenv('TRIGGER_WHATSAPP_APP_SECRET', SECRET)
    monkeypatch.setenv('TRIGGER_WHATSAPP_VERIFY_TOKEN', VERIFY)
    monkeypatch.setattr(wa, 'now', lambda: STAMP)
    for tenant in (A, B):
        await database.execute('''INSERT INTO tank.trigger_bot_config(tenant_id,enabled,handover_email)
            VALUES($1,true,'placeholder@example.invalid')''', tenant)
    bot = Bot(runtime)
    bot.retrieve = AsyncMock(return_value=[Passage(POINT, A, uuid4(), 'placeholder question',
        'https://placeholder.invalid/source', 'placeholder source', 'faq', 1.0, approved_answer='placeholder answer')])
    bot.route = AsyncMock(side_effect=AssertionError('No real model call allowed'))
    bot.voice = AsyncMock(return_value={})
    bot.live_rig = AsyncMock(side_effect=lambda tenant, p: p)
    mail = SimpleNamespace(send=AsyncMock())
    monkeypatch.setattr(trigger_bot.SmtpMailer, 'from_env', lambda: mail)
    monkeypatch.setattr(api, 'make_bot', lambda: bot)
    cloud = FakeCloud()
    cloud.pool = database
    transport = httpx.MockTransport(cloud)
    monkeypatch.setattr(httpx, 'AsyncClient', lambda *a, **kw: CLIENT(*a, **{**kw, 'transport': transport}))
    app = FastAPI()
    app.include_router(wa.router)
    async with CLIENT(transport=httpx.ASGITransport(app=app), base_url='http://placeholder.invalid') as client:
        yield SimpleNamespace(pool=database, bot=bot, cloud=cloud, mail=mail, client=client,
                              service=wa.WhatsApp(bot), binding=wa.bindings()[PHONE])


async def post(b3, value, *, signature=None, raw=None):
    raw = raw if raw is not None else json.dumps(value).encode()
    signature = signature if signature is not None else 'sha256=' + hmac.new(SECRET.encode(), raw, hashlib.sha256).hexdigest()
    return await b3.client.post('/v1/bot/whatsapp', content=raw,
                               headers={'content-type': 'application/json', 'x-hub-signature-256': signature})


async def seed(b3, count, binding=None, stamp=None):
    binding = binding or b3.binding
    await b3.pool.execute('''INSERT INTO tank.trigger_whatsapp_months(tenant_id,phone_number_id,month,timezone,count)
        VALUES($1,$2,$3,$4,$5) ON CONFLICT(tenant_id,phone_number_id,month) DO UPDATE SET count=$5''',
        binding.tenant, PHONE, wa.month(binding, stamp), binding.zone.key, count)


@pytest.mark.asyncio
async def test_signature_before_parsing_challenge_unknown_and_caps(b3, monkeypatch):
    for signature in ('', 'sha256=' + '0' * 64):
        response = await post(b3, None, signature=signature, raw=b'{placeholder invalid JSON')
        assert response.status_code == 403
    assert (await post(b3, None, raw=b'{placeholder invalid JSON')).status_code == 422
    headers = {'x-whatsapp-mode': 'subscribe', 'x-whatsapp-verify-token': VERIFY, 'x-whatsapp-challenge': '123456'}
    response = await b3.client.get('/v1/bot/whatsapp', headers=headers)
    assert response.status_code == 200 and response.text == '123456'
    headers['x-whatsapp-verify-token'] = 'placeholder-wrong'
    assert (await b3.client.get('/v1/bot/whatsapp', headers=headers)).status_code == 403
    assert (await post(b3, payload('placeholder-unknown'))).status_code == 200
    assert await b3.pool.fetchval('SELECT count(*) FROM tank.trigger_bot_conversations') == 0
    assert (await post(b3, payload(incoming=message(text='placeholder' * 200)))).status_code == 200
    assert await b3.pool.fetchval('SELECT count(*) FROM tank.trigger_bot_conversations') == 0
    assert (await post(b3, payload(), raw=b'x' * 262145)).status_code == 413
    assert not b3.cloud.calls


@pytest.mark.asyncio
async def test_faq_zero_cost_private_identity_dedupe_and_stats(b3, caplog):
    incoming = message(text='placeholder question\nName: placeholder name\nEmail: placeholder@example.invalid')
    assert (await post(b3, payload(incoming=incoming))).status_code == 200
    assert (await post(b3, payload(incoming=incoming))).status_code == 200
    assert len(b3.cloud.calls) == 1
    assert b3.cloud.calls[0]['text']['body'] == 'placeholder answer\nhttps://placeholder.invalid/source'
    b3.bot.route.assert_not_awaited()
    row = await b3.pool.fetchrow('SELECT * FROM tank.trigger_bot_conversations WHERE tenant_id=$1', A)
    assert row['channel'] == 'whatsapp' and str(row['visitor_id']) != incoming['from']
    assert open_seal(row['whatsapp_sealed'], wa.context(A, row['id'])) == {'sender': incoming['from']}
    stored = repr(row) + repr(await b3.pool.fetch('SELECT * FROM tank.trigger_whatsapp_events'))
    assert incoming['from'] not in stored and incoming['id'] not in stored
    assert TOKEN not in caplog.text and incoming['from'] not in caplog.text
    drafts = await b3.pool.fetch("SELECT state,data FROM tank.trigger_bot_drafts WHERE tenant_id=$1 AND kind='lead'", A)
    assert len(drafts) == 1 and drafts[0]['state'] == 'draft'
    assert incoming['from'] not in repr(drafts)
    from fastapi import HTTPException
    with pytest.raises(HTTPException):
        open_seal(row['whatsapp_sealed'], wa.context(B, row['id']))
    assert 'placeholder forbidden metadata' not in stored
    receipt = await b3.pool.fetchrow("SELECT * FROM tank.ledger WHERE tenant_id=$1 AND task_type='trigger.bot.answer'", A)
    assert receipt['model'] == 'code' and receipt['cost_usd'] == 0
    stats = await api.execute('stats', SimpleNamespace(), SimpleNamespace(tenant_id=A), uuid4())
    assert stats['count'] == 1 and stats['weeks'][0]['faq_answers'] == 1
    assert await wa.reply_count(b3.pool, B) == 0


@pytest.mark.asyncio
async def test_sourced_answer_and_foreign_unsupported_handover(b3):
    source = Passage(POINT, A, uuid4(), 'placeholder delivery takes 3 days.', 'https://placeholder.invalid/delivery',
                     'placeholder source', 'website', 1.0)
    b3.bot.retrieve.return_value = [source]
    b3.bot.route.side_effect = None
    b3.bot.route.return_value = SimpleNamespace(content=json.dumps({
        'answer': 'placeholder delivery takes 3 days.', 'passage_ids': [str(POINT)]}), ledger_id=uuid4())
    assert (await post(b3, payload())).status_code == 200
    assert b3.cloud.calls[0]['text']['body'].endswith(source.url)
    assert b3.bot.route.await_count == 1
    b3.bot.retrieve.return_value = [replace(source, tenant_id=B)]
    assert (await post(b3, payload())).status_code == 200
    assert len(b3.cloud.calls) == 1 and b3.mail.send.await_count == 1
    assert await wa.reply_count(b3.pool, A) == 1
    assert b3.bot.route.await_count == 1
    assert await b3.pool.fetchval("SELECT count(*) FROM tank.trigger_bot_conversations WHERE tenant_id=$1 AND status='handed_over'", A) == 1


@pytest.mark.asyncio
async def test_999_1000_then_handover_and_concurrent_boundary(b3):
    await seed(b3, 998)
    for expected in (999, 1000):
        await b3.service.receive(PHONE, b3.binding, message())
        assert await wa.reply_count(b3.pool, A) == expected
    await b3.service.receive(PHONE, b3.binding, message())
    assert len(b3.cloud.calls) == 2 and b3.mail.send.await_count == 1
    await seed(b3, 999)
    barrier = asyncio.Barrier(2)
    passages = b3.bot.retrieve.return_value

    async def competing_retrieval(*args):
        await barrier.wait()
        return passages

    b3.bot.retrieve.side_effect = competing_retrieval
    responses = await asyncio.gather(*(post(b3, payload()) for _ in range(2)))
    assert all(response.status_code == 200 for response in responses)
    assert len(b3.cloud.calls) == 3
    assert await wa.reply_count(b3.pool, A) == 1000
    assert b3.mail.send.await_count == 2


@pytest.mark.asyncio
async def test_timezone_local_month_boundaries_and_not_utc(b3, monkeypatch):
    cases = [('Africa/Johannesburg', '2026-10-31T21:59:59+00:00', '2026-10-31T22:00:00+00:00'),
             ('America/Los_Angeles', '2026-11-01T06:59:59+00:00', '2026-11-01T07:00:00+00:00')]
    for zone, before, after in cases:
        binding = replace(b3.binding, zone=ZoneInfo(zone))
        await b3.pool.execute('DELETE FROM tank.trigger_whatsapp_months WHERE tenant_id=$1', A)
        clock = datetime.fromisoformat(before)
        monkeypatch.setattr(wa, 'now', lambda: clock)
        await seed(b3, 1000, binding)
        assert wa.month(binding).isoformat() == '2026-10-01'
        assert not await wa.available(b3.pool, PHONE, binding)
        sender = 'placeholder-recurring-sender-' + zone
        await b3.service.receive(PHONE, binding, message(sender=sender, stamp=clock))
        clock = datetime.fromisoformat(after)
        assert wa.month(binding).isoformat() == '2026-11-01'
        assert await wa.available(b3.pool, PHONE, binding)
        await b3.service.receive(PHONE, binding, message(sender=sender, stamp=clock))
        assert await b3.pool.fetchval('''SELECT count FROM tank.trigger_whatsapp_months
            WHERE tenant_id=$1 AND phone_number_id=$2 AND month=$3''', A, PHONE, wa.month(binding)) == 1
        # Advancing through UTC midnight alone must not reset the local month.
        if zone == 'Africa/Johannesburg':
            assert wa.month(binding, datetime.fromisoformat('2026-11-01T00:00:00+00:00')) == wa.month(binding)
        else:
            assert wa.month(binding, datetime.fromisoformat('2026-11-01T00:00:00+00:00')).isoformat() == '2026-10-01'
    assert len(b3.cloud.calls) == 2


@pytest.mark.asyncio
async def test_missing_invalid_timezone_window_and_token_handover_no_generation(b3, monkeypatch):
    for zone in (None, '', 'placeholder/Invalid'):
        value = {'tenant_id': str(A), 'token_env': 'TRIGGER_WHATSAPP_TOKEN_PLACEHOLDER'}
        if zone is not None:
            value['timezone'] = zone
        monkeypatch.setenv('TRIGGER_WHATSAPP_BINDINGS', json.dumps({PHONE: value}))
        binding = wa.bindings()[PHONE]
        assert binding.zone is None
        await b3.service.receive(PHONE, binding, message())
    for stamp in (STAMP - timedelta(hours=24), STAMP + timedelta(seconds=1)):
        await b3.service.receive(PHONE, b3.binding, message(stamp=stamp))
    monkeypatch.delenv('TRIGGER_WHATSAPP_TOKEN_PLACEHOLDER')
    await b3.service.receive(PHONE, b3.binding, message())
    b3.bot.retrieve.assert_not_awaited()
    b3.bot.route.assert_not_awaited()
    assert not b3.cloud.calls and b3.mail.send.await_count == 6
    assert await wa.reply_count(b3.pool, A) == 0


@pytest.mark.asyncio
async def test_failed_send_and_crash_never_refund_or_replay(b3):
    for mode in (400, 429, 503, 'timeout', 'crash'):
        b3.cloud.mode = mode
        incoming = message()
        if mode == 'crash':
            with pytest.raises(asyncio.CancelledError):
                await b3.service.receive(PHONE, b3.binding, incoming)
        else:
            await b3.service.receive(PHONE, b3.binding, incoming)
        count = len(b3.cloud.calls)
        await b3.service.receive(PHONE, b3.binding, incoming)
        assert len(b3.cloud.calls) == count
        assert await wa.reply_count(b3.pool, A) == count
    assert len(b3.cloud.calls) == 5
    assert await b3.pool.fetchval("SELECT count(*) FROM tank.trigger_whatsapp_events WHERE tenant_id=$1 AND state='sending'", A) == 1


@pytest.mark.asyncio
async def test_retention_cascades_sealed_sender_and_dedupe_only_for_expired_tenant(b3):
    await b3.service.receive(PHONE, b3.binding, message())
    other = replace(b3.binding, tenant=B)
    await b3.service.receive(PHONE, other, message())
    for table in ('trigger_bot_conversations', 'trigger_bot_messages'):
        # Test-only table selection; runtime SQL is always literal.
        await b3.pool.execute(f"UPDATE tank.{table} SET created_at=now()-interval '13 months' WHERE tenant_id=$1", A)
    counts = await b3.bot.retain_conversations(A)
    assert counts['conversations'] == 1
    assert not await b3.pool.fetch('SELECT * FROM tank.trigger_bot_conversations WHERE tenant_id=$1', A)
    assert not await b3.pool.fetch('SELECT * FROM tank.trigger_whatsapp_events WHERE tenant_id=$1', A)
    assert await b3.pool.fetchval('SELECT count(*) FROM tank.trigger_bot_conversations WHERE tenant_id=$1', B) == 1
    # Aggregate account budget survives customer-data deletion, preventing a free-tier reset by retention.
    assert await wa.reply_count(b3.pool, A) == 1


@pytest.mark.asyncio
async def test_rollout_idempotency_and_restrictive_native_rls(b3):
    await b3.pool.execute(DDL)
    await b3.service.receive(PHONE, b3.binding, message())
    other = replace(b3.binding, tenant=B)
    await b3.service.receive(PHONE, other, message())
    async with b3.pool.acquire() as conn:
        await conn.execute('ALTER TABLE tank.command_threads ENABLE ROW LEVEL SECURITY')
        await conn.execute(DDL)
        await conn.execute(DDL)
        role = 'placeholder_b3_' + uuid4().hex[:12]
        await conn.execute(f'CREATE ROLE {role} NOSUPERUSER NOBYPASSRLS')
        try:
            await conn.execute(f'GRANT USAGE ON SCHEMA tank TO {role}')
            await conn.execute(f'GRANT SELECT,INSERT,UPDATE ON ALL TABLES IN SCHEMA tank TO {role}')
            for table in ('trigger_whatsapp_months', 'trigger_whatsapp_events'):
                flags = await conn.fetchrow("SELECT relrowsecurity,relforcerowsecurity FROM pg_class WHERE oid=$1::regclass", 'tank.' + table)
                assert all(flags)
            await conn.execute('CREATE POLICY placeholder_allow ON tank.trigger_whatsapp_months FOR ALL USING(true) WITH CHECK(true)')
            await conn.execute('CREATE POLICY placeholder_allow ON tank.trigger_whatsapp_events FOR ALL USING(true) WITH CHECK(true)')
            await conn.execute(f'SET ROLE {role}')
            await conn.execute("SELECT set_config('app.tenant_id',$1,false)", str(A))
            for table in ('trigger_whatsapp_months', 'trigger_whatsapp_events'):
                assert all(r['tenant_id'] == A for r in await conn.fetch(f'SELECT tenant_id FROM tank.{table}'))
            with pytest.raises(asyncpg.InsufficientPrivilegeError):
                await conn.execute('''INSERT INTO tank.trigger_whatsapp_months(tenant_id,phone_number_id,month,timezone,count)
                    VALUES($1,$2,$3,$4,1)''', B, PHONE, wa.month(b3.binding), b3.binding.zone.key)
        finally:
            await conn.execute('RESET ROLE')
            await conn.execute(f'DROP OWNED BY {role}')
            await conn.execute(f'DROP ROLE {role}')


@pytest.mark.asyncio
async def test_rebinding_timezone_change_abuse_and_window_closing_fail_closed(b3, monkeypatch):
    await b3.service.receive(PHONE, b3.binding, message())
    # Even a founder configuration move cannot allocate the same phone a second budget.
    foreign = replace(b3.binding, tenant=B)
    b3.bot.retrieve.return_value = [replace(b3.bot.retrieve.return_value[0], tenant_id=B)]
    await b3.service.receive(PHONE, foreign, message())
    assert len(b3.cloud.calls) == 1 and b3.mail.send.await_count == 1
    assert await b3.pool.fetchval('SELECT count(*) FROM tank.trigger_whatsapp_months WHERE tenant_id=$1', B) == 0
    changed = replace(b3.binding, zone=ZoneInfo('America/Los_Angeles'))
    await b3.service.receive(PHONE, changed, message())
    assert len(b3.cloud.calls) == 1 and b3.mail.send.await_count == 2
    b3.bot.retrieve.return_value = [replace(b3.bot.retrieve.return_value[0], tenant_id=A)]
    clock = STAMP
    monkeypatch.setattr(wa, 'now', lambda: clock)

    async def delayed_retrieval(*args):
        nonlocal clock
        clock = STAMP + timedelta(hours=24)
        return b3.bot.retrieve.return_value

    b3.bot.retrieve.side_effect = delayed_retrieval
    await b3.service.receive(PHONE, b3.binding, message())
    assert len(b3.cloud.calls) == 1 and b3.mail.send.await_count == 3
    assert await wa.reply_count(b3.pool, A) == 1
    # The actual inherited per-sender budget refuses the 11th message, without an event or send.
    sender = 'placeholder-limited-sender'
    address = str(UUID(wa.fingerprint(A, PHONE, sender)[:32]))
    from trigger_bot_shared import PgRateLimits
    for _ in range(10):
        await PgRateLimits(b3.pool).consume(str(A), address, '/v1/rig/ask')
    before = await b3.pool.fetchval('SELECT count(*) FROM tank.trigger_whatsapp_events WHERE tenant_id=$1', A)
    await b3.service.receive(PHONE, b3.binding, message(sender=sender, stamp=clock))
    assert await b3.pool.fetchval('SELECT count(*) FROM tank.trigger_whatsapp_events WHERE tenant_id=$1', A) == before
    assert len(b3.cloud.calls) == 1
