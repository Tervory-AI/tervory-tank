"""Acceptance of store rooms through real handlers and fixture transports only."""
import hashlib
import hmac
import json
from pathlib import Path

import httpx
import pytest

from test_rig_rooms import A, B, ROOT, SETTINGS, KEY, TOKEN, FakeCoolify, create_app, RigError


@pytest.mark.asyncio
async def test_chats_two_store_rooms_keep_search_cart_quote_and_destroy_isolated(monkeypatch, tmp_path, checkpoint='destroy'):
    """Actual Command turn + Confirm, signed lifecycle and two real PostgreSQL rooms."""
    import asyncpg
    from contextlib import AsyncExitStack
    from types import SimpleNamespace
    from uuid import UUID, uuid4
    from fastapi import FastAPI
    import access
    import command
    import ghost_routes
    monkeypatch.setenv("DATABASE_URL", "postgresql://fixture.invalid/unused")
    monkeypatch.setenv("LITELLM_MASTER_KEY", "fixture-unused")
    monkeypatch.setenv("TANK_API_KEY", "fixture-tank")
    import main
    from test_rig_postgres import _admin_url, _create_database, _database_url, _drop_database
    from rigbox.api import mount
    from rigbox.cart_api import mount as mount_cart
    from rigbox.cart import Cart
    from rigbox.commerce import Platform
    from rigbox.quotes.api import mount as mount_quotes
    from rigbox.quotes.service import QuoteService
    from rigbox.quotes.store import PgQuotes
    from rigbox.retailer_server import create_retailer_app
    from rigbox.service import RecordingHandoff, hash_key
    from rigbox.store import PgStore
    from rigbox import rooms
    from fixtures.rig_quote_sample import seed
    from test_rig_cart import Woo, CREDS

    admin = _admin_url()
    databases = []
    fake = FakeCoolify()
    routes, data_planes, stores, provider_calls, bucket = {}, {}, {}, {}, {}
    actor = command.Actor(UUID(A), 'fixture-founder', True, frozenset({'rig'}), True)
    monkeypatch.setenv('TERVORY_ADMIN_USER_IDS', actor.user_id)
    monkeypatch.setenv('RIG_LIFECYCLE_KEY', KEY)
    monkeypatch.setattr(rooms, 'SNAPSHOT_CHUNK_BYTES', 2048)
    monkeypatch.setenv('RIG_RETAILER_KEY', 'fixture-control')
    for name, value in zip(SETTINGS, ('https://fixture.invalid', TOKEN, 'fixture-project', 'fixture-server', 'fixture-test', 'fixture-source')):
        monkeypatch.setenv(name, value)
    monkeypatch.delenv('RIG_ROOM_TENANT', raising=False)
    original_client = httpx.AsyncClient

    class Dispatch(httpx.AsyncBaseTransport):
        async def handle_async_request(self, request):
            if request.url.host == 'fixture.invalid':
                return fake(request)
            if request.url.host == 'enforce-lifecycle':
                return await httpx.ASGITransport(app=lifecycle).handle_async_request(request)
            if request.url.host.startswith('rig-room-'):
                tenant = request.url.host.removeprefix('rig-room-')
                assert tenant in routes
                if not any(app['name'] == 'rig-room-' + tenant for app in fake.apps):
                    raise httpx.ConnectError('Fixture room has been destroyed', request=request)
                with monkeypatch.context() as local:
                    local.setenv('RIG_ROOM_TENANT', tenant)
                    local.setenv('DATA_DIR', str(tmp_path / tenant))
                    target = routes[tenant] if request.url.port == 8003 else data_planes[tenant]
                    return await httpx.ASGITransport(app=target).handle_async_request(request)
            if request.url.host.endswith('.r2.cloudflarestorage.com'):
                assert request.method == 'PUT'
                bucket[request.url.path] = request.content
                return httpx.Response(200, content=b'')
            raise AssertionError('Unexpected external request: ' + str(request.url))

    def client_factory(*args, **kwargs):
        if kwargs.get('transport') is None:
            kwargs['transport'] = Dispatch()
        return original_client(*args, **kwargs)

    monkeypatch.setattr(httpx, 'AsyncClient', client_factory)
    lifecycle = create_app()
    monkeypatch.setenv('R2_ACCOUNT_ID', 'a' * 32)
    monkeypatch.setenv('R2_ACCESS_KEY_ID_RIG', 'fixture-r2-access')
    monkeypatch.setenv('R2_SECRET_ACCESS_KEY_RIG', 'fixture-r2-secret')
    monkeypatch.setenv('AGENT_NAME', 'rig')
    monkeypatch.setenv('TANK_REGION', 'us-east')
    try:
        async with AsyncExitStack() as stack:
            async def database(label):
                name = 'rig_rooms_' + label + '_' + uuid4().hex[:10]
                await _create_database(admin, name)
                databases.append(name)
                pool = await asyncpg.create_pool(_database_url(admin, name), min_size=1, max_size=5)
                stack.push_async_callback(pool.close)
                return pool

            control = await database('control')
            async with control.acquire() as conn:
                await conn.execute((ROOT / 'tank/schema.sql').read_text())
            tank = FastAPI()
            tank.include_router(access.router)
            tank.include_router(command.router)
            tank.dependency_overrides[command.identity] = lambda: actor
            monkeypatch.setattr(main, 'app', tank)
            monkeypatch.setattr(main, 'pool', lambda: control)
            monkeypatch.setattr(main, 'box_region', lambda: 'us-east')
            monkeypatch.setattr(main, 'TANK_API_KEY', 'fixture-tank')
            shared_http = await stack.enter_async_context(client_factory())
            monkeypatch.setattr(ghost_routes, 'runtime', lambda: SimpleNamespace(_http=shared_http))
            tank_client = await stack.enter_async_context(client_factory(transport=httpx.ASGITransport(app=tank), base_url='http://tank'))

            async def chat(text):
                created = await tank_client.post('/v1/command/threads', json={'title': 'Store room fixture'})
                assert created.status_code == 200, created.text
                thread = created.json()['thread_id']
                turn = await tank_client.post(f'/v1/command/threads/{thread}/turn', json={'text': text})
                assert turn.status_code == 200, turn.text
                async with control.acquire() as conn:
                    state = json.loads(await conn.fetchval('SELECT state FROM tank.command_threads WHERE thread_id=$1', UUID(thread)))
                assert len(state['cards']) == 1, (state, turn.text)
                card = next(iter(state['cards'].values()))
                assert card['status'] == 'pending' and card['tool'] == text
                before = len([call for call in fake.calls if call.method == 'POST'])
                confirmed = await tank_client.post('/v1/command/cards/' + card['card_id'], json={'action': 'confirm'})
                assert confirmed.status_code == 200, confirmed.text
                result = confirmed.json()
                assert result['status'] == 'confirmed', result
                replay = await tank_client.post('/v1/command/cards/' + card['card_id'], json={'action': 'confirm'})
                assert replay.status_code == 200 and replay.json()['status'] == 'confirmed'
                assert len([call for call in fake.calls if call.method == 'POST']) - before == int(text == 'rig.store.onboard')
                return result['result']

            for tenant in (A, B):
                actor = command.Actor(UUID(tenant), 'fixture-founder', True, frozenset({'rig'}), True)
                result = await chat('rig.store.onboard')
                assert result['status'] == 'created' and result['cost_usd'] == 0
            assert len(fake.apps) == 2
            listed = await chat('rig.rooms.list')
            assert [row['name'] for row in listed['applications']] == ['rig-room-' + B]
            from rig_rooms import catalogue_tenants
            assert set(await catalogue_tenants(control, [A, B])) == {A, B}
            async with control.acquire() as conn:
                assert await conn.fetchval("SELECT count(*) FROM tank.rig_rooms WHERE state='created'") == 2
            if checkpoint == 'onboard':
                return

            for tenant, sku in ((A, 'ROOM-A'), (B, 'ROOM-B')):
                pool = await database(sku.lower().replace('-', '_'))
                store = PgStore(pool)
                await store.apply_schema()
                with monkeypatch.context() as local:
                    local.setenv('RIG_ROOM_TENANT', tenant)
                    await rooms.bind_database(pool)
                    await seed(store, tenant)
                    await store.upsert_product(tenant, {'id': sku, 'sku': sku, 'name': sku + ' only', 'brand': 'Fixture',
                        'category': 'core', 'price': 10, 'currency': 'USD', 'image_url': '', 'url': '', 'active': True, 'attributes': {}})
                    await store.put_key(tenant, hash_key('rk_pub_' + sku.replace('-', '_')), 'publishable', ['https://fixture.store'])
                    await store.put_key(tenant, hash_key('rk_adm_' + sku.replace('-', '_')), 'admin', [])
                    await store.save_commerce_config(tenant, {'mode': 'cart', 'region': 'US', 'platform': 'woocommerce',
                        'site': 'https://fixture.store', 'vault_name': 'fixture', 'delivery': {'ship_days': 2}, 'products': {sku: {'product_id': 1}}})
                sender = RecordingHandoff()
                service = QuoteService(store, None, sender, PgQuotes(pool))
                provider = Woo()
                provider_calls[tenant] = provider.calls
                provider_http = await stack.enter_async_context(original_client(transport=httpx.MockTransport(provider)))
                async def platform(owner, config, client=provider_http):
                    assert owner in (A, B)
                    return Platform(client, config, CREDS)
                service.cart = Cart(service, platform)
                public = FastAPI()
                public.state.rig = service
                mount(public)
                mount_cart(public)
                mount_quotes(public)
                public.add_middleware(rooms.RoomGateway)
                data_planes[tenant] = public
                routes[tenant] = create_retailer_app(service)
                stores[tenant] = (store, service, sender)
                (tmp_path / tenant).mkdir()

            shared = FastAPI()
            shared.add_middleware(rooms.RoomGateway)
            public_client = await stack.enter_async_context(client_factory(transport=httpx.ASGITransport(app=shared), base_url='https://rig.tervory.com'))
            def base(tenant):
                return rooms.PREFIX + tenant + '/v1/rig'
            def headers(sku):
                return {'X-Rig-Key': 'rk_pub_' + sku.replace('-', '_'), 'Origin': 'https://fixture.store'}
            searched = await public_client.get(base(A) + '/search?q=ROOM-A', headers=headers('ROOM-A'))
            assert searched.status_code == 200 and 'ROOM-A only' in searched.text and 'ROOM-B only' not in searched.text
            foreign = await public_client.get(base(B) + '/search?q=ROOM-A', headers=headers('ROOM-A'))
            assert foreign.status_code == 401
            session = (await public_client.post(base(A) + '/cart/session', headers=headers('ROOM-A'), json={})).json()['session']
            added = await public_client.post(base(A) + '/cart/add', headers=headers('ROOM-A'), json={'session': session, 'product_id': 'ROOM-A', 'quantity': 1})
            assert added.status_code == 200 and added.json()['lines'][0]['product_id'] == 'ROOM-A', added.text
            other_cart = await public_client.post(base(B) + '/cart/view', headers=headers('ROOM-B'), json={'session': session})
            assert other_cart.status_code == 200 and other_cart.json()['lines'] == []
            assert provider_calls[A] and not provider_calls[B]
            quote = await public_client.post(base(A) + '/quote', headers=headers('ROOM-A'), json={'product_id': 'ROOM-A', 'contact': {'name': 'Fixture Shopper', 'email': 'fixture@example.test'}})
            assert quote.status_code == 200, quote.text
            reference = quote.json()['request_id']
            assert await stores[A][1].quote_store.status(A, reference)
            assert await stores[B][1].quote_store.status(B, reference) is None
            own_delivery = await public_client.get(base(A) + '/admin/quotes/' + reference + '/delivery', headers={'X-Rig-Key': 'rk_adm_ROOM_A'})
            assert own_delivery.status_code == 200
            foreign_delivery = await public_client.get(base(B) + '/admin/quotes/' + reference + '/delivery', headers={'X-Rig-Key': 'rk_adm_ROOM_B'})
            assert foreign_delivery.status_code == 404
            assert stores[A][2].sent and not stores[B][2].sent
            actor = command.Actor(UUID(A), 'fixture-founder', True, frozenset({'rig'}), True)
            assert await access.rig_request(actor, 'panel', {})
            # Even possession of the private control credential cannot write a foreign tenant into a room.
            response = await shared_http.post('http://rig-room-' + A + ':8003/internal/retailer/settings',
                headers={'x-rig-retailer-key': 'fixture-control'}, json={'tenant_id': B, 'data': {'name': 'foreign'}})
            assert response.status_code == 403
            if checkpoint == 'isolation':
                return

            # No DELETE is sent when bucket retention cannot be acknowledged.
            original_archive = rooms.archive
            async def unavailable(*args):
                raise RigError('unavailable', 'Fixture bucket unavailable.', 503)
            with monkeypatch.context() as local:
                local.setattr(rooms, 'archive', unavailable)
                failed = await chat_failure(tank_client, control, actor)
                assert failed and len(fake.apps) == 2
            assert rooms.archive is original_archive
            result = await chat('rig.store.destroy')
            assert result['status'] == 'destroyed'
            assert [app['name'] for app in fake.apps] == ['rig-room-' + B]
            assert await catalogue_tenants(control, [A, B]) == [B]
            gone = await public_client.get(base(A) + '/search?q=ROOM-A', headers=headers('ROOM-A'))
            assert gone.status_code == 503
            snapshot = json.loads(bucket['/tervory-rig/us-east/' + A + '/backups/room-retained.json'])
            assert snapshot['tenant_id'] == A
            assert len(snapshot['tables']['products']) > 1
            restored = {}
            for table, pieces in snapshot['tables'].items():
                restored[table] = []
                for piece in pieces:
                    data = bucket['/tervory-rig/' + piece['key']]
                    assert hashlib.sha256(data).hexdigest() == piece['sha256']
                    restored[table].extend(json.loads(data))
            assert {row['sku'] for row in restored['products']} >= {'ROOM-A'}
            assert all(str(row['tenant_id']) == A for rows in restored.values() for row in rows)
            assert await stores[A][0].products(A)  # Retained database volume is untouched.
            with pytest.raises(asyncpg.RaiseError, match='archived'):
                await stores[A][0].put_retailer(A, 'fixture', None, None, 'forbidden after archive')
            after = await public_client.get(base(B) + '/search?q=ROOM-B', headers=headers('ROOM-B'))
            assert after.status_code == 200 and 'ROOM-B only' in after.text and 'ROOM-A only' not in after.text
            assert (await access.rig_request(command.Actor(UUID(B), actor.user_id, True), 'panel', {}))
            from rig_rooms import endpoint
            from fastapi import HTTPException
            with pytest.raises(HTTPException):
                await endpoint(control, actor)
    finally:
        for name in reversed(databases):
            await _drop_database(admin, name)


