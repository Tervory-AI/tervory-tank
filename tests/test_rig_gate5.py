"""Launch journeys and adverse I/O through real routes, with offline boundaries."""
import asyncio
import subprocess
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import UUID

import httpx
import pytest
from fastapi import FastAPI

from chassis import tenant_db
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "agents/rig"))

from rigbox.api import mount
from rigbox.commerce import CommerceError, Platform
from rigbox.configuration import startup_missing
from rigbox.quotes.api import mount as quote_routes
from rigbox.quotes.service import QuoteService
from rigbox.quotes.senders import DeliveryError, RetailerHandoff
from rigbox.quotes.store import MemoryQuotes
from rigbox.retailer_api import router as retailer_routes
from rigbox.service import RecordingHandoff
from rigbox.store import MemoryStore
from rigbox.three_d.api import mount as three_routes
from test_rig_feeds_retailer import TENANT, OTHER, envelope

ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.asyncio
async def test_new_store_first_import_search_quote_receipt_failure_and_retry(monkeypatch):
    monkeypatch.setenv('RIG_RETAILER_KEY', 'placeholder-control')
    monkeypatch.setenv('RIG_QUOTE_FLOWS', '{}')
    store = MemoryStore()
    service = QuoteService(store, None, RetailerHandoff(None), MemoryQuotes(store))
    app = FastAPI(); app.state.rig = service
    mount(app); quote_routes(app); app.include_router(retailer_routes)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url='https://placeholder.example') as client:
        async def admin(op, data=None, tenant=TENANT):
            response = await client.post('/internal/retailer/' + op,
                headers={'x-rig-retailer-key': 'placeholder-control'},
                json={'tenant_id': tenant, 'data': data or {}})
            assert response.status_code == 200, response.text
            return response.json()
        panel = await admin('panel')
        assert panel['products'] == 0 and panel['receipts'] == []
        assert (await client.post('/internal/retailer/settings', json={'tenant_id': TENANT})).status_code == 401
        await admin('settings', {'name': 'Placeholder shop', 'email': 'placeholder@example.com'})
        await admin('price-rule', {'freight': '1', 'duty_percent': '10', 'margin_percent': '20'})
        # Reuse the existing fixed-rate fixture; no currency provider is contacted.
        from rigbox.retailer import Retailer
        await Retailer(service).set_rate(TENANT, {'currency': 'USD', 'rate': '18.50'}, founder=True)
        imported = await admin('import', envelope())
        assert imported['ok'] and imported['receipt']['added'] == 2
        panel = await admin('panel')
        assert panel['products'] == 2 and len(panel['receipts']) == 1
        assert (await admin('panel', tenant=OTHER))['receipts'] == []
        embed = await admin('embed-keys', {'origins': ['https://placeholder.example']})
        headers = {'X-Rig-Key': embed['publishable_key'], 'Origin': 'https://placeholder.example'}
        product = (await store.products(TENANT))[0]
        result = await client.get('/v1/rig/search', params={'q': product['name']}, headers=headers)
        assert result.status_code == 200 and result.json()['results']
        assert 'unit_cost' not in result.text and 'margin_percent' not in result.text
        quote = await client.post('/v1/rig/quote', headers=headers, json={'product_id': product['sku'],
            'contact': {'name': 'Placeholder buyer', 'email': 'placeholder@example.com'}})
        assert quote.status_code == 200, quote.text
        receipt = quote.json(); assert receipt['delivery'] == 'pending' and receipt['request_id']
        qid = receipt['request_id']
        assert await store.quote_for(OTHER, qid) is None
        service.handoff = RecordingHandoff()
        await service.quote_store.retry_now(TENANT, qid)
        await asyncio.gather(*(service.deliver(TENANT, qid) for _ in range(4)))
        assert len(service.handoff.sent) == 1
        assert (await service.quote_store.status(TENANT, qid))['status'] == 'sent'
        bad = envelope(); bad['contents'] = '{broken'
        failed = await admin('import', bad)
        assert not failed['ok']
        assert (await admin('panel'))['products'] == 2
        assert (await admin('import', envelope()))['ok']
        assert (await admin('panel'))['products'] == 2


