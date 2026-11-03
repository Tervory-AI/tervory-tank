"""A2 synthetic contracts; all provider traffic is intercepted, no live settings."""
import asyncio
from concurrent.futures import ProcessPoolExecutor
import json
from pathlib import Path
import time
from types import SimpleNamespace

from cryptography.hazmat.primitives.asymmetric import rsa
import httpx
import jwt
import pytest
from fastapi.testclient import TestClient

from agents.ghost.app import Tank, create_app, refresh_market_lab_intel
from agents.ghost.market_lab_intel import market_lab_advisories, load_market_lab_advisories
from agents.ghost.native_webhooks import verify_cloudflare_notification, verify_google_push
from agents.ghost.never_block import ActionCap
from agents.ghost.smtp_email import SmtpEmailTransport, configured_transport, transport_status
from agents.ghost.store import Store
from agents.ghost.tenant_queue import queue_path_for_tenant
from agents.ghost.threat_queue import ThreatPayloadQueue
from agents.ghost.webhooks import WebhookRejected
import autumbra_google_keys as google_keys


@pytest.fixture(autouse=True)
def placeholder_settings(monkeypatch, tmp_path):
    monkeypatch.setenv('DATA_DIR', str(tmp_path / 'placeholder-state'))
    monkeypatch.setenv('DATABASE_URL', 'postgresql://127.0.0.1/placeholder')
    monkeypatch.setenv('LITELLM_MASTER_KEY', 'placeholder-master')
    monkeypatch.setenv('TANK_API_KEY', 'placeholder-workspace-key')
    for name in ('HOST', 'PORT', 'FROM', 'USER', 'PASSWORD'):
        monkeypatch.delenv('AUTUMBRA_SMTP_' + name, raising=False)


def _cap_worker(root):
    cap = ActionCap(limit=5, clock=lambda: 5000.0, data_dir=root)
    return sum(cap.allow('placeholder-tenant')[0] for _ in range(10))


def test_cap_survives_restart_and_two_processes(tmp_path):
    root = str(tmp_path / 'placeholder-cap')
    assert ActionCap(limit=5, clock=lambda: 5000.0, data_dir=root).allow('placeholder-tenant')[0]
    with ProcessPoolExecutor(max_workers=2) as workers:
        assert sum(workers.map(_cap_worker, [root, root])) == 4
    restarted = ActionCap(limit=5, clock=lambda: 5000.0, data_dir=root)
    assert restarted.allow('placeholder-tenant') == (False, 'actions-per-hour cap (5) reached')
    assert restarted.allow('placeholder-other')[0]
    assert ActionCap(limit=5, clock=lambda: 8601.0, data_dir=root).allow('placeholder-tenant')[0]
    Path(root, 'action-cap.json').write_text('placeholder-corrupt')
    assert not restarted.allow('placeholder-other')[0]


def test_smtp_interrupted_send_is_never_repeated_after_restart(tmp_path):
    calls = []
    class PlaceholderMailer:
        async def send(self, letter):
            calls.append(letter)
            raise SystemExit('placeholder-interruption-after-acceptance')
    kwargs = {'tenant_id': 'placeholder-tenant', 'message_key': 'placeholder-week', 'data_dir': tmp_path}
    first = SmtpEmailTransport(PlaceholderMailer(), **kwargs)
    with pytest.raises(SystemExit):
        first.send(to='placeholder-owner@example.test', subject='placeholder-subject', body='placeholder-body')
    restarted = SmtpEmailTransport(PlaceholderMailer(), **kwargs)
    assert restarted.send(to='placeholder-owner@example.test', subject='placeholder-subject', body='placeholder-body') == {
        'sent': False, 'transport': 'smtp', 'state': 'sending'}
    assert len(calls) == 1
    saved = (tmp_path / 'owner-email-attempts.json').read_text()
    assert 'placeholder-body' not in saved and 'placeholder-owner' not in saved


