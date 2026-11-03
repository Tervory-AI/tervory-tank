"""Offline watch measurements: fake proxy responses/tool reports and real persistence."""
import hashlib
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
import sys

import httpx
import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT/'agents/radix'), str(ROOT/'tests/radix_i8')]
import passive_r6 as r6
import passive_store
from test_events import pool as pool, watched, A, B, DOMAIN, TARGET

EICAR = b'X5O!P%@AP[4\\PZX54(P^)7CC)7}$' + b'EICAR-STANDARD-ANTIVIRUS-TEST-FILE!$H+H*'


def certificate(days):
    now = datetime.now(timezone.utc)
    fmt = '%b %d %H:%M:%S %Y GMT'
    return {'subjectAltName': [('DNS', DOMAIN)],
            'notBefore': (now-timedelta(days=20)).strftime(fmt),
            'notAfter': (now+timedelta(days=days)).strftime(fmt)}


@pytest.mark.parametrize('days,rule', [(-1,'tls-expired'), (10,'tls-expiring')])
def test_expiry_reuses_real_checker(days, rule):
    from live import tls_findings
    result = tls_findings(certificate(days),'TLSv1.3',TARGET,host=DOMAIN)
    assert [r['rule'] for r in result] == [rule]


def test_page_changes_and_unchanged_hash():
    digest = hashlib.sha256(b'placeholder').hexdigest()
    assert r6.page_changes({TARGET:digest},{TARGET:digest}) == []
    changed = r6.page_changes({TARGET:digest},{TARGET:'a'*64})
    assert changed[0]['rule'] == 'changed'
    assert changed[0]['facts'] == {'url':TARGET,'old_sha256':'a'*64,'new_sha256':digest}
    assert r6.page_changes({}, {TARGET:digest})[0]['rule'] == 'gone'
    assert r6.page_changes({TARGET:digest}, {})[0]['rule'] == 'new'


def test_links_reject_other_hosts_ports_credentials_and_queries():
    parser = r6.Links(TARGET)
    parser.feed('''<a href="/placeholder">placeholder</a><a href="https://other-placeholder.example/">x</a>
      <a href="https://placeholder.example:444/">x</a><a href="http://placeholder.example/">x</a>
      <a href="https://placeholder:placeholder@placeholder.example/">x</a><a href="/?token=placeholder">x</a>''')
    assert parser.links == [TARGET+'placeholder']
    argv = r6.testssl_command(TARGET, Path('/placeholder.json'))
    assert '--ip=proxy' in argv and '--nodns=none' in argv
    assert argv[argv.index('--proxy')+1] == 'radix-passive-proxy:8082'
    assert '--phone-out' not in argv


async def tool(argv, directory, seconds):
    assert seconds > 0
    if argv[0].endswith('testssl.sh'):
        Path(argv[argv.index('--jsonfile')+1]).write_text(json.dumps([
            {'id':'TLS1','severity':'HIGH','finding':'TLS 1 offered'}]))
        return 0,b'',b''
    if argv[0].endswith('clamscan'):
        if '--version' in argv:
            return 0,b'ClamAV placeholder/placeholder/Tue Nov 3 2026',b''
        assert Path(argv[-1]).read_bytes() == EICAR
        return 1,(argv[-1]+': Eicar-Test-Signature FOUND\n').encode(),b''
    assert argv[0] == '/usr/bin/node'
    return 0,json.dumps({'findings':[{'tool':'axe-core','rule':'image-alt','severity':'serious',
        'file':TARGET,'item':'["img"]','facts':{'page':TARGET,'element':['img'],'help':'Images must have alternative text',
        'helpUrl':'https://dequeuniversity.com/rules/axe/4.14/image-alt'},
        'explanation':'Images must have alternative text','remediation':'https://dequeuniversity.com/rules/axe/4.14/image-alt'}],
        'cookies':[{'name':'placeholder','domain':DOMAIN,'path':'/','expiry':-1,'Secure':True,
                    'HttpOnly':False,'SameSite':'Lax','first_party':True}],
        'third_party_refused':1,'client_refused':0}).encode(),b''