@pytest.mark.asyncio
@pytest.mark.parametrize('operation', ['capabilities', 'dashboard', 'reset', 'entitlement'])
async def test_internal_3d_scope_is_bound_before_any_query(monkeypatch, operation):
    monkeypatch.setenv('TANK_KEY', 'placeholder-room')
    monkeypatch.setenv('RIG_ROOM_TENANT', TENANT)
    seen = []
    async def query(*args, **kwargs):
        seen.append(tenant_db._tenant.get())
        assert not tenant_db.administrative()
        return {'rig_3d': True} if operation == 'capabilities' else [] if operation == 'dashboard' else 1
    engine = SimpleNamespace(capabilities=query, require=AsyncMock(),
        store=SimpleNamespace(jobs=query, kiosk=query, set_entitlement=query))
    app = FastAPI(); mount(app); three_routes(app); app.state.rig_three_d = engine
    url = '/v1/rig/internal/3d/entitlement' if operation == 'entitlement' else '/v1/rig/internal/3d/workspace/' + operation
    def payload(tenant):
        return {'tenant_id': tenant, 'enabled': True} if operation == 'entitlement' else {
            'tenant_id': tenant, 'actor': 'placeholder-admin',
            'payload': {'id': TENANT} if operation == 'reset' else {}}
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url='https://placeholder.example') as client:
        for tenant, headers, expected in [(TENANT, {}, 401), (OTHER, {'X-Tank-Key': 'placeholder-room'}, 403)]:
            response = await client.post(url, json=payload(tenant), headers=headers)
            assert response.status_code == expected
        assert seen == []
        response = await client.post(url, json=payload(TENANT), headers={'X-Tank-Key': 'placeholder-room'})
        assert response.status_code == 200, response.text
        assert seen and set(seen) == {TENANT}


@pytest.mark.asyncio
@pytest.mark.parametrize('method', ['GET', 'POST', 'PUT', 'DELETE'])
async def test_commerce_stalled_io_has_total_deadline_and_no_automatic_retry(monkeypatch, method):
    import rigbox.deadline as deadline
    real_timeout = asyncio.timeout
    monkeypatch.setattr(deadline.asyncio, 'timeout', lambda seconds: real_timeout(.01))
    calls = []
    async def stalled(*args, **kwargs):
        calls.append((args, kwargs)); await asyncio.Future()
    platform = Platform(SimpleNamespace(request=stalled),
        {'platform': 'shopify', 'site': 'https://placeholder.myshopify.com'}, {'access_token': 'placeholder-private'})
    with pytest.raises(CommerceError, match='^platform_request$'):
        await platform.request(method, '/orders')
    assert len(calls) == 1 and calls[0][1]['timeout'] == 25
    assert calls[0][1]['follow_redirects'] is False


@pytest.mark.asyncio
@pytest.mark.parametrize('failure', ['timeout', 'redirect', 'server', 'invalid_json'])
async def test_commerce_failure_contains_no_upstream_credentials_and_does_not_retry(failure, caplog):
    calls = []
    def handler(request):
        calls.append(request)
        if failure == 'timeout': raise httpx.ReadTimeout('placeholder-private')
        return httpx.Response({'redirect': 302, 'server': 500, 'invalid_json': 200}[failure],
            content=b'placeholder-private', headers={'Location': 'https://other.example'})
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        platform = Platform(client, {'platform': 'shopify', 'site': 'https://placeholder.myshopify.com'}, {'access_token': 'placeholder-private'})
        with pytest.raises(CommerceError) as error: await platform.request('POST', '/orders')
    assert str(error.value) == 'platform_request'
    assert len(calls) == 1 and 'placeholder-private' not in caplog.text