def test_no_smtp_settings_select_fixture_and_report_it_in_health():
    from agents.ghost.owner_email import DEFAULT_FIXTURE_TRANSPORT
    assert configured_transport('placeholder-tenant', 'placeholder-week') is DEFAULT_FIXTURE_TRANSPORT
    assert transport_status() == 'fixture'
    assert TestClient(create_app()).get('/health').json()['owner_email_transport'] == 'fixture'


def test_smtp_reuses_rig_sender(monkeypatch, tmp_path):
    from agents.rig.rigbox.reserve import SmtpMailer
    from agents.ghost import smtp_email
    monkeypatch.setenv('AUTUMBRA_SMTP_HOST', 'placeholder-smtp.example.test')
    monkeypatch.setenv('AUTUMBRA_SMTP_FROM', 'placeholder-sender@example.test')
    sent = []
    async def send(self, letter):
        assert isinstance(self, SmtpMailer)
        sent.append(letter)
    monkeypatch.setattr(SmtpMailer, 'send', send)
    sender = smtp_email.configured_transport('placeholder-tenant', 'placeholder-week')
    assert sender.send(to='placeholder-owner@example.test', subject='placeholder-subject', body='placeholder-body')['sent']
    assert not sender.send(to='placeholder-owner@example.test', subject='placeholder-subject', body='placeholder-body')['sent']
    assert len(sent) == 1 and transport_status() == 'smtp'


@pytest.fixture
def signing(monkeypatch):
    private = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    public = jwt.algorithms.RSAAlgorithm.to_jwk(private.public_key(), as_dict=True)
    public.update(kid='placeholder-key', alg='RS256', use='sig')
    audience = 'https://placeholder.example.test/push'
    account = 'placeholder-push@placeholder.iam.gserviceaccount.com'
    monkeypatch.setenv('AUTUMBRA_GOOGLE_PUSH_AUDIENCE', audience)
    monkeypatch.setenv('AUTUMBRA_GOOGLE_PUSH_SERVICE_ACCOUNT', account)
    claims = {'iss': 'https://accounts.google.com', 'aud': audience, 'email': account,
              'email_verified': True, 'exp': int(time.time()) + 600}
    def token(**changes):
        return jwt.encode({**claims, **changes}, private, algorithm='RS256', headers={'kid': public['kid']})
    return public, token


def push_body(ident='placeholder-message'):
    return json.dumps({'message': {'messageId': ident, 'data': 'cGxhY2Vob2xkZXI='},
                       'subscription': 'projects/placeholder/subscriptions/placeholder'}).encode()


@pytest.mark.asyncio
@pytest.mark.parametrize('issuer', ['accounts.google.com', 'https://accounts.google.com'])
async def test_google_keys_arrive_only_through_tank_room_key(signing, monkeypatch, tmp_path, issuer):
    public, token = signing
    monkeypatch.setenv('TANK_KEY', 'placeholder-room-key')
    calls = []
    def tank_route(request):
        assert request.url.host == 'tank' and request.url.port == 8000
        assert request.url.path == '/v1/ghost/google/signing-keys'
        assert dict(request.url.params) == {'kid': 'placeholder-key'}
        assert request.headers['X-Tank-Key'] == 'placeholder-room-key'
        assert 'authorization' not in request.headers
        assert request.content in (b'', b'null')
        calls.append(request)
        return httpx.Response(200, json={'keys': [public]})
    async with httpx.AsyncClient(transport=httpx.MockTransport(tank_route)) as http:
        tank = Tank(http)
        bearer = 'Bearer ' + token(iss=issuer)
        await verify_google_push(push_body(), bearer, tank)
        # A valid Pub/Sub token is reused across distinct deliveries.
        await verify_google_push(push_body('placeholder-second-message'), bearer, tank)
        with pytest.raises(WebhookRejected):
            await verify_google_push(push_body(), bearer, tank)
    assert len(calls) == 3
    assert bearer not in (tmp_path / 'placeholder-state/webhook-replay.json').read_text()


