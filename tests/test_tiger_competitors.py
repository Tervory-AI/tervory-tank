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
import os
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
    # Roles are cluster-wide: another xdist worker's disposable database can
    # acquire grants while this module owns agent_tiger, preventing DROP ROLE.
    # Keep the real ownership/RLS tests on a module-private cluster per worker.
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
async def test_review_read_is_tenant_scoped_newest_first_bounded_and_receipted(corridor):
    for tenant in (TENANT, OTHER):
        await corridor.pool.execute("""INSERT INTO agent_tiger.matches
            (tenant_id,sku,url,method,identifiers,seen_on,state,checked_at)
            SELECT $1,'own',$2 || n,'brand_mpn','{"seen":{"brand":"Offline brand","mpn":"ABC-1"}}'::jsonb,
                $2 || n,CASE WHEN n % 2=0 THEN 'suggested' ELSE 'rejected' END,
                now() - make_interval(secs => n) FROM generate_series(1,105) n""", tenant, SITE + '/item-')
    await publish(corridor, markup())  # Confirmed matches are excluded.
    response = await corridor.client.get('/v1/access/tiger/matches')
    assert response.status_code == 200, response.text
    result = response.json()
    assert len(result['matches']) == 100
    assert [row['url'] for row in result['matches']] == [SITE + '/item-' + str(n) for n in range(1,101)]
    assert all(row['tenant_id'] == str(TENANT) for row in result['matches'])
    assert all(row['identifiers']['seen']['mpn'] == 'ABC-1' and row['seen_on'] == row['url'] for row in result['matches'])
    receipt = await corridor.pool.fetchrow('SELECT * FROM tank.ledger WHERE id=$1', UUID(result['ledger_id']))
    assert receipt['tenant_id'] == TENANT and receipt['agent'] == 'tiger'
    assert receipt['task_type'] == 'tiger.matches' and receipt['cost_usd'] == 0
    assert command.ADAPTERS['tiger.matches'].method == 'GET'


@pytest.mark.asyncio
async def test_review_undo_requires_confirmation_and_only_changes_own_rejection(corridor):
    row = (await publish(corridor, markup(gtin13=None)))['matches'][0]
    match_id = row['id']
    assert (await decision(corridor, match_id, 'undo')).status_code == 409
    assert (await decision(corridor, match_id, 'reject')).status_code == 200
    response = await corridor.client.post('/v1/access/tiger/match/undo', json={'match_id': match_id})
    assert response.status_code == 409
    assert (await decision(corridor, match_id, 'undo', OTHER)).status_code == 404
    response = await decision(corridor, match_id, 'undo')
    assert response.status_code == 200 and response.json()['match']['state'] == 'suggested'
    assert response.json()['match']['identifiers'] == row['identifiers']
    assert (await decision(corridor, match_id, 'confirm')).status_code == 200
    assert (await decision(corridor, match_id, 'undo')).status_code == 409
    assert await corridor.pool.fetchval('SELECT state FROM agent_tiger.matches WHERE id=$1', UUID(match_id)) == 'confirmed'


@pytest.mark.asyncio
async def test_review_read_requires_tiger_entitlement(corridor):
    await corridor.pool.execute("DELETE FROM tank.tenant_squad WHERE tenant_id=$1 AND agent='tiger'", TENANT)
    assert (await corridor.client.get('/v1/access/tiger/matches')).status_code == 403


@pytest.mark.asyncio
async def test_review_keeps_stored_evidence_readable_when_catalogue_is_unavailable(corridor, monkeypatch):
    row = (await publish(corridor, markup(gtin13=None)))['matches'][0]
    monkeypatch.setattr(access, 'tiger_catalogue', AsyncMock(side_effect=HTTPException(503)))
    response = await corridor.client.get('/v1/access/tiger/matches')
    assert response.status_code == 200
    actual = response.json()['matches'][0]
    assert actual['id'] == row['id'] and actual['identifiers'] == row['identifiers']
    assert actual['product']['name'] is None