@pytest.mark.asyncio
async def test_webhook_stall_has_stable_delivery_id_and_bounded_attempt(monkeypatch):
    import rigbox.quotes.senders as senders
    real_timeout = asyncio.timeout
    monkeypatch.setattr(senders.asyncio, 'timeout', lambda seconds: real_timeout(.01))
    monkeypatch.setenv('RIG_QUOTE_FLOWS', '{}')
    calls = []
    async def stalled(*args, **kwargs): calls.append(kwargs); await asyncio.Future()
    handoff = RetailerHandoff(SimpleNamespace(post=stalled))
    for _ in range(2):
        with pytest.raises(DeliveryError, match='^retailer_unavailable$'):
            await handoff.send(tenant_id=TENANT, email=None, webhook='https://placeholder.example/handoff', quote={'id': 'placeholder'})
    assert len(calls) == 2
    assert calls[0]['headers'] == calls[1]['headers'] == {'Idempotency-Key': f'rig:{TENANT}:placeholder'}


@pytest.mark.asyncio
async def test_database_connect_timeout_degrades_without_leaking_dsn(monkeypatch):
    import asyncpg
    connect = AsyncMock(side_effect=TimeoutError('placeholder-private'))
    monkeypatch.setattr(asyncpg, 'connect', connect)
    assert await startup_missing('rig', {'DATABASE_URL': 'placeholder-private'}) == ['DATABASE_URL']
    assert connect.call_args.kwargs == {'timeout': 10, 'command_timeout': 10}


def test_launch_browser_journeys_accessibility_and_slow_phone():
    result = subprocess.run(['node', 'tests/rig_gate5_browser.mjs'], cwd=ROOT,
                            capture_output=True, text=True, timeout=110)
    assert result.returncode == 0, result.stdout + result.stderr


@pytest.mark.asyncio
@pytest.mark.parametrize('address', ['127.0.0.1', '169.254.169.254', '10.0.0.1', '::1', '::ffff:127.0.0.1'])
async def test_commerce_dns_rebinding_never_sends_credentials(monkeypatch, address):
    from rigbox.cart_runtime import PublicCommerceHTTP
    http = SimpleNamespace(request=AsyncMock())
    monkeypatch.setattr(asyncio.get_running_loop(), 'getaddrinfo', AsyncMock(return_value=[(0,0,0,'',(address,443))]))
    with pytest.raises(CommerceError):
        await PublicCommerceHTTP(http).request('POST', 'https://placeholder.example/orders',
            headers={'Authorization': 'placeholder-private'}, timeout=25)
    http.request.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize('domain', ['placeholder.example', 'bücher.example'])
async def test_commerce_public_dns_address_is_pinned_and_tls_hostname_preserved(monkeypatch, domain):
    from rigbox.cart_runtime import PublicCommerceHTTP
    monkeypatch.setattr(asyncio.get_running_loop(), 'getaddrinfo', AsyncMock(return_value=[(0,0,0,'',('93.184.216.34',443))]))
    http = SimpleNamespace(request=AsyncMock(return_value='placeholder-result'))
    assert await PublicCommerceHTTP(http).request('POST', f'https://{domain}/orders',
        headers={'Authorization': 'placeholder-private'}, timeout=25, follow_redirects=False) == 'placeholder-result'
    args, kwargs = http.request.call_args
    assert str(args[1]) == 'https://93.184.216.34/orders'
    assert kwargs['headers']['Host'] == kwargs['extensions']['sni_hostname'] == domain.encode('idna').decode('ascii')
    assert kwargs['headers']['Connection'] == 'close'
    assert kwargs['follow_redirects'] is False


@pytest.mark.asyncio
@pytest.mark.parametrize('kind', ['source', 'tiger'])
async def test_live_stock_checker_stall_is_unknown_and_never_an_order(monkeypatch, kind):
    from rigbox import locate_live
    async def stalled(*args, **kwargs): await asyncio.Future()
    wait_for = asyncio.wait_for
    monkeypatch.setattr(locate_live, 'asyncio', SimpleNamespace(wait_for=lambda awaitable, timeout: wait_for(awaitable, .01)))
    http = SimpleNamespace(get=AsyncMock(side_effect=stalled), post=AsyncMock(side_effect=stalled))
    source = {'id': 'placeholder'}
    checker = locate_live.SourceApiChecker(http, {'RIG_SUPPLY_API_URL_PLACEHOLDER': 'https://placeholder.example',
        'RIG_SUPPLY_API_KEY_PLACEHOLDER': 'placeholder-private'}) if kind == 'source' else locate_live.TigerChecker(http,
        {'RIG_TIGER_URL': 'https://placeholder.example', 'RIG_TIGER_CHECK_KEY': 'placeholder-private'})
    result = await checker.check(TENANT, source, {'sku': 'placeholder', 'url': 'https://placeholder.example/product'})
    assert result.status == 'unknown' and result.evidence == {'reason': 'unavailable'}
    assert http.get.await_count + http.post.await_count == 1