@pytest.mark.asyncio
@pytest.mark.parametrize('change', [
    {'aud': 'placeholder-wrong'}, {'iss': 'https://placeholder-wrong.example.test'}, {'exp': 1},
    {'email': 'placeholder-wrong@example.test'}, {'email_verified': False},
])
async def test_google_invalid_claims_are_refused(signing, change):
    public, token = signing
    class PlaceholderTank:
        async def call(self, *_):
            return {'keys': [public]}
    with pytest.raises(WebhookRejected):
        await verify_google_push(push_body(), 'Bearer ' + token(**change), PlaceholderTank())


@pytest.mark.asyncio
async def test_google_bad_signature_unknown_key_and_unavailable_keys_refused(signing):
    public, token = signing
    class PlaceholderTank:
        async def call(self, *_):
            return {'keys': [public]}
    valid = token()
    parts = valid.split('.')
    parts[2] = ('a' if parts[2][0] != 'a' else 'b') + parts[2][1:]
    with pytest.raises(WebhookRejected):
        await verify_google_push(push_body(), 'Bearer ' + '.'.join(parts), PlaceholderTank())
    public['kid'] = 'placeholder-wrong-key'
    with pytest.raises(WebhookRejected):
        # Sign with the original header ID, then make the served key unknown.
        await verify_google_push(push_body(), 'Bearer ' + valid, PlaceholderTank())
    class UnavailableTank:
        async def call(self, *_):
            raise RuntimeError('placeholder-unavailable')
    with pytest.raises(WebhookRejected):
        await verify_google_push(push_body(), 'Bearer ' + token(), UnavailableTank())


@pytest.mark.asyncio
@pytest.mark.parametrize('missing', ['AUTUMBRA_GOOGLE_PUSH_AUDIENCE', 'AUTUMBRA_GOOGLE_PUSH_SERVICE_ACCOUNT'])
async def test_google_empty_settings_refuse_before_fetch(signing, monkeypatch, missing):
    _, token = signing
    monkeypatch.delenv(missing)
    class NoFetch:
        async def call(self, *_):
            pytest.fail('No keys should be fetched with missing settings')
    with pytest.raises(WebhookRejected):
        await verify_google_push(push_body(), 'Bearer ' + token(), NoFetch())


@pytest.mark.asyncio
async def test_tank_google_cache_honours_lifetime_and_bounds_unknown_kid(signing, monkeypatch):
    import access
    public, _ = signing
    clock, calls = [100.0], []
    keys = [dict(public)]
    async def public_get(url, **kwargs):
        assert kwargs == {'limit': 262144}
        calls.append(url)
        if url == google_keys.DISCOVERY:
            return json.dumps({'issuer': 'https://accounts.google.com',
                               'jwks_uri': 'https://www.googleapis.com/oauth2/v3/certs'}).encode(), {'cache-control': 'max-age=3600'}
        assert url == 'https://www.googleapis.com/oauth2/v3/certs'
        return json.dumps({'keys': keys}).encode(), {'cache-control': 'max-age=600', 'age': '20'}
    monkeypatch.setattr(access, 'public_get', public_get)
    cache = google_keys.GoogleKeys(clock=lambda: clock[0])
    assert (await cache.get())['keys'][0]['kid'] == 'placeholder-key'
    assert cache.expires == 680.0
    clock[0] += 61
    keys.append({**public, 'kid': 'placeholder-rotated'})
    result = await asyncio.gather(*(cache.get('placeholder-rotated') for _ in range(8)))
    assert all(any(k['kid'] == 'placeholder-rotated' for k in row['keys']) for row in result)
    assert calls.count('https://www.googleapis.com/oauth2/v3/certs') == 2
    await asyncio.gather(*(cache.get('placeholder-unknown-' + str(i)) for i in range(8)))
    assert len(calls) == 3  # One discovery, initial keys, one refresh.
    clock[0] = cache.expires + 1
    await cache.get('placeholder-key')
    assert len(calls) == 4


