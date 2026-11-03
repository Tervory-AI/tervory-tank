"""Tiger catalogue matching: synthetic identifiers and offline pages only."""
import sys
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import UUID

import pytest

import trigger_routes

TENANT = UUID('11111111-1111-4111-8111-111111111111')


@pytest.mark.asyncio
async def test_code_receipt_default_still_records_trigger(monkeypatch):
    pool = SimpleNamespace(fetchval=AsyncMock(return_value=TENANT))
    monkeypatch.setitem(sys.modules, 'main', SimpleNamespace(pool=lambda: pool, box_region=lambda: 'us-east'))
    assert await trigger_routes.code_receipt(TENANT, 'trigger.check') == TENANT
    sql, *args = pool.fetchval.call_args.args
    assert "VALUES($1,$2,$5,$3,3,'code',0,0,0,$4)" in sql
    assert args == [TENANT, 'us-east', 'trigger.check', None, 'trigger']


@pytest.mark.asyncio
async def test_code_receipt_records_tiger_without_interpolating_agent(monkeypatch):
    pool = SimpleNamespace(fetchval=AsyncMock(return_value=TENANT))
    monkeypatch.setitem(sys.modules, 'main', SimpleNamespace(pool=lambda: pool, box_region=lambda: 'us-east'))
    await trigger_routes.code_receipt(TENANT, 'tiger.match', agent='tiger')
    sql, *args = pool.fetchval.call_args.args
    assert 'tiger' not in sql
    assert args == [TENANT, 'us-east', 'tiger.match', None, 'tiger']

import asyncio
import importlib.util
import json
import socket
from pathlib import Path
from uuid import uuid4

import asyncpg
import httpx
import pytest_asyncio
from fastapi import FastAPI, HTTPException

import access
import command
from trigger_commands import CONFIRMED

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'agents/tiger'))
from rig_watch import CatalogueDiscovery, DiscoveryGate, DiscoveryStopped
from watch import ensure_tables
from chassis.db import ensure_schema

OTHER = UUID('22222222-2222-4222-8222-222222222222')
SITE = 'https://competitor.example'
PAGE = SITE + '/products/item'
GTIN = '4006381333931'
OWN = {'sku': 'own', 'gtin': GTIN, 'brand': 'Offline brand', 'mpn': 'ABC-1', 'price': '15.00', 'currency': 'USD'}

@pytest.fixture(autouse=True)
def offline_dns(monkeypatch):
    original = socket.getaddrinfo
    def resolve(host, *args, **kwargs):
        if host in {'localhost','127.0.0.1','::1'}:
            return original(host, *args, **kwargs)
        return [(2,1,6,'',('8.8.8.8',443))]
    monkeypatch.setattr(socket,'getaddrinfo',resolve)



def markup(**changes):
    node = {'@type': 'Product', 'name': 'Unrelated title', 'sku': 'not-the-store-sku',
            'url': PAGE, 'gtin13': GTIN, 'brand': {'@type': 'Brand', 'name': 'Offline brand'}, 'mpn': 'ABC-1',
            'offers': {'@type': 'Offer', 'price': '12.00', 'priceCurrency': 'USD', 'availability': 'https://schema.org/InStock'}}
    node.update(changes)
    return '<script type="application/ld+json">' + json.dumps(node) + '</script>'


@pytest.mark.parametrize('value,expected', [(GTIN, '04006381333931'), ('0' + GTIN, '04006381333931'),
    ('4006-3813 33931', '04006381333931'), ('96385074', '00000096385074'), ('4006381333932', None), (4006381333931, None), ('abc', None), ('00000000000000', None), ('0000-0000', None)])
def test_gtin_normalization_validates_check_digit(value, expected):
    assert access.tiger_gtin(value) == expected


@pytest.mark.parametrize('html,expected', [(markup(), ('gtin','confirmed')),
    (markup(gtin13='5012345678900'), None), (markup(gtin13='4006381333932'), None),
    (markup(gtin13=None, brand=None, mpn=None, name='own'), None),
    (markup(gtin13=None), ('brand_mpn','suggested')),
    (markup(gtin13=None, brand='Other brand'), None)])
def test_identifier_rule_never_matches_title_or_competitor_sku(html, expected):
    facts = access.tiger_product_evidence(html, PAGE)
    assert len(facts) == 1
    assert access.tiger_identity_match(OWN, facts[0]) == expected
    assert facts[0]['readings'][0]['price'] == '12.00'


def test_microdata_identifiers_and_nested_brand_use_existing_price_reader():
    html = f'''<div itemscope itemtype="https://schema.org/Product">
    <meta itemprop="gtin14" content="0{GTIN}"><meta itemprop="mpn" content="ABC-1">
    <div itemprop="brand" itemscope itemtype="https://schema.org/Brand"><b itemprop="name">Offline brand</b></div>
    <b itemprop="name">Different title</b><div itemprop="offers" itemscope itemtype="https://schema.org/Offer">
    <meta itemprop="price" content="12.00"><meta itemprop="priceCurrency" content="USD"></div></div>'''
    facts = access.tiger_product_evidence(html, PAGE)
    assert facts[0]['brand'] == 'Offline brand' and facts[0]['mpn'] == 'ABC-1'
    assert access.tiger_identity_match(OWN, facts[0]) == ('gtin','confirmed')


@pytest.fixture(scope='module')
def postgres(tmp_path_factory):
    import pgserver
    return pgserver.get_server(tmp_path_factory.mktemp('tiger-t1-postgres'))