@pytest.mark.asyncio
@pytest.mark.parametrize('kind', ['forge', 'storage', 'photo'])
async def test_stalled_model_and_storage_calls_are_bounded_and_safe(monkeypatch, kind):
    from rigbox import deadline
    from rigbox.service import RigError
    from rigbox.three_d.forge import BrainForge
    from rigbox.rooms import RoomStorage
    from rigbox.three_d.assets import ForgeFiles
    from chassis.storage import Storage, StorageError
    real_timeout = asyncio.timeout
    monkeypatch.setattr(deadline.asyncio, 'timeout', lambda seconds: real_timeout(.01))
    async def stalled(*args, **kwargs): await asyncio.Future()
    if kind == 'forge':
        forge = BrainForge(SimpleNamespace(request=AsyncMock(side_effect=stalled)), 'placeholder')
        with pytest.raises(RigError, match='product service is not connected'):
            await forge._call('GET', SimpleNamespace(id=UUID(TENANT), tenant_id=UUID(TENANT)))
        assert forge.client.request.await_count == 1
    elif kind == 'storage':
        monkeypatch.setattr(Storage, '_request', stalled)
        with pytest.raises(StorageError): await RoomStorage.__new__(RoomStorage)._request('GET', 'placeholder')
    else:
        from contextlib import asynccontextmanager
        @asynccontextmanager
        async def stream(*args, **kwargs):
            await stalled(); yield
        files = SimpleNamespace(bucket='placeholder', host='placeholder.example', _sign=lambda *args: {},
            _http=SimpleNamespace(stream=stream))
        with pytest.raises(StorageError, match='Input storage is unavailable'):
            await ForgeFiles._read_photo(files, 'placeholder', 'png', 20)