def pages():
    calls = []
    async def request(req):
        calls.append(str(req.url))
        assert req.url.host == DOMAIN and req.url.port in (None,443)
        if req.url.path == '/placeholder-file':
            return httpx.Response(200,headers={'content-type':'application/octet-stream'},content=EICAR)
        return httpx.Response(200,headers={'content-type':'text/html'},
            text='<html><a href="/placeholder-file">placeholder</a><img src="/placeholder.png"></html>')
    return calls,httpx.MockTransport(request)


@pytest.mark.asyncio
async def test_tools_find_eicar_axe_cookies_and_preserve_only_measurements(tmp_path):
    calls, transport = pages()
    result = await r6.collect(TARGET,tmp_path,run=tool,transport=transport)
    rules = {r['rule'] for r in result['findings']}
    assert {'Eicar-Test-Signature','image-alt','cookie','missing-privacy-notice','TLS1','new'} <= rules
    assert result['checks']['browser']['third_party_refused'] == 1
    assert result['checks']['malware']['database_date'] == 'Tue Nov 3 2026'
    assert set(result['page_hashes']) == {TARGET}
    assert all(u.startswith(TARGET) for u in calls)
    assert not list(tmp_path.glob('download-*'))
    assert EICAR.decode() not in json.dumps(result)
    cookie = next(r for r in result['findings'] if r['rule']=='cookie')
    assert 'value' not in cookie['facts']
    assert 'essential' not in json.dumps(cookie)
    assert 'explanation' not in passive_store.report_finding(cookie)


@pytest.mark.asyncio
async def test_zero_budget_skips_never_passes_or_fetches(tmp_path):
    async def forbidden(*args): raise AssertionError('placeholder: work after budget')
    result = await r6.collect(TARGET,tmp_path,run=forbidden,budget=r6.Budget(0),
        transport=httpx.MockTransport(forbidden))
    assert all(c['status']=='skipped' for c in result['checks'].values())
    assert result['page_hashes'] is None
    assert all(f['rule']=='skipped' for f in result['findings'])


@pytest.mark.asyncio
async def test_memory_failure_skipped_other_checks_continue(tmp_path):
    async def memory(argv, directory, seconds):
        if argv[0].endswith('clamscan') and '--version' not in argv:
            return -9,b'',b''
        return await tool(argv,directory,seconds)
    _,transport=pages()
    result=await r6.collect(TARGET,tmp_path,run=memory,transport=transport)
    assert result['checks']['malware'] == {'status':'skipped','reason':'memory_limit'}
    assert result['checks']['browser']['status']=='complete'
    assert any(f['tool']=='clamav' and f['rule']=='skipped' for f in result['findings'])


@pytest.mark.asyncio
async def test_incomplete_pages_never_make_gone_findings(tmp_path):
    async def fail(req): return httpx.Response(429)
    result = await r6.collect(TARGET,tmp_path,run=tool,transport=httpx.MockTransport(fail),previous={TARGET:'a'*64})
    assert result['page_hashes'] is None
    assert not any(f['rule']=='gone' for f in result['findings'])
    assert result['checks']['pages']['status']=='partial'


@pytest.mark.asyncio
async def test_snapshot_atomic_complete_and_tenant_scoped(pool,tmp_path):
    store=await watched(pool)
    _,transport=pages()
    result=await r6.collect(TARGET,tmp_path,run=tool,transport=transport)
    ident=await store.create(A,TARGET,passive_store.watch_artifact(DOMAIN),watched=True)
    assert await store.running(A,ident)
    await store.complete(A,ident,result['findings'],measurements=result)
    assert await store.previous_hashes(A,DOMAIN)==result['page_hashes']
    assert await store.previous_hashes(B,DOMAIN)=={}
    delta=await store.changes(A,DOMAIN)
    assert delta['checks']['browser']['third_party_refused']==1
    assert any(f.get('facts',{}).get('database_date') for f in delta['findings'])
    assert await store.changes(B,DOMAIN)=={'status':'pending'}