@pytest_asyncio.fixture
async def database(postgres):
    from urllib.parse import urlsplit, urlunsplit
    admin = await asyncpg.connect(postgres.get_uri())
    name = 'tiger_t1_' + uuid4().hex
    await admin.execute('CREATE DATABASE ' + name)
    parsed = urlsplit(postgres.get_uri())
    pool = await asyncpg.create_pool(urlunsplit(parsed._replace(path='/' + name)), min_size=1, max_size=5)
    try:
        async with pool.acquire() as conn:
            await conn.execute((ROOT / 'tank/schema.sql').read_text())
            await ensure_schema(conn, 'tiger')
            await ensure_tables(conn, 'agent_tiger')
        yield pool
    finally:
        await pool.close()
        await admin.execute('DROP DATABASE ' + name)
        await admin.close()


@pytest_asyncio.fixture
async def corridor(database, monkeypatch):
    spec = importlib.util.spec_from_file_location('tiger_t1_agent', ROOT / 'agents/tiger/app.py')
    agent = importlib.util.module_from_spec(spec)
    monkeypatch.setitem(sys.modules, spec.name, agent)
    spec.loader.exec_module(agent)
    agent.app.state.pool = database
    # Test DNS never queries the outside network.
    monkeypatch.setattr(socket, 'getaddrinfo', lambda *args, **kwargs: [(2,1,6,'',('8.8.8.8',443))])
    monkeypatch.setenv('TERVORY_ADMIN_USER_IDS', '')
    for tenant in (TENANT, OTHER):
        await database.execute("INSERT INTO tank.tenant_squad(tenant_id,agent,enabled_by) VALUES($1,'tiger','offline')", tenant)
        await database.execute("INSERT INTO tank.vault_items(tenant_id,vault,kind,name,metadata) VALUES($1,'tiger.vault','links','source',$2::jsonb)", tenant, json.dumps({'url': SITE}))
    actor = SimpleNamespace(current=command.Actor(TENANT, 'offline-user', False, frozenset({'tiger'})))
    app = FastAPI()
    app.include_router(access.router)
    app.dependency_overrides[access.identity] = lambda: actor.current
    async def catalogue(tenant):
        return [{**OWN, 'price': '99.00' if str(tenant) == str(OTHER) else '15.00'}]
    async def tiger_call(method, path, params, content):
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=agent.app), base_url='http://tiger') as client:
            return await client.request(method, path, params=params, content=content, headers={'content-type':'application/json'})
    monkeypatch.setitem(sys.modules, 'main', SimpleNamespace(pool=lambda: database, box_region=lambda: 'us-east', _tiger_call=tiger_call))
    monkeypatch.setattr(access, 'tiger_catalogue', catalogue)
    monkeypatch.setattr(access, 'require_tiger', lambda request: None)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url='http://tank') as client:
        agent.app.state.http = client
        yield SimpleNamespace(pool=database, client=client, agent=agent, actor=actor)


async def publish(system, html, tenant=TENANT, human=False):
    response = await system.client.post('/v1/access/rig/tiger/match-page', json={
        'tenant_id': str(tenant), 'site': SITE, 'url': PAGE, 'html': html, 'human_check': human})
    assert response.status_code == 200, response.text
    return response.json()


async def decision(system, match_id, decision='confirm', tenant=TENANT):
    system.actor.current = command.Actor(tenant, 'offline-user', False, frozenset({'tiger'}))
    args = {'match_id': match_id}
    token = CONFIRMED.set((tenant, 'offline-user', uuid4(), 'tiger.match.' + decision, args))
    try:
        return await system.client.post('/v1/access/tiger/match/' + decision, json=args)
    finally:
        CONFIRMED.reset(token)


@pytest.mark.asyncio
@pytest.mark.parametrize('html', [markup(gtin13='5012345678900'), markup(gtin13=None, brand=None, mpn=None, name='own')])
async def test_mismatch_and_title_only_never_write_links_or_watches(corridor, html):
    assert (await publish(corridor, html))['matches'] == []
    assert await corridor.pool.fetchval('SELECT count(*) FROM tank.access_feed_links') == 0
    assert await corridor.pool.fetchval('SELECT count(*) FROM agent_tiger.watchlist') == 0


@pytest.mark.asyncio
async def test_exact_gtin_links_with_evidence_and_all_handmade_watch_defaults(corridor):
    result = await publish(corridor, markup())
    match = result['matches'][0]
    assert match['state'] == 'confirmed' and match['method'] == 'gtin'
    assert match['seen_on'] == PAGE and match['identifiers']['seen']['gtins'] == [GTIN]
    assert await corridor.pool.fetchval('SELECT sku FROM tank.access_feed_links WHERE tenant_id=$1 AND url=$2', TENANT, PAGE) == 'own'
    row = await corridor.pool.fetchrow('SELECT * FROM agent_tiger.watchlist WHERE tenant_id=$1', TENANT)
    assert row['every'] == '6h'
    assert all(row[k] for k in ('enabled','alert_price','alert_stock','alert_new_product','alert_below_cost','alert_market_gap'))
    await publish(corridor, markup())
    assert await corridor.pool.fetchval('SELECT count(*) FROM agent_tiger.watchlist') == 1