async def chat_failure(client, pool, actor):
    """Exercise an already confirmed destroy while the real archive boundary fails."""
    from trigger_commands import CONFIRMED
    from uuid import uuid4
    token = CONFIRMED.set((actor.tenant_id, actor.user_id, uuid4(), 'rig.store.destroy', {}))
    try:
        response = await client.post('/v1/access/rig/rooms/destroy', json={})
        assert response.status_code == 503
        async with pool.acquire() as conn:
            assert await conn.fetchval('SELECT state FROM tank.rig_rooms WHERE tenant_id=$1', actor.tenant_id) == 'created'
        return True
    finally:
        CONFIRMED.reset(token)


def test_room_commands_require_admin_and_never_accept_foreign_tenant(monkeypatch):
    import command
    from fastapi import HTTPException
    from uuid import UUID
    monkeypatch.setenv('TERVORY_ADMIN_USER_IDS', 'fixture-founder')
    member = command.Actor(UUID(A), 'fixture-member', False, frozenset({'rig'}))
    admin = command.Actor(UUID(A), 'fixture-admin', False, frozenset({'rig'}), True)
    unlicensed = command.Actor(UUID(A), 'fixture-admin', False, frozenset(), True)
    for tool in ('rig.store.onboard', 'rig.rooms.list', 'rig.store.destroy'):
        assert tool not in command.allowed_tools(member)
        assert tool not in command.allowed_tools(unlicensed)
        assert tool in command.allowed_tools(admin)
        assert not command.ADAPTERS[tool].paid
        with pytest.raises(HTTPException) as denied:
            command.validate_action(command.PlannedAction(tool=tool, arguments={}), member)
        assert denied.value.status_code == 403
        with pytest.raises(HTTPException) as foreign:
            command.validate_action(command.PlannedAction(tool=tool, arguments={'tenant_id': B}), admin)
        assert foreign.value.status_code == 422