@pytest.mark.asyncio
async def test_review_buttons_use_real_durable_cards_and_decision_routes(corridor, monkeypatch):
    match = (await publish(corridor, markup(gtin13=None)))['matches'][0]
    app = corridor.client._transport.app
    app.include_router(command.router)
    app.dependency_overrides[command.identity] = lambda: corridor.actor.current
    monkeypatch.setattr(sys.modules['main'], 'app', app, raising=False)
    monkeypatch.setattr(sys.modules['main'], 'TANK_API_KEY', 'placeholder-service-key', raising=False)
    thread = (await corridor.client.post('/v1/command/threads', json={'title': 'Tiger'})).json()['thread_id']
    for operation, state in [('reject','rejected'),('undo','suggested'),('confirm','confirmed')]:
        card = await corridor.client.post(f'/v1/command/threads/{thread}/actions', json={
            'tool': 'tiger.match.' + operation, 'arguments': {'match_id': match['id']}})
        assert card.status_code == 200, card.text
        response = await corridor.client.post('/v1/command/cards/' + card.json()['card_id'], json={'action': 'confirm'})
        assert response.status_code == 200, response.text
        result = response.json()
        assert result['status'] == 'confirmed', result
        assert result['result']['match']['state'] == state
        assert result['result']['cost_usd'] == 0
    assert await corridor.pool.fetchval('SELECT state FROM agent_tiger.matches WHERE id=$1', UUID(match['id'])) == 'confirmed'


@pytest.mark.asyncio
async def test_saved_site_checks_use_only_own_latest_run_and_immutable_sightings(corridor):
    ctx = await seeded_run(corridor, [OWN])
    root = UUID(ctx.job_id)
    progress = {'sites': [{'site': SITE, 'status': 'human_check', 'pages': 12, 'warnings': []},
                          {'site': 'https://unsaved.example', 'status': 'completed', 'pages': 500}]}
    await corridor.pool.execute('UPDATE agent_tiger.match_runs SET progress=$2::jsonb WHERE job_id=$1', root, json.dumps(progress))
    await corridor.pool.execute("UPDATE agent_tiger.jobs SET finished_at=now(),status='completed',result=$2::jsonb WHERE id=$1", root, json.dumps(progress))
    first_finished = await corridor.pool.fetchval('SELECT finished_at FROM agent_tiger.jobs WHERE id=$1', root)
    await corridor.pool.execute("""INSERT INTO agent_tiger.jobs(id,tenant_id,kind,input,result,status,finished_at)
        VALUES($1,$2,'competitor_match',$3::jsonb,$4::jsonb,'completed',now()+interval '1 hour')""",
        uuid4(), TENANT, json.dumps({'root_job_id': str(root)}), json.dumps(progress))
    match = (await publish(corridor, markup(gtin13=None)))['matches'][0]
    for _ in range(2):
        await corridor.pool.execute('INSERT INTO agent_tiger.match_sightings(tenant_id,job_id,root_job_id,match_id,evidence) VALUES($1,$2,$3,$4,$5::jsonb)',
            TENANT, uuid4(), root, UUID(match['id']), json.dumps(match))
    checks = (await corridor.client.get('/v1/access/tiger/matches')).json()['site_checks']
    assert len(checks) == 1 and checks[0]['url'] == SITE
    assert checks[0]['pages'] == 12 and checks[0]['matches'] == 1
    assert checks[0]['status'] == 'human_check' and checks[0]['checked_at']
    assert checks[0]['checked_at'] == first_finished.isoformat()
    corridor.actor.current = command.Actor(OTHER, 'offline-user', False, frozenset({'tiger'}))
    assert (await corridor.client.get('/v1/access/tiger/matches')).json()['site_checks'] == []


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
    assert not await database.fetchval("SELECT relrowsecurity FROM pg_class WHERE oid='agent_tiger.matches'::regclass")
    await database.execute('ALTER TABLE tank.command_threads ENABLE ROW LEVEL SECURITY')
    async with database.acquire() as conn:
        await ensure_tables(conn, 'agent_tiger')
        await ensure_tables(conn, 'agent_tiger')
    for table in ('matches','match_runs','match_sightings'):
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
    for text in ('tiger.match','tiger.position','tiger.matches','tiger.match.confirm '+str(OTHER),'tiger.match.reject '+str(OTHER),'tiger.match.undo '+str(OTHER)):
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
    await corridor.pool.execute('INSERT INTO agent_tiger.match_runs(tenant_id,operation_id,job_id,ledger_id) VALUES($1,$2,$3,$4)',TENANT,uuid4(),root,uuid4())
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
    assert json.loads(continuation['input']) == {'root_job_id':str(root)}
    saved = await corridor.pool.fetchval('SELECT cursor FROM agent_tiger.match_runs WHERE tenant_id=$1 AND job_id=$2',TENANT,root)
    assert json.loads(saved)['active']['queue']
    async with corridor.pool.acquire() as conn:
        await run_claimed(conn,'tiger',continuation,{'competitor_match':corridor.agent.competitor_match},
                          lambda job:SimpleNamespace(tenant_id=str(TENANT),job_id=str(job['id']),input=json.loads(job['input'])))
    assert corridor.agent._fetch_text.await_count == 2