@pytest.mark.asyncio
async def test_brand_mpn_requires_a_bound_confirm_card_and_is_tenant_scoped(corridor):
    result = await publish(corridor, markup(gtin13=None))
    match = result['matches'][0]
    assert match['state'] == 'suggested'
    assert await corridor.pool.fetchval('SELECT count(*) FROM tank.access_feed_links') == 0
    assert await corridor.pool.fetchval('SELECT count(*) FROM agent_tiger.watchlist') == 0
    refused = await corridor.client.post('/v1/access/tiger/match/confirm', json={'match_id':match['id']})
    assert refused.status_code == 409
    foreign = await decision(corridor, match['id'], tenant=OTHER)
    assert foreign.status_code == 404
    confirmed = await decision(corridor, match['id'])
    assert confirmed.status_code == 200, confirmed.text
    assert confirmed.json()['match']['state'] == 'confirmed'
    assert await corridor.pool.fetchval('SELECT count(*) FROM tank.access_feed_links WHERE tenant_id=$1', OTHER) == 0
    ledger = await corridor.pool.fetchrow('SELECT agent,cost_usd FROM tank.ledger WHERE id=$1', UUID(confirmed.json()['ledger_id']))
    assert ledger['agent'] == 'tiger' and ledger['cost_usd'] == 0


@pytest.mark.asyncio
async def test_rejected_suggestion_stays_rejected_on_discovery(corridor):
    match = (await publish(corridor, markup(gtin13=None)))['matches'][0]
    rejected = await decision(corridor, match['id'], 'reject')
    assert rejected.status_code == 200 and rejected.json()['match']['state'] == 'rejected'
    assert (await publish(corridor, markup()))['matches'][0]['state'] == 'rejected'
    assert await corridor.pool.fetchval('SELECT count(*) FROM tank.access_feed_links') == 0


@pytest.mark.asyncio
async def test_position_figures_use_latest_tenant_reading_and_zero_receipt(corridor):
    await publish(corridor, markup())
    for tenant,price in [(TENANT,12),(OTHER,1)]:
        await corridor.pool.execute("INSERT INTO agent_tiger.observations(tenant_id,url,price,currency,availability,method) VALUES($1,$2,$3,'USD','InStock','jsonld')", tenant, PAGE, price)
    response = await corridor.client.get('/v1/access/tiger/position')
    assert response.status_code == 200, response.text
    row = response.json()['products'][0]
    assert row['own_price'] == '15.00' and row['rank'] == 2 and row['difference'] == '3.00'
    assert row['cheapest'] == {'price':'12', 'url':PAGE}
    assert row['competitors'][0]['price'] == '12' and row['competitors'][0]['checked_at']
    assert row['competitors'][0]['url'] == PAGE
    corridor.actor.current = command.Actor(OTHER, 'offline-user', False, frozenset({'tiger'}))
    result = (await corridor.client.get('/v1/access/tiger/position')).json()
    assert result['products'] == [] and result['total'] == 0


def test_position_ties_missing_and_cross_currency_are_not_guessed():
    matches = [{'sku':'own','url':PAGE,'state':'confirmed'}, {'sku':'own','url':SITE+'/other','state':'confirmed'}]
    readings = {PAGE:{'price':'15','currency':'USD'}, SITE+'/other':{'price':'1','currency':'EUR'}}
    row = access.tiger_positions([OWN], matches, readings)[0]
    assert row['rank'] == 1 and row['difference'] == '0.00'
    assert len(row['competitors']) == 2


class OfflineGate:
    def __init__(self):
        self.calls, self.blocked = [], set()
    async def call(self, url, operation):
        if SITE in self.blocked:
            raise DiscoveryStopped('human_check')
        if len(self.calls) >= 500:
            raise DiscoveryStopped('page_limit')
        self.calls.append(url)
        return await operation()
    async def block(self, site):
        self.blocked.add(site)


@pytest.mark.asyncio
async def test_discovery_obeys_robots_sitemap_and_human_check_without_other_pages():
    gate = OfflineGate()
    seen = []
    async def fetch(url):
        if url.endswith('robots.txt'):
            return {'status':200, 'text': 'User-agent: *\nDisallow: /blocked\nSitemap: '+SITE+'/map.xml'}
        if url.endswith('map.xml'):
            return {'status':200,'text':'<urlset><url><loc>'+SITE+'/blocked</loc></url><url><loc>'+PAGE+'</loc></url><url><loc>'+SITE+'/later</loc></url></urlset>'}
        return {'status':404, 'text':''}
    async def render(url):
        seen.append(url)
        return {'ok':False,'challenge':True}
    recorded = []
    async def publish(site,url,html,human):
        recorded.append((site,url,human))
        return {'matches':[]}
    result = await CatalogueDiscovery(fetch,render,gate,publish).run([SITE],[OWN])
    assert result['sites'][0]['status'] == 'human_check'
    assert seen == [PAGE] and recorded == [(SITE,PAGE,True)]
    assert not any('/blocked' in url or '/later' in url for url in gate.calls)


@pytest.mark.asyncio
async def test_discovery_search_uses_gtin_and_existing_get_form():
    gate, visited = OfflineGate(), []
    async def fetch(url): return {'status':404,'text':''}
    async def render(url):
        visited.append(url)
        html = '<form action="/find"><input type="search" name="query"></form>' if url == SITE+'/' else ''
        if '/find?' in url:
            html = '<a href="/products/item">product</a>'
        return {'ok':True,'url':url,'html':html}
    async def publish(site,url,html,human):
        return {'matches':[{'sku':'own','state':'confirmed'}]} if url == PAGE else {'matches':[]}
    result = await CatalogueDiscovery(fetch,render,gate,publish).run([SITE],[OWN])
    assert result['sites'][0]['status'] == 'completed'
    assert SITE+'/search?q='+GTIN in visited
    assert SITE+'/?s='+GTIN+'&post_type=product' in visited
    assert SITE+'/find?query='+GTIN in visited and PAGE in visited