def test_load_harness_records_p95_and_memory_and_cleans_only_its_fixtures(monkeypatch, tmp_path):
    import importlib.util
    import subprocess
    from types import SimpleNamespace
    path = ROOT / 'tests/load/rig_rooms_load.py'
    spec = importlib.util.spec_from_file_location('rig_room_load_fixture', path)
    harness = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(harness)
    root = tmp_path / 'codex-rig-rooms-fixture'
    root.mkdir()
    (root / 'tests').symlink_to(ROOT / 'tests', target_is_directory=True)
    monkeypatch.setenv('TMPDIR', str(root / '.tmp'))

    # Capture fixture responses through the real handlers so the k6 replay
    # checks the shipped API contract.
    import asyncio
    async def api_fixture():
        from fastapi import FastAPI
        from fixtures.rig_quote_sample import seed, KEY as public_key, TENANT
        from rigbox.api import mount
        from rigbox.store import MemoryStore
        from rigbox.service import RecordingHandoff
        from rigbox.quotes.service import QuoteService
        from rigbox.quotes.store import MemoryQuotes
        store = MemoryStore()
        await seed(store, TENANT)
        app = FastAPI()
        app.state.rig = QuoteService(store, None, RecordingHandoff(), MemoryQuotes(store))
        mount(app)
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url='http://127.0.0.1:8001',
                headers={'X-Rig-Key': public_key, 'Origin': 'http://127.0.0.1:8001'}) as client:
            search = await client.get('/v1/rig/search?q=Core')
            quote = await client.post('/v1/rig/quote', json={'product_id': 'CORE-1', 'contact': {'name': 'Load fixture', 'email': 'load@example.test'}})
        assert search.status_code == quote.status_code == 200
        return {'search': search.json(), 'quote': quote.json()}
    fixture_file = root / 'api-fixture.json'
    fixture_file.write_text(json.dumps(asyncio.run(api_fixture())))
    calls, containers, stopped, networks = [], [], [], []

    def docker(args, *, input=None, check=True):
        calls.append(args)
        if args[:2] == ['git', '-C']:
            return 'fixture-commit'
        if args[1:3] == ['network', 'create']:
            networks.append(args[-1])
        elif args[1] == 'run':
            assert '--rm' in args and args[args.index('--label') + 1] == 'tervory.test=1'
            name = args[args.index('--name') + 1]
            assert name.startswith(root.name)
            containers.append(name)
            assert '--privileged' not in args and '/var/run/docker.sock' not in str(args)
        elif args[1] == 'exec':
            if 'pg_isready' in args:
                return 'database:5432 - accepting connections'
            assert args[-2:] == ['python', '-'] and 'await seed(' in input
        elif args[1] == 'port':
            return '127.0.0.1:32999'
        elif args[1] == 'stats':
            return '\n'.join(json.dumps({'Name': name, 'MemUsage': '20MiB / 256MiB' if name.endswith('-pg') else '40MiB / 384MiB'}) for name in args[5:])
        elif args[1] == 'stop':
            stopped.append(args[-1])
        elif args[1:3] == ['network', 'rm']:
            assert args[-1] in networks
        return ''

    def launch(args, **kwargs):
        docker(args)
        assert harness.K6_IMAGE in args and '@sha256:' in harness.K6_IMAGE
        assert 'K6_NO_USAGE_REPORT=true' in args and 'cloud' not in args
        volume = next(value for value in args if value.endswith(':/results'))
        output = Path(volume.removesuffix(':/results'))
        manifest = json.loads((output / 'rooms.json').read_text())
        assert len(manifest) == 2 and manifest[0]['tenant_id'] != manifest[1]['tenant_id']
        assert all(row['url'].startswith('http://' + root.name) for row in manifest)
        replay = subprocess.run(['node', str(ROOT / 'tests/load/rig_rooms_replay.cjs'), str(output / 'rooms.json'), str(fixture_file)], capture_output=True, text=True, timeout=30)
        assert replay.returncode == 0, replay.stdout + replay.stderr
        (output / 'raw-k6.json').write_text(replay.stdout)
        return SimpleNamespace(wait=lambda **kwargs: 0, poll=lambda: 0)

    output, result = harness.run(root, 2, '20s', 'fixture-room-image', docker=docker,
        ready=lambda name: name.startswith(root.name), launch=launch)
    assert result['rooms'] == 2 and len(result['per_room']) == 2
    assert result['search_p95_ms'] == 40 and result['quote_p95_ms'] == 80
    assert result['max_total_room_memory_bytes'] == 120 * 1024**2
    assert all(row['search_p95_ms'] == 38.5 and row['quote_p95_ms'] == 77 for row in result['per_room'])
    assert result['capacity_claim'] is None and result['shared_workers_included'] is False
    assert json.loads((output / 'measurement.json').read_text()) == result
    assert set(stopped) == {name for name in containers if not name.endswith('-k6')}
    assert len(networks) == 3
    assert not any(args[:3] == ['docker', 'volume', 'rm'] for args in calls)
    metrics = json.loads((output / 'raw-k6.json').read_text())['metrics']
    with pytest.raises(ValueError, match='every room'):
        harness.summarize({'metrics': metrics}, [{'containers': []}], 2)
    metrics['rig_search_ms']['values']['p(95)'] = float('nan')
    with pytest.raises(ValueError, match='percentiles'):
        harness.summarize({'metrics': metrics}, result['samples'], 2)
    metrics['rig_search_ms']['values']['p(95)'] = 40
    metrics['checks']['values']['fails'] = 1
    with pytest.raises(ValueError, match='failed checks'):
        harness.summarize({'metrics': metrics}, result['samples'], 2)

    unknown_root = tmp_path / 'codex-rig-rooms-unknown-start'
    unknown_root.mkdir()
    unknown_calls = []
    def unknown_start(args, *, input=None, check=True):
        unknown_calls.append(args)
        if args[1] == 'run':
            raise subprocess.TimeoutExpired(args, 0.1)
        return ''
    with pytest.raises(subprocess.TimeoutExpired):
        harness.run(unknown_root, 1, '5s', 'fixture-room-image', docker=unknown_start)
    attempted = next(args for args in unknown_calls if args[1] == 'run')
    reserved = attempted[attempted.index('--name') + 1]
    assert ['docker', 'stop', '-t', '3', reserved] in unknown_calls
    assert len([args for args in unknown_calls if args[1:3] == ['network', 'rm']]) == 2
    failure = next((unknown_root / '.tmp').glob('rig-room-load-*/failure.json'))
    assert json.loads(failure.read_text())['containers'] == [reserved]