@pytest.mark.asyncio
@pytest.mark.parametrize('tables_first',[True,False])
async def test_room_migration_and_nonowner_tank_admin_after_role_ownership(database,tables_first):
    from chassis.roles import _ownership
    async with database.acquire() as conn:
        await conn.execute('CREATE ROLE agent_tiger NOLOGIN NOSUPERUSER NOBYPASSRLS')
        await conn.execute('CREATE ROLE tiger_t1_admin NOLOGIN NOSUPERUSER BYPASSRLS')
        try:
            if not tables_first:
                await conn.execute('DROP TABLE agent_tiger.match_sightings,agent_tiger.match_runs,agent_tiger.matches,agent_tiger.discovery_limits')
            await conn.execute('GRANT USAGE,CREATE ON SCHEMA agent_tiger TO agent_tiger')
            await conn.execute(_ownership('agent_tiger'))
            # Give the documented admin its existing Tank-owned migrations,
            # without membership/CREATE/ownership in the room's schema.
            schemas = ('tank','base','agent_tank','agent_base')
            relations = await conn.fetch("""SELECT format('%I.%I',n.nspname,c.relname) AS qualified,c.relkind
                FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace
                WHERE n.nspname=ANY($1::text[]) AND c.relkind IN ('r','p','S')
                ORDER BY CASE WHEN c.relkind='S' THEN 1 ELSE 0 END""", list(schemas))
            for relation in relations:
                kind = 'SEQUENCE' if relation['relkind'] == b'S' or relation['relkind'] == 'S' else 'TABLE'
                await conn.execute('ALTER '+kind+' '+relation['qualified']+' OWNER TO tiger_t1_admin')
            for schema in schemas:
                await conn.execute('ALTER SCHEMA '+schema+' OWNER TO tiger_t1_admin')
            functions = await conn.fetch("SELECT p.oid::regprocedure::text AS signature FROM pg_proc p JOIN pg_namespace n ON n.oid=p.pronamespace WHERE n.nspname IN ('tank','base','agent_tank','agent_base') AND p.prokind='f'")
            for function in functions:
                await conn.execute('ALTER FUNCTION '+function['signature']+' OWNER TO tiger_t1_admin')
            database_name = await conn.fetchval('SELECT current_database()')
            await conn.execute('GRANT CREATE ON DATABASE '+database_name+' TO tiger_t1_admin')
            async with conn.transaction():
                await conn.execute('SET LOCAL ROLE agent_tiger')
                await ensure_tables(conn,'agent_tiger')
                await ensure_tables(conn,'agent_tiger')
                assert not await conn.fetchval('SELECT rolsuper OR rolbypassrls FROM pg_roles WHERE rolname=current_user')
            async with conn.transaction():
                await conn.execute('SET LOCAL ROLE tiger_t1_admin')
                assert not await conn.fetchval("SELECT has_schema_privilege(current_user,'agent_tiger','CREATE')")
                assert not await conn.fetchval("SELECT pg_has_role(current_user,'agent_tiger','MEMBER')")
                assert await conn.fetchval('SELECT rolbypassrls AND NOT rolsuper FROM pg_roles WHERE rolname=current_user')
                await conn.execute((ROOT/'tank/schema.sql').read_text())
                await conn.execute((ROOT/'tank/schema.sql').read_text())
            # The ELSE branch must undo an earlier rollout, as in Tisan.
            await conn.execute('ALTER TABLE tank.command_threads ENABLE ROW LEVEL SECURITY')
            async with conn.transaction():
                await conn.execute('SET LOCAL ROLE agent_tiger')
                await ensure_tables(conn,'agent_tiger')
            await conn.execute('ALTER TABLE tank.command_threads DISABLE ROW LEVEL SECURITY')
            async with conn.transaction():
                await conn.execute('SET LOCAL ROLE agent_tiger')
                await ensure_tables(conn,'agent_tiger')
            for table in ('matches','match_runs','match_sightings'):
                assert not await conn.fetchval('SELECT relrowsecurity OR relforcerowsecurity FROM pg_class WHERE oid=$1::regclass','agent_tiger.'+table)
        finally:
            for role in ('agent_tiger','tiger_t1_admin'):
                await conn.execute('REASSIGN OWNED BY '+role+' TO postgres')
                await conn.execute('DROP OWNED BY '+role)
                await conn.execute('DROP ROLE '+role)


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