@pytest.mark.asyncio
async def test_real_gate_enforces_rate_page_cap_failure_accounting_and_reset(database, monkeypatch):
    monkeypatch.setattr(socket, 'getaddrinfo', lambda *args, **kwargs: [(2,1,6,'',('8.8.8.8',443))])
    from chassis.tenant_db import TenantPool
    gate = DiscoveryGate(TenantPool(database))
    times = []
    async def read():
        times.append(asyncio.get_running_loop().time())
        return {'ok':True}
    await asyncio.gather(gate.call(PAGE,read),DiscoveryGate(database).call(PAGE,read))
    assert times[1] - times[0] >= 2.95
    await database.execute("UPDATE agent_tiger.discovery_limits SET requests=499,last_at=clock_timestamp()-interval '3 seconds' WHERE site=$1", SITE)
    await gate.call(PAGE,read)
    with pytest.raises(DiscoveryStopped, match='page_limit'):
        await gate.call(PAGE,read)
    assert len(times) == 3
    await database.execute("UPDATE agent_tiger.discovery_limits SET day=current_date-1, human_check=true WHERE site=$1", SITE)
    async def fail(): raise OSError('offline failure')
    with pytest.raises(OSError):
        await gate.call(PAGE,fail)
    assert await database.fetchval('SELECT requests FROM agent_tiger.discovery_limits WHERE site=$1', SITE) == 1
    await gate.block(SITE)
    with pytest.raises(DiscoveryStopped, match='human_check'):
        await gate.call(PAGE,read)


@pytest.mark.asyncio
async def test_schema_rollout_is_idempotent_legacy_safe_and_enforces_tenant_rls(database):
    ddl = (ROOT / 'tank/schema.sql').read_text()
    assert not await database.fetchval("SELECT relrowsecurity FROM pg_class WHERE oid='agent_tiger.matches'::regclass")
    await database.execute('ALTER TABLE tank.command_threads ENABLE ROW LEVEL SECURITY')
    await database.execute(ddl)
    await database.execute(ddl)
    for table in ('matches','match_runs'):
        assert await database.fetchval('SELECT relrowsecurity AND relforcerowsecurity FROM pg_class WHERE oid=$1::regclass', 'agent_tiger.'+table)
        assert await database.fetchval("SELECT count(*) FROM pg_policy WHERE polrelid=$1::regclass AND polname IN ('tenant_access','tenant_boundary')", 'agent_tiger.'+table) == 2
    await database.execute("INSERT INTO agent_tiger.matches(tenant_id,sku,url,method,identifiers,seen_on,state) VALUES($1,'own',$2,'gtin','{}',$2,'confirmed')", TENANT,PAGE)
    async with database.acquire() as conn:
        await conn.execute('CREATE ROLE tiger_t1_reader NOLOGIN NOSUPERUSER NOBYPASSRLS')
        await conn.execute('GRANT USAGE ON SCHEMA agent_tiger TO tiger_t1_reader')
        await conn.execute('GRANT SELECT,INSERT ON agent_tiger.matches TO tiger_t1_reader')
        await conn.execute('CREATE POLICY extra_allow ON agent_tiger.matches USING (true) WITH CHECK (true)')
        try:
            async with conn.transaction():
                await conn.execute('SET LOCAL ROLE tiger_t1_reader')
                await conn.execute("SELECT set_config('app.tenant_id',$1,true)",str(OTHER))
                assert await conn.fetchval('SELECT count(*) FROM agent_tiger.matches') == 0
                with pytest.raises(asyncpg.InsufficientPrivilegeError):
                    async with conn.transaction():
                        await conn.execute("INSERT INTO agent_tiger.matches(tenant_id,sku,url,method,identifiers,seen_on,state) VALUES($1,'other',$2,'gtin','{}',$2,'confirmed')",TENANT,PAGE)
                await conn.execute("SELECT set_config('app.tenant_id',$1,true)",str(TENANT))
                assert await conn.fetchval('SELECT count(*) FROM agent_tiger.matches') == 1
        finally:
            await conn.execute('DROP OWNED BY tiger_t1_reader')
            await conn.execute('DROP ROLE tiger_t1_reader')


@pytest.mark.asyncio
async def test_explicit_planning_requires_tiger_squad_and_never_uses_a_model(monkeypatch):
    async def same(actor, *args): return actor
    monkeypatch.setattr(command,'authorized_actor',same)
    monkeypatch.setattr(trigger_routes,'code_receipt',AsyncMock(return_value=TENANT))
    actor = command.Actor(TENANT,'offline',False,frozenset({'tiger'}))
    for text in ('tiger.match','tiger.position','tiger.match.confirm '+str(OTHER),'tiger.match.reject '+str(OTHER)):
        plan = await command.tiger_code_plan(actor,[{'role':'user','content':text}],None)
        assert json.loads(plan.content)['actions'][0]['tool'] == text.split()[0]
    with pytest.raises(HTTPException) as exc:
        await command.tiger_code_plan(command.Actor(TENANT,'offline',False),[{'role':'user','content':'tiger.match'}],None)
    assert exc.value.status_code == 403
    assert command.ADAPTERS['tiger.position'].method == 'GET'
    assert all(not command.ADAPTERS[t].paid for t in ('tiger.match','tiger.position','tiger.match.confirm','tiger.match.reject'))