@pytest.mark.asyncio
async def test_new_tables_force_rls_in_existing_rollout(pool):
    from chassis.tenant_db import TenantPool, tenant_scope
    from uuid import uuid4
    import asyncpg
    await watched(pool)
    async with pool.acquire() as conn:
        await conn.execute('CREATE SCHEMA IF NOT EXISTS tank')
        await conn.execute('CREATE TABLE IF NOT EXISTS tank.command_threads(id integer)')
        await conn.execute('ALTER TABLE tank.command_threads ENABLE ROW LEVEL SECURITY')
        await conn.execute((ROOT/'agents/radix/schema.sql').read_text())
        await conn.execute("""DO $$ BEGIN CREATE ROLE radix_placeholder_r6 NOLOGIN;
          EXCEPTION WHEN duplicate_object THEN NULL; END $$""")
        await conn.execute('GRANT USAGE ON SCHEMA agent_radix TO radix_placeholder_r6')
        await conn.execute('GRANT SELECT,INSERT,UPDATE ON ALL TABLES IN SCHEMA agent_radix TO radix_placeholder_r6')
        ident = uuid4()
        await conn.execute("""INSERT INTO agent_radix.page_hashes(tenant_id,scan_id,domain,url,sha256)
          VALUES($1,$2,$3,$4,$5)""", A,ident,DOMAIN,TARGET,'a'*64)
        await conn.execute("""INSERT INTO agent_radix.regulation_runs(tenant_id,domain,event_id,scan_id,facts)
          VALUES($1,$2,$3,$4,'{}')""", A,DOMAIN,uuid4(),ident)
        rows=await conn.fetch("""SELECT relrowsecurity,relforcerowsecurity FROM pg_class
          WHERE oid IN ('agent_radix.page_hashes'::regclass,'agent_radix.regulation_runs'::regclass)""")
        assert len(rows)==2 and all(r['relrowsecurity'] and r['relforcerowsecurity'] for r in rows)
    async def setup(conn): await conn.execute('SET ROLE radix_placeholder_r6')
    raw=await asyncpg.create_pool(__import__('os').environ['RADIX_I8_TEST_DATABASE_URL'],setup=setup,min_size=1,max_size=2)
    scoped=TenantPool(raw,pool)
    try:
        with tenant_scope(B):
            async with scoped.acquire() as conn:
                assert await conn.fetch('SELECT tenant_id FROM agent_radix.page_hashes') == []
                assert await conn.fetch('SELECT tenant_id FROM agent_radix.regulation_runs') == []
                with pytest.raises(asyncpg.InsufficientPrivilegeError):
                    await conn.execute("""INSERT INTO agent_radix.page_hashes(tenant_id,scan_id,domain,url,sha256)
                      VALUES($1,$2,$3,$4,$5)""", A,uuid4(),DOMAIN,TARGET,'a'*64)
        with tenant_scope(A):
            async with scoped.acquire() as conn:
                assert len(await conn.fetch('SELECT tenant_id FROM agent_radix.page_hashes')) == 1
                assert len(await conn.fetch('SELECT tenant_id FROM agent_radix.regulation_runs')) == 1
    finally:
        await raw.close()


@pytest.mark.asyncio
async def test_skipped_check_cannot_fix_or_replace_complete_baseline(pool):
    store=await watched(pool)
    finding=r6.measured('scan.tls','tls-expiring',TARGET,{'placeholder':True},severity='medium')
    async def complete(findings,checks):
        ident=await store.create(A,TARGET,passive_store.watch_artifact(DOMAIN),watched=True)
        assert await store.running(A,ident)
        await store.complete(A,ident,findings,measurements={'checks':checks})
        return ident
    first=await complete([finding],{'certificate':{'status':'complete'}})
    await complete([r6.measured('scan.tls','skipped',TARGET,{'reason':'lease_budget'})],
        {'certificate':{'status':'skipped','reason':'lease_budget'}})
    assert (await store.changes(A,DOMAIN))['fixed']==[]
    await complete([finding],{'certificate':{'status':'complete'}})
    result=await store.changes(A,DOMAIN)
    assert result['previous_scan_id']==str(first)
    assert len(result['unchanged'])==1 and result['fixed']==result['new']==[]


def test_partial_tls_json_retains_only_completed_objects():
    row={'id':'placeholder-protocol','severity':'HIGH','finding':'placeholder'}
    rows,complete=r6.tls_rows('['+json.dumps(row)+', {"id":')
    assert rows==[row] and complete is False
    assert r6.tls_rows(json.dumps([row]))==([row],True)