@pytest.mark.asyncio
async def test_position_arithmetic_includes_competitors_beyond_twentieth(corridor):
    urls = [SITE+'/products/'+str(i).zfill(3) for i in range(21)]
    await corridor.pool.executemany("""INSERT INTO agent_tiger.matches(tenant_id,sku,url,method,identifiers,seen_on,state)
        VALUES($1,'own',$2,'gtin','{}',$2,'confirmed')""", [(TENANT,url) for url in urls])
    await corridor.pool.executemany("""INSERT INTO agent_tiger.observations(tenant_id,url,price,currency,method)
        VALUES($1,$2,$3,'USD','jsonld')""", [(TENANT,url,1 if i == 20 else 12) for i,url in enumerate(urls)])
    response = await corridor.client.get('/v1/access/tiger/position')
    assert response.status_code == 200
    row = response.json()['products'][0]
    assert len(row['competitors']) == 21 and row['rank'] == 22
    assert row['cheapest']['url'] == urls[-1] and row['difference'] == '14.00'

@pytest.mark.asyncio
@pytest.mark.parametrize('failed_kind',['map','product'])
async def test_item_transport_timeout_continues_other_candidates_and_search(failed_kind):
    gate, visits = OfflineGate(), []
    bad = SITE + ('/listed.xml' if failed_kind == 'map' else '/products/bad')
    async def fetch(url):
        visits.append(url)
        if url.endswith('/robots.txt'):
            return {'status':200,'text':'User-agent: *\nSitemap: '+SITE+'/listed.xml'}
        if failed_kind == 'map' and url == bad:
            raise httpx.ReadTimeout('synthetic sitemap timeout')
        return {'status':200,'text':'<urlset><url><loc>'+SITE+'/products/bad</loc></url><url><loc>'+PAGE+'</loc></url></urlset>'}
    async def render(url):
        visits.append(url)
        if failed_kind == 'product' and url == bad:
            raise OSError('synthetic product transport error')
        return {'ok':True,'url':url,'html':''}
    result = await CatalogueDiscovery(fetch,render,gate,AsyncMock(return_value={'matches':[]})).run([SITE],[OWN])
    assert result['sites'][0]['status'] == 'completed'
    assert SITE+'/sitemap.xml' in visits and SITE+'/search?q='+GTIN in visits and PAGE in visits
    assert {'url':bad,'reason':'transport_error'} in result['sites'][0]['warnings']