@pytest.mark.asyncio
async def test_room_gateway_preserves_signed_callback_bytes_and_refuses_control_paths(monkeypatch):
    from fastapi import FastAPI
    from rigbox.rooms import RoomGateway, PREFIX
    from rigbox.commerce import signature
    import base64
    raw = b'{ "id": 7, "status": "completed" }\n'
    digest = base64.b64encode(hmac.new(b'fixture-webhook', raw, hashlib.sha256).digest()).decode()
    original = httpx.AsyncClient
    captured = []
    def callback(request):
        captured.append(request)
        assert request.url.host == 'rig-room-' + A and request.url.port == 8000
        assert request.url.path == '/v1/rig/commerce/webhooks/' + A
        assert request.content == raw
        assert request.headers['x-forwarded-for'] == '203.0.113.4'
        assert request.headers['origin'] == 'https://fixture.store'
        signature('woocommerce', raw, request.headers, 'fixture-webhook')
        return httpx.Response(200, json={'accepted': True})
    def client(*args, **kwargs):
        if kwargs.get('transport') is None:
            kwargs['transport'] = httpx.MockTransport(callback)
        return original(*args, **kwargs)
    monkeypatch.setattr(httpx, 'AsyncClient', client)
    monkeypatch.delenv('RIG_ROOM_TENANT', raising=False)
    shared = FastAPI()
    shared.add_middleware(RoomGateway)
    async with client(transport=httpx.ASGITransport(app=shared, client=('203.0.113.4', 12345)), base_url='https://rig.tervory.com') as http:
        result = await http.post(PREFIX + A + '/v1/rig/commerce/webhooks/' + A,
            content=raw, headers={'X-WC-Webhook-Signature': digest, 'Origin': 'https://fixture.store', 'X-Forwarded-For': '198.51.100.77'})
        assert result.status_code == 200 and result.json() == {'accepted': True}
        for tail in ['internal/retailer/settings', 'v1/rig/rooms/' + B + '/v1/rig/search']:
            assert (await http.post(PREFIX + A + '/' + tail, content=raw)).status_code == 404
    assert len(captured) == 1