@pytest.mark.asyncio
async def test_start_durable_job_returns_matches_to_existing_card_and_denies_other_tenant(corridor, monkeypatch):
    args, operation = {}, uuid4()
    token = CONFIRMED.set((TENANT,'offline-user',operation,'tiger.match',args))
    try:
        response = await corridor.client.post('/v1/access/tiger/match',json=args)
    finally:
        CONFIRMED.reset(token)
    assert response.status_code == 200, response.text
    result = response.json()
    job = await corridor.pool.fetchrow('SELECT * FROM agent_tiger.jobs WHERE tenant_id=$1 AND id=$2', TENANT,UUID(result['job_id']))
    assert job['kind'] == 'competitor_match' and job['timeout_s'] == 45
    assert result['cost_usd'] == 0 and result['model_calls'] == 0
    gate = OfflineGate()
    async def fetch(url, **kwargs):
        assert kwargs == {'catalogue':True}
        if url.endswith('robots.txt'):
            return {'status':200,'text':'User-agent: *\nAllow: /'}
        return {'status':200,'text':'<urlset><url><loc>'+PAGE+'</loc></url></urlset>'}
    async def render(url, session, agent, tenant, task, **kwargs):
        assert kwargs == {'catalogue_match':True} and tenant == str(TENANT)
        return {'ok':True,'url':url,'html':markup() if url == PAGE else ''}
    monkeypatch.setattr(corridor.agent,'_fetch_text',fetch)
    monkeypatch.setattr(corridor.agent,'_render',render)
    monkeypatch.setattr(corridor.agent,'DiscoveryGate',lambda pool:gate)
    monkeypatch.setattr(corridor.agent.app.state,'http',corridor.client,raising=False)
    monkeypatch.delenv('TANK_KEY',raising=False)
    for _ in range(30):
        data = await corridor.agent.competitor_match(SimpleNamespace(tenant_id=str(TENANT),job_id=str(job['id']),input=json.loads(job['input'])))
        await corridor.pool.execute("UPDATE agent_tiger.jobs SET status='completed',result=$3::jsonb WHERE tenant_id=$1 AND id=$2",TENANT,job['id'],json.dumps(data))
        if not data['continuation_id']:
            break
        job = await corridor.pool.fetchrow('SELECT * FROM agent_tiger.jobs WHERE id=$1', UUID(data['continuation_id']))
    else:
        pytest.fail('Discovery did not finish its bounded slices')
    card = await access.tiger_card_result(TENANT,result)
    assert card['status'] == 'completed'
    assert card['matches'][0]['url'] == PAGE and card['matches'][0]['identifiers']['seen']['gtins'] == [GTIN]
    assert (await access.tiger_card_result(OTHER,{'job_id':result['job_id'],'matches':[]}))['matches'] == []
    assert await corridor.pool.fetchval('SELECT count(*) FROM agent_tiger.watchlist WHERE tenant_id=$1',TENANT) == 1


@pytest.mark.asyncio
async def test_no_squad_grant_cannot_run_position_or_spend_a_receipt(corridor):
    await corridor.pool.execute('DELETE FROM tank.tenant_squad WHERE tenant_id=$1',TENANT)
    response = await corridor.client.get('/v1/access/tiger/position')
    assert response.status_code == 403
    assert await corridor.pool.fetchval('SELECT count(*) FROM tank.ledger') == 0


@pytest.mark.asyncio
async def test_human_check_records_tenant_queue_without_match_or_watch(corridor):
    assert (await publish(corridor,'',human=True))['human_check'] is True
    assert await corridor.pool.fetchval("SELECT reason FROM tank.access_queue WHERE tenant_id=$1 AND site=$2",TENANT,SITE) == 'captcha'
    assert await corridor.pool.fetchval('SELECT count(*) FROM agent_tiger.matches') == 0
    assert await corridor.pool.fetchval('SELECT count(*) FROM agent_tiger.watchlist') == 0


@pytest.mark.asyncio
async def test_matching_preserves_existing_watch_reader_and_ocr(corridor, monkeypatch):
    await publish(corridor,markup())
    calls = []
    async def extract(tenant,name,body):
        calls.append(name)
        assert name in {'tiger.price_extract', 'tiger.price_ocr'}
        return {'items': [],'method':None}
    async def render(*args,**kwargs):
        return {'ok':True,'url':PAGE,'html':'<p>No structured price</p>','png_base64':'offline'}
    async def feed(*args): return {'found':False}
    async def approved(*args):
        return {'decision':'read','reason':'offline'}
    # The existing check runner owns observation/alert persistence. Capture its
    # injected readers to exercise both paths without any external/model call.
    async def run(store,tenant,watch,agent,render_fn,extract_fn,ocr_fn,*args,**kwargs):
        await extract_fn('<p>Offline</p>',PAGE)
        assert (await ocr_fn('offline',PAGE))['items'] == []
        return {'status':'unread'}
    monkeypatch.setattr(corridor.agent,'run_check',run)
    monkeypatch.setattr(corridor.agent,'_render',render)
    monkeypatch.setattr(corridor.agent,'official_feed',feed)
    ctx = SimpleNamespace(tenant_id=str(TENANT),input={'url':PAGE},job_id=uuid4(),agent='tiger',files=None,
                          tank=SimpleNamespace(run_skill=extract,approved_skill=approved))
    assert await corridor.agent.check(ctx) == {'status':'unread'}
    assert calls == ['tiger.price_extract', 'tiger.price_ocr']


from test_agent1_browser import visitor as _offline_visitor  # noqa: E402
visitor = _offline_visitor
from test_agent1_isolation import browser as public_browser


@pytest.mark.asyncio
async def test_discovery_browser_only_admits_one_anonymous_get_and_never_clicks(visitor, monkeypatch):
    visitor.gate.set()
    monkeypatch.setenv('ACCESS_ROOM','tiger')
    monkeypatch.setattr(public_browser,'access_configured',lambda:False)
    monkeypatch.setattr(public_browser,'held',{})
    clicks = AsyncMock(side_effect=AssertionError('Discovery must never click'))
    monkeypatch.setattr(public_browser,'confirm_age',clicks)
    result = await public_browser.visit(public_browser.Page(url=PAGE,catalogue_match=True,price_reader=True),
        str(TENANT),str(uuid4()),SITE)
    assert result['ok'] and visitor.context_options['storage_state'] is None
    assert visitor.started == []
    assert visitor.robots_calls == [PAGE]
    assert visitor.request_options == [{'timeout': 10000, 'max_redirects': 0}]
    clicks.assert_not_awaited()