def test_cloudflare_native_header_missing_bad_and_replayed(monkeypatch):
    body = b'{"text":"placeholder-cloudflare-dashboard-test"}'
    for header in (None, 'placeholder-wrong'):
        with pytest.raises(WebhookRejected):
            verify_cloudflare_notification(body, header)
    monkeypatch.setenv('AUTUMBRA_CLOUDFLARE_WEBHOOK_SECRET', 'placeholder-secret')
    for header in (None, 'placeholder-wrong'):
        with pytest.raises(WebhookRejected):
            verify_cloudflare_notification(body, header)
    verify_cloudflare_notification(body, 'placeholder-secret')
    with pytest.raises(WebhookRejected):
        verify_cloudflare_notification(body, 'placeholder-secret')


@pytest.mark.asyncio
async def test_market_lab_contract_only_through_tank_and_source_receipt(monkeypatch, tmp_path):
    from agents.ghost.models import PLATFORM_TENANT
    monkeypatch.setenv('TANK_KEY', 'placeholder-room-key')
    monkeypatch.setenv('THREAT_PAYLOAD_QUEUE_ROOT', str(tmp_path / 'placeholder-queues'))
    bundle = {'schema_version': 'market_lab.ioc.v1', 'bundle_id': 'placeholder-bundle', 'paid': False,
              'sources': [{'id': 'placeholder-source', 'name': 'placeholder-public-source',
                           'credit': 'placeholder-credit', 'url': 'https://example.test/placeholder'}],
              'indicators': [{'kind': 'cve', 'value': 'CVE-2026-12345', 'source_ids': ['placeholder-source'],
                              'rating': 'critical', 'url': 'https://www.cisa.gov/placeholder'}]}
    calls = []
    def contract(request):
        assert str(request.url) == 'http://tank:8000/v1/market-lab/intel'
        assert request.headers['x-tank-key'] == 'placeholder-room-key'
        calls.append(request)
        return httpx.Response(200, json=bundle)
    previous = market_lab_advisories()
    store = Store(tmp_path / 'placeholder.sqlite3')
    try:
        async with httpx.AsyncClient(transport=httpx.MockTransport(contract)) as http:
            app = SimpleNamespace(state=SimpleNamespace(http=http, store=store))
            assert (await refresh_market_lab_intel(app))['bundle_id'] == 'placeholder-bundle'
            await refresh_market_lab_intel(app)
        receipts = ThreatPayloadQueue(queue_path_for_tenant(PLATFORM_TENANT)).list_receipts()
        assert len(receipts) == 1
        assert receipts[0]['sources'] == [{'id': 'placeholder-source', 'credit': 'placeholder-credit',
                                         'url': 'https://example.test/placeholder', 'via': 'Market Lab'}]
        assert len(calls) == 2
    finally:
        store.close()
        load_market_lab_advisories(previous)


@pytest.mark.asyncio
async def test_tank_key_route_is_read_only_and_room_scoped(signing, monkeypatch):
    import main
    public, _ = signing
    monkeypatch.setenv('TANK_KEY_GHOST', 'placeholder-ghost-key')
    monkeypatch.setenv('TANK_KEY_BASE', 'placeholder-base-key')
    monkeypatch.setattr(main, 'TANK_API_KEY', 'placeholder-workspace-key')
    monkeypatch.setattr(main, '_agent_keys_synced', True)
    calls = []
    class PlaceholderKeys:
        async def get(self, kid):
            calls.append(kid)
            return {'keys': [public]}
    monkeypatch.setattr(google_keys, 'CACHE', PlaceholderKeys())
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=main.app), base_url='http://tank') as http:
        for key in ('', 'placeholder-base-key', 'placeholder-workspace-key'):
            refused = await http.get('/v1/ghost/google/signing-keys', headers={'x-tank-key': key})
            assert refused.status_code in {401, 403}
        accepted = await http.get('/v1/ghost/google/signing-keys?kid=placeholder-key',
                                  headers={'x-tank-key': 'placeholder-ghost-key'})
        assert accepted.status_code == 200 and accepted.json() == {'keys': [public]}
        assert calls == ['placeholder-key']
        assert (await http.post('/v1/ghost/google/signing-keys',
                               headers={'x-tank-key': 'placeholder-ghost-key'})).status_code == 405