@pytest.mark.asyncio
async def test_tool_severity_preserved_but_bus_vocabulary_respected(pool,monkeypatch):
    from chassis import events
    from unittest.mock import AsyncMock
    publish=AsyncMock(return_value=True)
    monkeypatch.setattr(events,'publish',publish)
    store=await watched(pool)
    finding=r6.measured('axe-core','image-alt',TARGET,{'element':'placeholder'},severity='serious')
    ident=await store.create(A,TARGET,passive_store.watch_artifact(DOMAIN),watched=True)
    assert await store.running(A,ident)
    await store.complete(A,ident,[finding])
    assert (await store.findings(A,ident))[0]['severity']=='serious'
    assert publish.call_args.args[3]['severity']=='unknown'


@pytest.mark.asyncio
async def test_page_cap_does_not_falsely_mark_existing_page_gone(tmp_path):
    root='<html>'+''.join('<a href="/placeholder-'+str(n)+'">placeholder</a>' for n in range(12))+'</html>'
    content=b'<p>placeholder</p>'
    old=TARGET+'placeholder-11'
    async def request(req):
        return httpx.Response(200,headers={'content-type':'text/html'},content=root.encode() if req.url.path=='/' else content)
    result=await r6.collect(TARGET,tmp_path,run=tool,transport=httpx.MockTransport(request),
        previous={old:hashlib.sha256(content).hexdigest()})
    assert len(result['page_hashes'])==11 and old in result['page_hashes']
    assert len(result['checks']['pages']['skipped'])==2
    assert all(r['reason']=='page_limit' for r in result['checks']['pages']['skipped'])
    assert not any(f['file']==old and f['tool']=='sha256' for f in result['findings'])


@pytest.mark.asyncio
async def test_linked_page_404_is_gone_but_500_is_incomplete(tmp_path):
    gone=TARGET+'placeholder-gone'
    for status in (404,500):
        async def request(req):
            return httpx.Response(200 if req.url.path=='/' else status,headers={'content-type':'text/html'},
                text='<html><a href="/placeholder-gone">placeholder</a></html>')
        result=await r6.collect(TARGET,tmp_path,run=tool,transport=httpx.MockTransport(request),previous={gone:'a'*64})
        if status==404:
            assert any(f['rule']=='gone' and f['facts']=={'url':gone,'old_sha256':'a'*64,'new_sha256':None}
                       for f in result['findings'])
            assert result['checks']['pages']['status']=='complete'
        else:
            assert result['page_hashes'] is None
            assert not any(f['rule']=='gone' for f in result['findings'])


@pytest.mark.asyncio
async def test_watch_completion_survives_newer_event_queue_row(pool,monkeypatch):
    import passive_gateway as gateway
    import passive_routes as routes
    from regulation_events import Queue
    from test_events import message
    store=await watched(pool)
    class Server:
        def __init__(self,*args,**kwargs): pass
        def start(self): return self
        def close(self): pass
    async def proof(*args): return True
    monkeypatch.setattr(gateway,'private_bind_address',lambda:'127.0.0.1')
    lease=gateway.Lease(store,check=proof,server=Server)
    monkeypatch.setattr(gateway.app.state,'lease',lease,raising=False)
    async def scanner(*args):
        await Queue(pool).enqueue(A,message())
        return []
    result=await routes.execute(store,routes.Scan(tenant_id=A,target=TARGET,
        artifact=passive_store.watch_artifact(DOMAIN)),watched=True,scanner=scanner,
        http=httpx.AsyncClient(transport=httpx.ASGITransport(app=gateway.app)))
    assert result['status']=='complete'
    newer=await store.changes(A,DOMAIN)
    assert newer['status']=='pending' and newer['scan_id']!=result['scan_id']


@pytest.mark.parametrize('host,expected', [('shop.placeholder.example',[]),
    ('deep.shop.placeholder.example',['tls-name'])])
def test_watched_subdomain_certificate_wildcards_use_standard_matching(host,expected):
    from live import tls_findings
    cert=certificate(30)
    cert['subjectAltName']=[('DNS','*.placeholder.example')]
    result=tls_findings(cert,'TLSv1.3','https://'+host+'/',host=host)
    assert [f['rule'] for f in result]==expected


@pytest.mark.parametrize('label', ['CCPA notice','CPRA notice','California Consumer Privacy Act notice'])
def test_ccpa_notice_uses_existing_checker_without_new_wording(label):
    from scanlib.comply import scan_html
    result=scan_html('<html><a href="/placeholder-ccpa">'+label+'</a></html>',name='placeholder.html',page_host=DOMAIN)
    assert not any(f['rule']=='missing-privacy-notice' for f in result['findings'])