def test_signup_day_zero_server_identity_invalid_input_and_private_plugin_errors():
    script = r'''
const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path');
const wr=require('node:module').createRequire(process.cwd()+'/workspace/package.json'),ts=wr('typescript');
let identity=null,calls=[],mode='ok';
const bindings={
 '@/lib/tenant':{activeTenant:async()=>identity},
 '@/lib/tank':{rigCatalogueCounts:async tenant=>{calls.push(tenant);return {products:0,fits:0};}},
 './lab':{Lab:()=>null},'./vault-server':{loadRigPlugins:async()=>({enabled:false})},
 '../../rig-server':{rigCall:async(tenant,op,body)=>{calls.push({tenant,op,body});return {results:[]};}},
 '@/lib/trigger-signin-fetch':{signinFetch:async(url,init)=>{
   calls.push({url,init});assert(init.signal);assert.equal(init.redirect,'error');
   return new Response(mode==='fail'?'placeholder-private':JSON.stringify({enabled:false}),{status:mode==='fail'?500:200});
 }}
};
function load(filename){
 const file=path.resolve(filename),code=ts.transpileModule(fs.readFileSync(file,'utf8'),{compilerOptions:{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2022,jsx:ts.JsxEmit.ReactJSX}}).outputText;
 const mod={exports:{}};
 const local=name=>{if(name in bindings)return bindings[name];if(name.startsWith('.'))return load(path.resolve(path.dirname(file),name+'.ts'));return wr(name);};
 new Function('require','module','exports',code)(local,mod,mod.exports);return mod.exports;
}
(async()=>{
 const dir='workspace/app/rig/',page=load(dir+'page.tsx').default,route=load(dir+'api/rig/route.ts');
 let view=await page();assert.equal(view.props.products,null);assert.equal(calls.length,0);
 const request=body=>new Request('https://placeholder.example/rig/api/rig',{method:'POST',headers:{origin:'https://placeholder.example',host:'placeholder.example','content-type':'application/json'},body:JSON.stringify(body)});
 assert.equal((await route.POST(request({op:'search',q:'placeholder'}))).status,401);
 assert.equal(calls.length,0);
 // Trigger sign-in owns sign-up. Its first verified account must render zero data.
 identity={tenantId:'placeholder-new-account',userId:'placeholder-member',orgName:'Placeholder shop'};
 view=await page();assert.equal(view.props.products,0);assert.equal(view.props.fits,0);assert.equal(view.props.accountName,'Placeholder shop');
 calls=[];
 for(const invalid of [null,[],true,4,'search',{op:'entitlement'}])assert.equal((await route.POST(request(invalid))).status,400);
 assert.equal(calls.length,0);
 let response=await route.POST(request({op:'search',q:'placeholder',tenant_id:'forged'}));assert.equal(response.status,200);
 assert.equal(calls[0].tenant,identity.tenantId);
 const vault=load(dir+'vault-server.ts');mode='fail';
 await assert.rejects(vault.saveRigSecret('placeholder','placeholder','placeholder-value'),e=>e.message==='The retailer request was not confirmed.');
 await assert.rejects(vault.uploadRigFiles(new FormData()),e=>e.message==='The file was not saved.');
 identity=null;const before=calls.length;await assert.rejects(vault.saveRigSecret('placeholder','placeholder','placeholder-value'),/Sign in/);assert.equal(calls.length,before);
 console.log('PASS: sign-up boundary, empty account, server-owned identity, invalid JSON shapes, private plugin errors.');
})().catch(e=>{console.error(e);process.exitCode=1;});
'''
    result = subprocess.run(['node', '-e', script], cwd=ROOT, capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, result.stdout + result.stderr


@pytest.mark.asyncio
@pytest.mark.parametrize('lost', [False, True])
async def test_cart_http_journey_never_repeats_an_uncertain_checkout(monkeypatch, lost):
    from test_rig_cart import setup, TENANT as tenant
    from rigbox.cart_api import mount as cart_routes
    from rigbox.service import Service, hash_key
    cart, platform, _, _, _, remote = await setup(monkeypatch)
    service = Service(cart.store); service.cart = cart
    await cart.store.put_key(tenant, hash_key('rk_pub_placeholder'), 'publishable', ['https://store.example'])
    app = FastAPI(); app.state.rig = service; mount(app); cart_routes(app)
    try:
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url='https://store.example') as client:
            headers={'X-Rig-Key':'rk_pub_placeholder','Origin':'https://store.example'}
            async def call(op, data):
                return await client.post('/v1/rig/cart/'+op,headers=headers,json=data)
            assert (await client.post('/v1/rig/cart/session',json={})).status_code == 401
            session=(await call('session',{})).json()['session']
            assert (await call('add',{'session':session,'product_id':'stock','quantity':1})).status_code == 200
            platform.lose_create=lost
            first=await call('checkout',{'session':session})
            assert first.status_code == 200
            again=await asyncio.gather(*(call('checkout',{'session':session}) for _ in range(3)))
            assert all(r.status_code == 200 and r.json()['id']==first.json()['id'] for r in again)
            assert len(platform.orders)==1
            assert first.json()['state'] == ('create_unknown' if lost else 'pending')
            invalid=await call('add',{'session':session,'product_id':'stock','quantity':True})
            assert invalid.status_code == 409
    finally:
        await remote.aclose()