def test_cloudflare_dashboard_test_hits_native_watch_route(monkeypatch):
    monkeypatch.setenv('AUTUMBRA_CLOUDFLARE_WEBHOOK_SECRET', 'placeholder-secret')
    client = TestClient(create_app())
    path = '/ghost/autumbra/webhooks/cloudflare'
    body = {'text': 'placeholder-dashboard-notification'}
    accepted = client.post(path, json=body, headers={'cf-webhook-auth': 'placeholder-secret'})
    assert accepted.status_code == 200 and accepted.json()['accepted'] is True
    assert client.post(path, json=body, headers={'cf-webhook-auth': 'placeholder-secret'}).status_code == 401
    assert client.post(path, json=body, headers={'cf-webhook-auth': 'placeholder-forged'}).status_code == 401


def test_weekly_smtp_transport_claim_is_stable_across_rebuilds(monkeypatch):
    from agents.rig.rigbox.reserve import SmtpMailer
    from agents.ghost.owner_email_jobs import run_weekly_owner_updates
    from agents.ghost.client_settings import ClientAutumbraSettings
    monkeypatch.setenv('AUTUMBRA_SMTP_HOST', 'placeholder-smtp.example.test')
    monkeypatch.setenv('AUTUMBRA_SMTP_FROM', 'placeholder-sender@example.test')
    letters = []
    async def send(self, letter):
        letters.append(letter)
    monkeypatch.setattr(SmtpMailer, 'send', send)
    client = ClientAutumbraSettings(tenant_id='placeholder-tenant', site_name='placeholder-site',
                                   owner_email='placeholder-owner@example.test')
    first = run_weekly_owner_updates([client], receipts_by_tenant={'placeholder-tenant': []})
    second = run_weekly_owner_updates([client], receipts_by_tenant={'placeholder-tenant': []})
    assert first[0]['sent'] and not second[0]['sent']
    assert first[0]['transport'] == 'smtp' and len(letters) == 1
    assert 'Quiet week.' in letters[0]['text']


@pytest.mark.asyncio
async def test_google_replay_refused_for_entire_valid_token_lifetime(signing, monkeypatch):
    from agents.ghost import native_webhooks
    public, token = signing
    clock = [time.time()]
    monkeypatch.setattr(native_webhooks, 'time', SimpleNamespace(time=lambda: clock[0]))
    class PlaceholderTank:
        async def call(self, *_):
            return {'keys': [public]}
    bearer = 'Bearer ' + token(exp=int(clock[0]) + 3600)
    await verify_google_push(push_body(), bearer, PlaceholderTank())
    clock[0] += 601
    with pytest.raises(WebhookRejected):
        await verify_google_push(push_body(), bearer, PlaceholderTank())


@pytest.mark.asyncio
async def test_act_mail_uses_watch_receipts_once_without_enforce_network(monkeypatch, tmp_path):
    from datetime import datetime, timezone
    from agents.ghost import app as watch_app
    from agents.ghost.client_settings import ClientAutumbraSettings, save_settings
    from agents.rig.rigbox.reserve import SmtpMailer
    monkeypatch.setenv('AUTUMBRA_SMTP_HOST', 'placeholder-smtp.example.test')
    monkeypatch.setenv('AUTUMBRA_SMTP_FROM', 'placeholder-sender@example.test')
    letters = []
    async def send(self, letter):
        letters.append(letter)
    monkeypatch.setattr(SmtpMailer, 'send', send)
    assert transport_status() == 'smtp'  # Establish availability before this new action.
    receipt = {'id': 'placeholder-act', 'tenant_id': 'placeholder-tenant', 'applied': True,
               'timestamp': datetime.now(timezone.utc).isoformat()}
    monkeypatch.setattr(watch_app, '_receipts_for_tenant', lambda tenant: [receipt])
    store = Store(tmp_path / 'placeholder-act.sqlite3')
    try:
        save_settings(store, ClientAutumbraSettings(tenant_id='placeholder-tenant', site_name='placeholder-site',
                                                  owner_email='placeholder-owner@example.test'))
        app = SimpleNamespace(state=SimpleNamespace(store=store))
        await watch_app.deliver_act_owner_updates(app)
        await watch_app.deliver_act_owner_updates(app)
        assert len(letters) == 1
        assert letters[0]['to'] == 'placeholder-owner@example.test'
    finally:
        store.close()