@pytest.mark.asyncio
@pytest.mark.parametrize('status',[401,403])
async def test_browser_service_refusal_is_not_a_site_challenge(corridor,monkeypatch,status):
    async with httpx.AsyncClient(transport=httpx.MockTransport(lambda request:httpx.Response(status))) as client:
        monkeypatch.setattr(corridor.agent.app.state,'http',client)
        async def render(url):
            return await corridor.agent._render(url,'','tiger',str(TENANT),catalogue_match=True)
        active = {'robots':'','queue':[{'kind':'product','url':PAGE}],'visited':[],
                  'confirmed':[],'forms':[],'pages':0,'warnings':[]}
        publish_page = AsyncMock(side_effect=AssertionError('Service errors must not publish captcha items'))
        await CatalogueDiscovery(AsyncMock(),render,DiscoveryGate(corridor.pool),publish_page).step(
            [SITE],[OWN],{'site_index':0,'sites':[],'active':active})
    publish_page.assert_not_awaited()
    assert not await corridor.pool.fetchval('SELECT human_check FROM agent_tiger.discovery_limits WHERE site=$1',SITE)
    assert await corridor.pool.fetchval('SELECT count(*) FROM tank.access_queue') == 0


@pytest.mark.asyncio
async def test_slow_catalogue_fetch_has_an_overall_deadline(corridor,monkeypatch):
    class Trickle(httpx.AsyncByteStream):
        async def __aiter__(self):
            while True:
                await asyncio.sleep(.005)
                yield b' '
    async def respond(request): return httpx.Response(200,stream=Trickle())
    monkeypatch.setattr(corridor.agent,'CATALOGUE_FETCH_BUDGET_S',.03)
    async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as client:
        monkeypatch.setattr(corridor.agent.app.state,'http',client)
        with pytest.raises(TimeoutError):
            await asyncio.wait_for(corridor.agent._fetch_text(SITE+'/sitemap.xml',catalogue=True),.5)


@pytest.mark.asyncio
async def test_catalogue_render_has_an_overall_deadline(corridor,monkeypatch):
    async def respond(request):
        await asyncio.sleep(1)
        return httpx.Response(200,json={'ok':True})
    monkeypatch.setattr(corridor.agent,'CATALOGUE_RENDER_BUDGET_S',.03)
    async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as client:
        monkeypatch.setattr(corridor.agent.app.state,'http',client)
        with pytest.raises(TimeoutError):
            await asyncio.wait_for(corridor.agent._render(PAGE,'','tiger',str(TENANT),catalogue_match=True),.5)


async def seeded_run(system,products):
    root, operation = uuid4(), uuid4()
    payload = {'sites':[SITE],'products':products,'operation_id':str(operation)}
    await system.pool.execute("INSERT INTO agent_tiger.jobs(id,tenant_id,kind,input) VALUES($1,$2,'competitor_match',$3::jsonb)",root,TENANT,json.dumps(payload))
    await system.pool.execute('INSERT INTO agent_tiger.match_runs(tenant_id,operation_id,job_id,ledger_id) VALUES($1,$2,$3,$4)',TENANT,operation,root,uuid4())
    return SimpleNamespace(tenant_id=str(TENANT),job_id=str(root),input=payload)


@pytest.mark.asyncio
async def test_large_catalogue_continuation_input_is_only_a_run_reference(corridor,monkeypatch):
    products = [{**OWN,'sku':'product-'+str(i)} for i in range(2000)]
    ctx = await seeded_run(corridor,products)
    monkeypatch.setattr(corridor.agent,'_fetch_text',AsyncMock(return_value={'status':404}))
    monkeypatch.setattr(corridor.agent,'DiscoveryGate',lambda pool:OfflineGate())
    result = await corridor.agent.competitor_match(ctx)
    child = UUID(result['continuation_id'])
    payload = await corridor.pool.fetchval('SELECT input FROM agent_tiger.jobs WHERE id=$1',child)
    assert json.loads(payload) == {'root_job_id':ctx.job_id}
    assert len(payload.encode()) < 100
    assert await corridor.pool.fetchval('SELECT pg_column_size(input) FROM agent_tiger.jobs WHERE id=$1',child) < 100
    # One catalogue copy; the cursor lives once on the run, never in jobs.
    assert await corridor.pool.fetchval("SELECT count(*) FROM agent_tiger.jobs WHERE tenant_id=$1 AND input ? 'products'",TENANT) == 1
    assert await corridor.pool.fetchval("SELECT count(*) FROM agent_tiger.jobs WHERE tenant_id=$1 AND input ? 'cursor'",TENANT) == 0