@pytest.mark.asyncio
async def test_discovery_browser_uses_existing_human_check_detection(visitor, monkeypatch):
    visitor.gate.set()
    visitor.html = '<div class="g-recaptcha">Verify you are human</div>'
    monkeypatch.setenv('ACCESS_ROOM','tiger')
    monkeypatch.setattr(public_browser,'access_configured',lambda:False)
    result = await public_browser.visit(public_browser.Page(url=PAGE,catalogue_match=True,price_reader=True),
        str(TENANT),str(uuid4()),SITE)
    assert result['challenge'] and not result['ok'] and not result.get('html')


def test_relative_product_urls_are_resolved_before_accepting_evidence():
    assert access.tiger_product_evidence(markup(url='/products/item'),PAGE)
    assert access.tiger_product_evidence(markup(url='/different-product'),PAGE) == []


@pytest.mark.asyncio
async def test_two_own_skus_on_one_competitor_page_are_not_arbitrarily_linked(corridor,monkeypatch):
    async def catalogue(tenant):
        return [OWN,{**OWN,'sku':'second','gtin':'036000291452'}]
    monkeypatch.setattr(access,'tiger_catalogue',catalogue)
    result = await publish(corridor,markup()+markup(gtin13=None,gtin12='036000291452'))
    assert result['matches'] == []
    assert await corridor.pool.fetchval('SELECT count(*) FROM tank.access_feed_links') == 0
    assert await corridor.pool.fetchval('SELECT count(*) FROM agent_tiger.watchlist') == 0


@pytest.mark.asyncio
async def test_failed_watch_creation_cannot_commit_a_feed_link(corridor,monkeypatch):
    async def unavailable(*args):
        return httpx.Response(503,json={})
    monkeypatch.setattr(sys.modules['main'],'_tiger_call',unavailable)
    response = await corridor.client.post('/v1/access/rig/tiger/match-page',json={
        'tenant_id':str(TENANT),'site':SITE,'url':PAGE,'html':markup()})
    assert response.status_code == 503
    assert await corridor.pool.fetchval('SELECT count(*) FROM tank.access_feed_links') == 0
    assert await corridor.pool.fetchval('SELECT state FROM agent_tiger.matches WHERE tenant_id=$1',TENANT) == 'suggested'

@pytest.mark.parametrize('rule', ['/?s=', '/*?s='])
def test_discovery_robots_matches_queries_and_wildcards(rule):
    from rig_watch import discovery_robots_allows
    body = 'User-agent: *\nDisallow: ' + rule
    assert not discovery_robots_allows(body, SITE + '/?s=' + GTIN + '&post_type=product')
    assert discovery_robots_allows(body, PAGE)
    assert discovery_robots_allows('User-agent: *\nDisallow: /products/*$\nAllow: /products/item$', PAGE)


def test_link_filter_never_resolves_dns(monkeypatch):
    from rig_watch import discovery_same
    monkeypatch.setattr(socket, 'getaddrinfo', lambda *a, **k: pytest.fail('link filter resolved DNS'))
    assert discovery_same(SITE, SITE.upper().replace('HTTPS:', 'https:') + '/product')
    assert not discovery_same(SITE, SITE + ':444/product')
    assert not discovery_same(SITE, SITE + '/manual.pdf')


@pytest.mark.asyncio
@pytest.mark.parametrize('response', [
    {'status':200, 'text':'<!doctype html><html>Not found</html>'},
    {'status':302, 'location':SITE+'/'}, {'status':410}, {'status':500}])
async def test_odd_sitemap_does_not_prevent_search(response):
    gate, published = OfflineGate(), []
    async def fetch(url):
        return {'status':404} if url.endswith('robots.txt') else response
    async def render(url):
        if '/search?' in url:
            return {'ok':False, 'reason':'redirect', 'status':302, 'location':PAGE}
        return {'ok':True,'url':url,'html':markup()}
    async def publish(site,url,html,human):
        published.append(url)
        return {'matches':[{'sku':'own','state':'confirmed'}]}
    result = await CatalogueDiscovery(fetch,render,gate,publish).run([SITE],[OWN])
    assert result['sites'][0]['status'] == 'completed'
    assert published == [PAGE]
    assert gate.calls.count(PAGE) == 1
    assert gate.calls.index(PAGE) > gate.calls.index(SITE+'/search?q='+GTIN)
    assert gate.calls.count(SITE+'/sitemap.xml') == 1


def test_large_and_truncated_sitemaps_keep_bounded_locations():
    from rig_watch import discovery_sitemap
    source = '<urlset>' + ''.join('<url><loc>'+SITE+'/p/'+str(i)+'</loc></url>' for i in range(4000)) + '</urlset>'
    assert len(source.encode()) > 100000
    kind, urls, cut = discovery_sitemap(source)
    assert kind == 'urlset' and len(urls) == 4000 and not cut
    assert discovery_sitemap(source, limit=10)[2]
    assert discovery_sitemap(source[:-20])[2]