@pytest.mark.parametrize('sender', ['', 'placeholder@@example.test', 'placeholder <'])
def test_partial_smtp_configuration_keeps_watch_healthy(monkeypatch, sender):
    from agents.ghost import smtp_email
    monkeypatch.setenv('AUTUMBRA_SMTP_HOST', 'placeholder-smtp.example.test')
    monkeypatch.setenv('AUTUMBRA_SMTP_FROM', sender)
    with pytest.raises(ValueError, match='^mail_not_configured$'):
        smtp_email.settings()
    assert transport_status() == 'unavailable'
    response = TestClient(create_app()).get('/health')
    assert response.status_code == 200
    assert response.json()['owner_email_transport'] == 'unavailable'


@pytest.mark.asyncio
async def test_smtp_activation_skips_history_and_restart_never_resends(monkeypatch, tmp_path):
    from datetime import datetime, timedelta, timezone
    from agents.ghost import app as watch_app, owner_email_jobs, smtp_email
    from agents.ghost.client_settings import ClientAutumbraSettings, save_settings
    from agents.rig.rigbox.reserve import SmtpMailer
    start = datetime(2026, 11, 2, tzinfo=timezone.utc)
    moment = start + timedelta(hours=12)
    monkeypatch.setattr(owner_email_jobs, 'week_bounds', lambda now=None: (start, start + timedelta(days=7)))
    monkeypatch.setattr(smtp_email, 'time', SimpleNamespace(time=lambda: moment.timestamp()))
    old = {'id': 'placeholder-old-act', 'tenant_id': 'placeholder-tenant', 'applied': True,
           'timestamp': (moment - timedelta(seconds=1)).isoformat()}
    receipts, letters = [old], []
    monkeypatch.setattr(watch_app, '_receipts_for_tenant', lambda tenant: receipts)
    async def send(self, letter):
        letters.append(letter)
    monkeypatch.setattr(SmtpMailer, 'send', send)
    assert transport_status() == 'fixture'
    monkeypatch.setenv('AUTUMBRA_SMTP_HOST', 'placeholder-smtp.example.test')
    monkeypatch.setenv('AUTUMBRA_SMTP_FROM', 'placeholder-sender@example.test')
    # Health can observe availability before the scheduler's first scan.
    assert TestClient(create_app()).get('/health').json()['owner_email_transport'] == 'smtp'
    database = tmp_path / 'placeholder-activation.sqlite3'
    store = Store(database)
    try:
        save_settings(store, ClientAutumbraSettings(tenant_id='placeholder-tenant', site_name='placeholder-site',
                                                  owner_email='placeholder-owner@example.test'))
        app = SimpleNamespace(state=SimpleNamespace(store=store))
        await watch_app.deliver_act_owner_updates(app)
        assert letters == []
        receipts.append({**old, 'id': 'placeholder-new-act',
                         'timestamp': (moment + timedelta(seconds=1)).isoformat()})
        await watch_app.deliver_act_owner_updates(app)
        await watch_app.deliver_act_owner_updates(app)
        assert len(letters) == 1
    finally:
        store.close()
    # Recreate Watch state against the same data folder, not a fresh in-memory claim.
    store = Store(database)
    try:
        await watch_app.deliver_act_owner_updates(SimpleNamespace(state=SimpleNamespace(store=store)))
        assert len(letters) == 1
        state = json.loads((tmp_path / 'placeholder-state/owner-email-availability.json').read_text())
        assert state['available_since'] == moment.timestamp()
    finally:
        store.close()