@pytest.mark.asyncio
async def test_two_thousand_skus_without_gtin_need_only_bounded_empty_slices(corridor,monkeypatch):
    ctx = await seeded_run(corridor,[{**OWN,'sku':str(i),'gtin':None} for i in range(2000)])
    monkeypatch.setattr(corridor.agent,'_fetch_text',AsyncMock(return_value={'status':404}))
    monkeypatch.setattr(corridor.agent,'_render',AsyncMock(return_value={'ok':True,'url':SITE+'/','html':''}))
    monkeypatch.setattr(corridor.agent,'DiscoveryGate',lambda pool:OfflineGate())
    for slices in range(1,8):
        result = await corridor.agent.competitor_match(ctx)
        if not result['continuation_id']:
            break
        job = await corridor.pool.fetchrow('SELECT id,input FROM agent_tiger.jobs WHERE id=$1',UUID(result['continuation_id']))
        ctx = SimpleNamespace(tenant_id=str(TENANT),job_id=str(job['id']),input=json.loads(job['input']))
    else:
        pytest.fail('Unusable SKUs generated per-product continuations')
    assert slices <= 6 and result['status'] == 'completed'
    assert corridor.agent._render.await_count == 1


@pytest.mark.asyncio
async def test_exhausted_slice_marks_run_and_card_failed(corridor,monkeypatch):
    from chassis.worker import claim_next, run_claimed
    ctx = await seeded_run(corridor,[OWN])
    await corridor.pool.execute("UPDATE agent_tiger.jobs SET attempts=max_attempts-1 WHERE id=$1",UUID(ctx.job_id))
    await corridor.pool.execute('UPDATE agent_tiger.match_runs SET progress=$2::jsonb WHERE job_id=$1',UUID(ctx.job_id),json.dumps({'status':'running'}))
    monkeypatch.setattr(CatalogueDiscovery,'step',AsyncMock(side_effect=RuntimeError('synthetic slice failure')))
    async with corridor.pool.acquire() as conn:
        job = await claim_next(conn,'tiger')
        await run_claimed(conn,'tiger',job,{'competitor_match':corridor.agent.competitor_match},lambda job:ctx)
    assert await corridor.pool.fetchval('SELECT status FROM agent_tiger.jobs WHERE id=$1',UUID(ctx.job_id)) == 'failed'
    progress = json.loads(await corridor.pool.fetchval('SELECT progress FROM agent_tiger.match_runs WHERE job_id=$1',UUID(ctx.job_id)))
    assert progress['status'] == 'failed'
    assert (await access.tiger_card_result(TENANT,{'job_id':ctx.job_id}))['status'] == 'failed'


@pytest.mark.asyncio
async def test_card_reconciles_worker_crash_after_last_attempt(corridor):
    ctx = await seeded_run(corridor,[OWN])
    child = uuid4()
    await corridor.pool.execute("INSERT INTO agent_tiger.jobs(id,tenant_id,kind,input,status) VALUES($1,$2,'competitor_match',$3::jsonb,'failed')",child,TENANT,json.dumps({'root_job_id':ctx.job_id}))
    await corridor.pool.execute('UPDATE agent_tiger.match_runs SET progress=$2::jsonb WHERE job_id=$1',UUID(ctx.job_id),json.dumps({'status':'running','continuation_id':str(child)}))
    result = await access.tiger_card_result(TENANT,{'job_id':ctx.job_id})
    assert result['status'] == 'failed' and result['discovery']['failed_job_id'] == str(child)
    saved = json.loads(await corridor.pool.fetchval('SELECT progress FROM agent_tiger.match_runs WHERE job_id=$1',UUID(ctx.job_id)))
    assert saved['status'] == 'failed'