@pytest.mark.asyncio
async def test_search_markup_is_not_published_and_pdf_is_not_reserved():
    gate, published = OfflineGate(), []
    async def fetch(url):
        if url.endswith('robots.txt'):
            return {'status':404}
        return {'status':200, 'text':'<urlset><url><loc>'+SITE+'/manual.pdf</loc></url></urlset>'}
    async def render(url): return {'ok':True,'url':url,'html':markup()}
    async def publish(*args): published.append(args); return {'matches':[]}
    await CatalogueDiscovery(fetch,render,gate,publish).run([SITE],[OWN])
    assert not published and not gate.blocked
    assert not any(url.endswith('.pdf') for url in gate.calls)


@pytest.mark.asyncio
@pytest.mark.parametrize('status',['waiting','handling'])
async def test_existing_handoff_is_unchanged_by_discovery(corridor,status):
    await corridor.pool.execute("""INSERT INTO tank.access_queue(tenant_id,room,site,reason,browser_handle,status,handler)
        VALUES($1,'tiger',$2,'captcha',$3,$4,'founder')""", TENANT,SITE,uuid4(),status)
    before = dict(await corridor.pool.fetchrow('SELECT * FROM tank.access_queue WHERE tenant_id=$1',TENANT))
    await publish(corridor,'',human=True)
    assert dict(await corridor.pool.fetchrow('SELECT * FROM tank.access_queue WHERE tenant_id=$1',TENANT)) == before


@pytest.mark.asyncio
async def test_large_unmatched_catalogue_position_fits_card(corridor,monkeypatch):
    async def catalogue(tenant): return [{**OWN,'sku':str(i)} for i in range(1000)]
    monkeypatch.setattr(access,'tiger_catalogue',catalogue)
    response = await corridor.client.get('/v1/access/tiger/position')
    assert response.status_code == 200
    assert response.json()['products'] == [] and response.json()['total'] == 0
    assert len(response.content) < 256000


@pytest.mark.asyncio
async def test_run_sightings_do_not_leak_into_other_cards(corridor):
    jobs = [uuid4(), uuid4()]
    for job in jobs:
        await corridor.pool.execute("INSERT INTO agent_tiger.jobs(id,tenant_id,kind,input) VALUES($1,$2,'competitor_match','{}')",job,TENANT)
    for job in jobs:
        response = await corridor.client.post('/v1/access/rig/tiger/match-page',json={
            'tenant_id':str(TENANT),'site':SITE,'url':PAGE,'html':markup(), 'job_id':str(job)})
        assert response.status_code == 200
    # A third run with the same time window saw nothing.
    third = uuid4()
    await corridor.pool.execute("INSERT INTO agent_tiger.jobs(id,tenant_id,kind,input) VALUES($1,$2,'competitor_match','{}')",third,TENANT)
    assert (await access.tiger_card_result(TENANT,{'job_id':str(third)}))['matches'] == []
    for job in jobs:
        assert len((await access.tiger_card_result(TENANT,{'job_id':str(job)}))['matches']) == 1


@pytest.mark.asyncio
async def test_card_database_error_preserves_saved_card(monkeypatch):
    monkeypatch.setattr(access,'_tiger_card_result',AsyncMock(side_effect=RuntimeError('offline DB unavailable')))
    saved = {'job_id':str(uuid4()),'matches':[]}
    assert await access.tiger_card_result(TENANT,saved) == saved


@pytest.mark.asyncio
async def test_catalogue_browser_preserves_cookie_bytes_and_refuses_redirects(visitor,monkeypatch):
    monkeypatch.setattr(public_browser,'access_configured',lambda:False)
    storage = public_browser.storage_for(str(TENANT),SITE)
    storage.parent.mkdir(parents=True,exist_ok=True)
    original = b'{"cookies":[{"name":"solved","value":"synthetic"}],"origins":[]}\n'
    storage.write_bytes(original)
    visitor.status, visitor.redirect = 302, PAGE
    result = await public_browser.visit(public_browser.Page(url=SITE+'/?s='+GTIN,catalogue_match=True),str(TENANT),str(uuid4()),SITE)
    assert result['reason'] == 'redirect' and result['location'] == PAGE
    assert visitor.started == [] and visitor.request_options[0]['max_redirects'] == 0
    assert storage.read_bytes() == original


@pytest.mark.asyncio
@pytest.mark.parametrize('private,pdf', [(True,False),(False,True)])
async def test_catalogue_unsupported_is_not_a_human_check(visitor,monkeypatch,private,pdf):
    monkeypatch.setattr(public_browser,'access_configured',lambda:private)
    monkeypatch.setattr(public_browser,'access_rpc',AsyncMock(return_value={'state':'allowed'}))
    result = await public_browser.visit(public_browser.Page(url=PAGE+('.pdf' if pdf else ''),catalogue_match=True),str(TENANT),str(uuid4()),SITE)
    assert result['reason'] == 'unsupported' and not result['challenge']
    assert visitor.robots_calls == []