@pytest.mark.parametrize('provider', ['cloudflare', 'google', 'google_workspace'])
def test_verified_native_event_cannot_queue_another_tenant(provider, signing, monkeypatch, tmp_path):
    from agents.ghost import app as watch_app
    public, token = signing
    malicious = {'tenant_id': '00000000-0000-0000-0000-000000000608',
                 'site': 'placeholder-other.example.test', 'address': '203.0.113.8',
                 'raw_log': 'placeholder event from 203.0.113.8'}
    if provider == 'cloudflare':
        monkeypatch.setenv('AUTUMBRA_CLOUDFLARE_WEBHOOK_SECRET', 'placeholder-secret')
        headers = {'cf-webhook-auth': 'placeholder-secret'}
    else:
        malicious.update(json.loads(push_body()))
        headers = {'authorization': 'Bearer ' + token()}
    async def tank_call(self, method, path, **kwargs):
        assert method == 'GET' and path == '/v1/ghost/google/signing-keys?kid=placeholder-key'
        return {'keys': [public]}
    monkeypatch.setattr(watch_app.Tank, 'call', tank_call)
    monkeypatch.setattr(watch_app, 'watch_queue_configured', lambda: True)
    def no_queue(**kwargs):
        pytest.fail('Provider identity cannot authorize any tenant queue')
    monkeypatch.setattr(watch_app, 'enqueue_fixture_attack_for_watch', no_queue)
    response = TestClient(create_app()).post('/ghost/autumbra/webhooks/' + provider,
                                           json=malicious, headers=headers)
    assert response.status_code == 200
    assert response.json()['accepted'] is True and response.json()['stored'] is True
    assert response.json()['queued'] is False and response.json()['queue_receipt'] is None
    saved = (tmp_path / 'placeholder-state/verified-webhook-events.json').read_text()
    assert json.loads(saved)[provider]['provider'] == provider
    assert malicious['tenant_id'] not in saved and malicious['site'] not in saved
    assert 'authorization' not in saved and 'placeholder-secret' not in saved


def test_existing_hmac_path_still_queues_the_verified_tenant(monkeypatch):
    from agents.ghost import app as watch_app
    from agents.ghost.webhooks import EDGE_WEBHOOK_SECRET_ENV, sign_body
    monkeypatch.setenv(EDGE_WEBHOOK_SECRET_ENV, 'placeholder-secret')
    monkeypatch.setenv('TANK_KEY', 'placeholder-room-key')
    monkeypatch.setattr(watch_app, 'watch_queue_configured', lambda: True)
    calls = []
    def enqueue(**kwargs):
        calls.append(kwargs)
        return {'queued': True}
    monkeypatch.setattr(watch_app, 'enqueue_fixture_attack_for_watch', enqueue)
    payload = {'tenant_id': '00000000-0000-0000-0000-000000000608',
               'site': 'placeholder.example.test', 'address': '203.0.113.8',
               'raw_log': 'placeholder event from 203.0.113.8'}
    body = json.dumps(payload).encode()
    timestamp, nonce = str(int(time.time())), 'placeholder-review-hmac'
    signature = sign_body(secret='placeholder-secret', body=body, timestamp=timestamp, nonce=nonce)
    from types import SimpleNamespace
    app = create_app()
    app.state.store = SimpleNamespace(get_state=lambda *args: None)
    response = TestClient(app).post('/ghost/autumbra/webhooks/edge', content=body,
        headers={'x-tank-key': 'placeholder-room-key', 'x-autumbra-signature': signature, 'x-autumbra-timestamp': timestamp, 'x-autumbra-nonce': nonce})
    assert response.status_code == 200 and response.json()['queued'] is True
    assert len(calls) == 1 and calls[0]['tenant_id'] == payload['tenant_id']