@pytest.mark.asyncio
async def test_photo_upload_stall_cleans_scratch_and_never_retries(monkeypatch):
    from rigbox.three_d import assets
    from test_rig_3d_uploads import StorageTransport, files, job, TENANT as tenant
    real_timeout = asyncio.timeout
    monkeypatch.setattr(assets.asyncio, 'timeout', lambda seconds: real_timeout(.02))
    class StalledUpload(StorageTransport):
        writes = 0
        async def handle_async_request(self, request):
            if request.method == 'PUT':
                self.writes += 1
                await asyncio.Future()
            return await super().handle_async_request(request)
    scratch = []
    temporary_directory = assets.TemporaryDirectory
    def tracked_directory(*args, **kwargs):
        directory = temporary_directory(*args, **kwargs); scratch.append(Path(directory.name)); return directory
    monkeypatch.setattr(assets, 'TemporaryDirectory', tracked_directory)
    transport = StalledUpload()
    storage = files(transport)
    try:
        with pytest.raises(assets.StorageError, match='Input storage is unavailable'):
            await storage.stage(job(source='ai', inputs=[f'{tenant}/uploads/placeholder.jpg']))
        assert transport.writes == 1
        assert scratch and all(not path.exists() for path in scratch)
    finally:
        await storage.close()


@pytest.mark.asyncio
@pytest.mark.parametrize('kind', ['memory', 'receipt', 'relay'])
async def test_brain_io_stalls_without_replaying_mutations(monkeypatch, tmp_path, kind):
    shared = ROOT / 'agents/_brain'
    packages = tmp_path / 'packages'; packages.mkdir()
    (packages / 'brain').symlink_to(shared, target_is_directory=True)
    monkeypatch.syspath_prepend(str(packages))
    from rig_brain import service as brain
    from agents.rig.forge import service as forge
    async def stalled(*args, **kwargs): await asyncio.Future()
    client = SimpleNamespace(post=AsyncMock(side_effect=stalled))
    wait_for = asyncio.wait_for
    module = forge if kind == 'relay' else brain
    monkeypatch.setattr(module, 'asyncio', SimpleNamespace(wait_for=lambda awaitable, timeout: wait_for(awaitable, .01)))
    if kind == 'relay':
        from contextlib import asynccontextmanager
        @asynccontextmanager
        async def connection(*args, **kwargs): yield client
        monkeypatch.setattr(forge.httpx, 'AsyncClient', connection)
        operation = forge.relay('steps', {})
    elif kind == 'memory':
        operation = brain.memory(client, '/memories', {})
    else:
        operation = brain.step(client, SimpleNamespace(tenant_id=TENANT, task_id=TENANT, home_region='us-east'), 'recall', 'done')
    with pytest.raises(TimeoutError): await operation
    assert client.post.await_count == 1


@pytest.mark.asyncio
@pytest.mark.parametrize('operation', ['get', 'put'])
async def test_storage_failure_is_a_plain_client_error(monkeypatch, operation):
    from rigbox.three_d.asgi import LazyR2
    from rigbox.service import RigError
    from chassis.storage import StorageError
    io = AsyncMock(side_effect=StorageError('placeholder-private'))
    storage = LazyR2(); storage.instance = SimpleNamespace(**{operation: io})
    with pytest.raises(RigError) as error:
        await getattr(storage, operation)(TENANT, TENANT)
    assert error.value.status == 503
    assert 'placeholder-private' not in error.value.message
    io.assert_awaited_once()


@pytest.mark.asyncio
async def test_store_room_timeout_reaches_the_client_without_a_second_request(monkeypatch):
    from contextlib import asynccontextmanager
    from rigbox import rooms
    monkeypatch.delenv('RIG_ROOM_TENANT', raising=False)
    requests = []
    @asynccontextmanager
    async def stream(*args, **kwargs):
        requests.append((args, kwargs)); await asyncio.Future(); yield
    @asynccontextmanager
    async def connection(*args, **kwargs): yield SimpleNamespace(stream=stream)
    app = rooms.RoomGateway(FastAPI())
    client = httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url='https://placeholder.example')
    real_timeout = asyncio.timeout
    monkeypatch.setattr(rooms.asyncio, 'timeout', lambda seconds: real_timeout(.01))
    monkeypatch.setattr(rooms.httpx, 'AsyncClient', connection)
    async with client:
        response = await client.get(f'/v1/rig/rooms/{TENANT}/v1/rig/search')
    assert response.status_code == 503
    assert response.json()['error']['message'] == 'This store room is unavailable.'
    assert len(requests) == 1