@pytest.mark.asyncio
async def test_room_startup_installs_matching_schema_before_serving(corridor,monkeypatch):
    from contextlib import asynccontextmanager
    @asynccontextmanager
    async def inner(instance):
        yield
    monkeypatch.setattr(corridor.agent,'_tiger_inner',inner)
    await corridor.pool.execute('DROP TABLE agent_tiger.match_sightings,agent_tiger.match_runs,agent_tiger.matches,agent_tiger.discovery_limits')
    # An administrative read pool must not be selected for owner-only room DDL.
    monkeypatch.setattr(corridor.agent.app.state,'pool',SimpleNamespace(raw=corridor.pool))
    async with corridor.agent.app.router.lifespan_context(corridor.agent.app):
        assert await corridor.pool.fetchval("SELECT to_regclass('agent_tiger.match_runs') IS NOT NULL")


@pytest.mark.asyncio
@pytest.mark.parametrize('enforced',[False,True])
async def test_room_schema_concurrently_repeats_without_catalog_writes(database,postgres,enforced):
    from chassis.roles import _ownership
    from urllib.parse import urlsplit,urlunsplit
    async with database.acquire() as conn:
        await conn.execute('CREATE ROLE agent_tiger NOLOGIN NOSUPERUSER NOBYPASSRLS')
        try:
            await conn.execute('GRANT USAGE,CREATE ON SCHEMA agent_tiger TO agent_tiger')
            await conn.execute(_ownership('agent_tiger'))
            if enforced:
                await conn.execute('ALTER TABLE tank.command_threads ENABLE ROW LEVEL SECURITY')
            async with conn.transaction():
                await conn.execute('SET LOCAL ROLE agent_tiger')
                await ensure_tables(conn,'agent_tiger')
            tables = ['agent_tiger.'+name for name in ('matches','match_runs','match_sightings','discovery_limits')]
            before = await conn.fetch('SELECT oid,xmin::text FROM pg_class WHERE oid=ANY($1::regclass[]) ORDER BY oid',tables)
            policies = await conn.fetch("SELECT oid,xmin::text FROM pg_policy WHERE polrelid=ANY($1::regclass[]) ORDER BY oid",tables)
            name = await conn.fetchval('SELECT current_database()')
            uri = urlunsplit(urlsplit(postgres.get_uri())._replace(path='/'+name))
            async def repeat():
                session = await asyncpg.connect(uri)
                try:
                    await session.execute('SET ROLE agent_tiger')
                    assert not await session.fetchval('SELECT rolsuper OR rolbypassrls FROM pg_roles WHERE rolname=current_user')
                    for _ in range(20):
                        await ensure_tables(session,'agent_tiger')
                finally:
                    await session.close()
            # Eight real sessions, beyond the fixture pool's five-connection cap.
            await asyncio.gather(*(repeat() for _ in range(8)))
            assert await conn.fetch('SELECT oid,xmin::text FROM pg_class WHERE oid=ANY($1::regclass[]) ORDER BY oid',tables) == before
            assert await conn.fetch('SELECT oid,xmin::text FROM pg_policy WHERE polrelid=ANY($1::regclass[]) ORDER BY oid',tables) == policies
        finally:
            await conn.execute('REASSIGN OWNED BY agent_tiger TO postgres')
            await conn.execute('DROP OWNED BY agent_tiger')
            await conn.execute('DROP ROLE agent_tiger')