@pytest.mark.parametrize('provider', ['cloudflare', 'google', 'google_workspace'])
def test_provider_urls_never_fall_back_to_internal_hmac(provider, monkeypatch):
    from agents.ghost.webhooks import EDGE_WEBHOOK_SECRET_ENV, MAILBOX_WEBHOOK_SECRET_ENV, sign_body
    monkeypatch.setenv(EDGE_WEBHOOK_SECRET_ENV, 'placeholder-internal-key')
    monkeypatch.setenv(MAILBOX_WEBHOOK_SECRET_ENV, 'placeholder-internal-key')
    body, timestamp = b'{}', str(int(time.time()))
    signature = sign_body(secret='placeholder-internal-key', body=body, timestamp=timestamp, nonce=provider)
    response = TestClient(create_app()).post('/ghost/autumbra/webhooks/' + provider, content=body,
        headers={'x-autumbra-signature': signature, 'x-autumbra-timestamp': timestamp, 'x-autumbra-nonce': provider})
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_connected_google_alert_intake_uses_binding_not_body_tenant(signing, monkeypatch, tmp_path):
    import base64
    from types import SimpleNamespace
    from agents.ghost.provider_intake import INDEX_TENANT
    public, token = signing
    tenant, other = '00000000-0000-0000-0000-000000000608', '00000000-0000-0000-0000-000000000609'
    ident = '00000000-0000-0000-0000-000000000610'
    monkeypatch.setenv('TANK_KEY', 'placeholder-room-key')
    app = create_app()
    app.state.store = Store(tmp_path / 'connections.sqlite3')
    app.state.http = None
    async def keys(*args, **kwargs):
        return {'keys': [public]}
    monkeypatch.setattr(Tank, 'call', keys)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url='http://watch') as client:
        binding = {'tenant_id': tenant, 'connection_id': ident,
                   'audience': 'https://placeholder.example.test/push',
                   'service_account': 'placeholder-push@placeholder.iam.gserviceaccount.com',
                   'subscription': 'projects/placeholder/subscriptions/placeholder', 'customer_id': 'C-placeholder'}
        configure = '/ghost/autumbra/connections/google_workspace'
        assert (await client.post(configure, json=binding)).status_code == 404
        assert (await client.post(configure, json=binding, headers={'X-Tank-Key': 'placeholder-room-key'})).status_code == 200
        attack = {**binding, 'tenant_id': other}
        assert (await client.post(configure, json=attack, headers={'X-Tank-Key': 'placeholder-room-key'})).status_code == 409
        path = '/ghost/autumbra/webhooks/google_workspace/' + ident
        def event(message_id, customer='C-placeholder', subscription=binding['subscription']):
            alert = {'customerId': customer, 'alertId': 'placeholder-alert', 'type': 'Suspicious login',
                     'source': 'Google Identity', 'data': {'email': 'private@example.test'}}
            return {'tenant_id': other, 'subscription': subscription,
                    'message': {'messageId': message_id, 'data': base64.b64encode(json.dumps(alert).encode()).decode(),
                    'attributes': {'alertcenter_resource_type': 'ALERT', 'alertcenter_payload_format': 'JSON',
                                   'alertcenter_resource_status': 'CREATED'}}}
        headers = {'authorization': 'Bearer ' + token()}
        assert (await client.post(path, json=event('placeholder-unsigned'))).status_code == 401
        assert (await client.post(path, json=event('placeholder-wrong-sub', subscription='projects/other/subscriptions/other'), headers=headers)).status_code == 401
        assert (await client.post(path, json=event('placeholder-wrong-customer', customer='C-other'), headers=headers)).status_code == 401
        accepted = await client.post(path, json=event('placeholder-valid'), headers=headers)
        assert accepted.status_code == 200
        assert accepted.json()['receipt']['tenant_id'] == tenant
        assert accepted.json()['queued'] is False
        assert (await client.post(path, json=event('placeholder-valid'), headers=headers)).status_code == 401
        rows = app.state.store.get_state(tenant, 'autumbra_workspace_alerts', [])
        assert len(rows) == 1
        assert app.state.store.get_state(other, 'autumbra_workspace_alerts', []) == []
        assert 'private@example.test' not in json.dumps(rows)
        assert 'placeholder-alert' not in json.dumps(rows)
        assert app.state.store.get_state(tenant, 'autumbra_client_settings')['google_workspace_connected'] is True