@pytest.mark.asyncio
async def test_check_is_claimed_between_discovery_slices(corridor,monkeypatch):
    from chassis.worker import claim_next, run_claimed
    root, check = uuid4(), uuid4()
    await corridor.pool.execute("INSERT INTO agent_tiger.jobs(id,tenant_id,kind,input) VALUES($1,$2,'competitor_match',$3::jsonb)",root,TENANT,json.dumps({'sites':[SITE],'products':[OWN]}))
    monkeypatch.setattr(corridor.agent,'_fetch_text',AsyncMock(return_value={'status':404}))
    monkeypatch.setattr(corridor.agent,'DiscoveryGate',lambda pool:OfflineGate())
    first = await corridor.agent.competitor_match(SimpleNamespace(tenant_id=str(TENANT),job_id=str(root),input={'sites':[SITE],'products':[OWN]}))
    assert first['continuation_id']
    await corridor.pool.execute("UPDATE agent_tiger.jobs SET status='completed' WHERE id=$1",root)
    await corridor.pool.execute("INSERT INTO agent_tiger.jobs(id,tenant_id,kind,input,run_at) VALUES($1,$2,'check','{}',now()-interval '1 second')",check,TENANT)
    async with corridor.pool.acquire() as conn:
        claimed = await claim_next(conn,'tiger')
    assert claimed['id'] == check
    # The actual check handler gets a turn before traversal resumes.
    ran = []
    async def check_handler(ctx): ran.append(ctx.job_id); return {'status':'checked'}
    async with corridor.pool.acquire() as conn:
        await run_claimed(conn,'tiger',claimed,{'check':check_handler},lambda job:SimpleNamespace(job_id=str(job['id'])))
    assert await corridor.pool.fetchval('SELECT status FROM agent_tiger.jobs WHERE id=$1',check) == 'done'
    await corridor.pool.execute("UPDATE agent_tiger.jobs SET run_at=now() WHERE id=$1",UUID(first['continuation_id']))
    async with corridor.pool.acquire() as conn:
        continuation = await claim_next(conn,'tiger')
    assert continuation['id'] == UUID(first['continuation_id']) and ran == [str(check)]
    assert json.loads(continuation['input'])['cursor']['active']['queue']
    async with corridor.pool.acquire() as conn:
        await run_claimed(conn,'tiger',continuation,{'competitor_match':corridor.agent.competitor_match},
                          lambda job:SimpleNamespace(tenant_id=str(TENANT),job_id=str(job['id']),input=json.loads(job['input'])))
    assert corridor.agent._fetch_text.await_count == 2


@pytest.mark.asyncio
@pytest.mark.parametrize('role_first', [True,False])
async def test_agent_role_has_t1_privileges_in_both_deployment_orders(database,role_first):
    from chassis.roles import _ownership
    async with database.acquire() as conn:
        await conn.execute('CREATE ROLE agent_tiger NOLOGIN NOSUPERUSER NOBYPASSRLS')
        try:
            if role_first:
                # Existing deployment: migration grants to a role already provisioned.
                await conn.execute((ROOT/'tank/schema.sql').read_text())
            else:
                # Fresh deployment: provisioner's ownership pass follows migration.
                await conn.execute('GRANT USAGE,CREATE ON SCHEMA agent_tiger TO agent_tiger')
                await conn.execute(_ownership('agent_tiger'))
            for table in ('matches','match_runs','match_sightings','discovery_limits'):
                for privilege in ('SELECT','INSERT','UPDATE'):
                    assert await conn.fetchval("SELECT has_table_privilege('agent_tiger',$1,$2)",'agent_tiger.'+table, privilege)
            async with conn.transaction():
                await conn.execute('SET LOCAL ROLE agent_tiger')
                await conn.execute("SELECT set_config('app.tenant_id',$1,true)",str(TENANT))
                await conn.execute("INSERT INTO agent_tiger.discovery_limits(site) VALUES($1)",SITE)
                await conn.execute("UPDATE agent_tiger.discovery_limits SET requests=1 WHERE site=$1",SITE)
                assert await conn.fetchval('SELECT requests FROM agent_tiger.discovery_limits WHERE site=$1',SITE) == 1
                await conn.execute("INSERT INTO agent_tiger.match_runs(tenant_id,operation_id,ledger_id) VALUES($1,$2,$3)",TENANT,uuid4(),uuid4())
        finally:
            # Reassign disposable database objects before removing the NOLOGIN role.
            await conn.execute('REASSIGN OWNED BY agent_tiger TO postgres')
            await conn.execute('DROP OWNED BY agent_tiger')
            await conn.execute('DROP ROLE agent_tiger')

@pytest.mark.asyncio
async def test_catalogue_fetch_uses_separate_robot_and_sitemap_caps(corridor,monkeypatch):
    source = '<urlset>' + '<url><loc>'+PAGE+'</loc></url>' + ' ' * 150000 + '</urlset>'
    async def respond(request):
        return httpx.Response(200,text=source if request.url.path != '/robots.txt' else 'x'*150000)
    async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as client:
        monkeypatch.setattr(corridor.agent.app.state,'http',client)
        sitemap = await corridor.agent._fetch_text(SITE+'/map.xml',catalogue=True)
        robots = await corridor.agent._fetch_text(SITE+'/robots.txt',catalogue=True)
    assert sitemap['text'] == source and not sitemap['truncated']
    assert len(robots['text']) == 100000 and robots['truncated']


def test_serialized_card_bound_includes_escaped_text_duplicate():
    result = access.tiger_bounded_card({'products':[{'sku':'\\"'*2000} for _ in range(100)],'has_more':False},'products')
    assert len(json.dumps(result).encode()) < 256000
    assert result['has_more'] and result['products']

@pytest.mark.asyncio
@pytest.mark.parametrize('marker', ['Confirm you are human','Prove you are human','Sorry, blocked','Your request has been blocked'])
async def test_sitemap_challenge_fragments_use_browser_detector(marker):
    gate, recorded = OfflineGate(), []
    async def fetch(url):
        return {'status':404} if url.endswith('robots.txt') else {'status':200,'text':'<div>'+marker+'</div>'}
    async def render(url): return {'ok':False,'challenge':True}
    async def publish(site,url,html,human): recorded.append(human); return {'matches':[]}
    result = await CatalogueDiscovery(fetch,render,gate,publish).run([SITE],[OWN])
    assert result['sites'][0]['status'] == 'human_check' and recorded == [True]
    assert gate.calls.count(SITE+'/sitemap.xml') == 2