@pytest.mark.asyncio
async def test_room_schema_repairs_only_missing_table_privileges(database):
    async with database.acquire() as conn:
        await conn.execute('CREATE ROLE agent_tiger NOLOGIN NOSUPERUSER NOBYPASSRLS')
        try:
            await ensure_tables(conn,'agent_tiger')
            await conn.execute('REVOKE UPDATE ON agent_tiger.matches FROM agent_tiger')
            tables = ['agent_tiger.'+name for name in ('match_runs','match_sightings','discovery_limits')]
            before = await conn.fetch('SELECT oid,xmin::text FROM pg_class WHERE oid=ANY($1::regclass[]) ORDER BY oid',tables)
            assert not await conn.fetchval("SELECT has_table_privilege('agent_tiger','agent_tiger.matches','UPDATE')")
            await ensure_tables(conn,'agent_tiger')
            assert await conn.fetchval("SELECT has_table_privilege('agent_tiger','agent_tiger.matches','UPDATE')")
            assert await conn.fetch('SELECT oid,xmin::text FROM pg_class WHERE oid=ANY($1::regclass[]) ORDER BY oid',tables) == before
        finally:
            await conn.execute('DROP OWNED BY agent_tiger')
            await conn.execute('DROP ROLE agent_tiger')


@pytest.mark.asyncio
@pytest.mark.parametrize('bad',['4006381333932','0000000000000','1234567',5012345678900,None])
async def test_search_skips_invalid_gtins_before_reserving(bad):
    assert access.tiger_gtin(bad) is None
    gate, visits = OfflineGate(), []
    async def render(url):
        visits.append(url)
        return {'ok':True,'url':url,'html':''}
    active = {'robots':'','queue':[],'visited':[],'confirmed':[],'forms':[],
              'pages':0,'warnings':[],'home_finished':True}
    state,done = await CatalogueDiscovery(AsyncMock(),render,gate,AsyncMock()).step(
        [SITE],[{**OWN,'sku':str(i),'gtin':bad} for i in range(200)]+[OWN],
        {'site_index':0,'sites':[],'active':active})
    assert not done and active['search_index'] == 201
    assert visits == [SITE+'/search?q='+GTIN]
    assert gate.calls == visits
    assert state['active'] is active


@pytest.mark.asyncio
async def test_slice_results_bound_warnings_and_keep_details_once_per_run(corridor,monkeypatch):
    ctx = await seeded_run(corridor,[OWN])
    root = UUID(ctx.job_id)
    step_number = 0
    warnings = [{'url':SITE+'/products/'+str(i)+'x'*160,'reason':'transport_error'} for i in range(200)]
    async def step(self,sites,products,cursor=None):
        nonlocal step_number
        cursor = cursor or {'site_index':0,'sites':[],'active':None}
        assert all('warnings' not in site for site in cursor['sites'])
        if step_number in (0,10,20):
            cursor['sites'].append({'site':SITE+'/'+str(step_number),'status':'completed','pages':200,'warnings':warnings})
        step_number += 1
        return cursor,step_number == 40
    monkeypatch.setattr(CatalogueDiscovery,'step',step)
    for _ in range(40):
        result = await corridor.agent.competitor_match(ctx)
        assert len(json.dumps(result).encode()) < 2048
        assert all(site['warning_count'] == 200 and 'warnings' not in site for site in result['sites'])
        if not result['continuation_id']:
            break
        row = await corridor.pool.fetchrow('SELECT id,input FROM agent_tiger.jobs WHERE id=$1',UUID(result['continuation_id']))
        ctx = SimpleNamespace(tenant_id=str(TENANT),job_id=str(row['id']),input=json.loads(row['input']))
    assert step_number == 40 and result['status'] == 'completed'
    run = await corridor.pool.fetchrow('SELECT progress,cursor FROM agent_tiger.match_runs WHERE job_id=$1',root)
    progress = json.loads(run['progress'])
    assert len(progress['sites']) == 3 and all(site['warnings'] == warnings for site in progress['sites'])
    assert run['cursor'] is None
    assert await corridor.pool.fetchval("SELECT count(*) FROM agent_tiger.jobs WHERE tenant_id=$1",TENANT) == 40
    assert await corridor.pool.fetchval("SELECT max(pg_column_size(result)) FROM agent_tiger.jobs WHERE tenant_id=$1",TENANT) < 2048
    assert await corridor.pool.fetchval("SELECT sum(pg_column_size(result)) FROM agent_tiger.jobs WHERE tenant_id=$1",TENANT) < 40*2048
