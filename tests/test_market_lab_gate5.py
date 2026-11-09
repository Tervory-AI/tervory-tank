"""Launch boundary review: adversarial files, auth, deadlines and durable claims."""
import asyncio
from contextlib import asynccontextmanager
import io
import json
from pathlib import Path
import sys
import subprocess
from types import SimpleNamespace
from uuid import uuid4
import zipfile

import asyncpg
import httpx
import pytest
from fastapi import FastAPI

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'agents/market_lab'))
from core import document_read, readiness, execution, database
from feeds.live import PoliteClient


def test_one_command_failure_never_prints_a_connection_value(monkeypatch):
    monkeypatch.setenv('TANK_KEY','placeholder-room-key')
    monkeypatch.setenv('DATABASE_URL','placeholder-private-invalid-database-url')
    result=subprocess.run([str(ROOT/'scripts/run-market-lab.sh'),'--job','refresh','--tenant',str(uuid4())],
                          cwd=ROOT,text=True,capture_output=True,timeout=20)
    assert result.returncode==1
    assert json.loads(result.stdout)['status']=='failed'
    assert 'placeholder-private-invalid-database-url' not in result.stdout+result.stderr
    assert 'Traceback' not in result.stderr


def workbook(sheet, extra=None):
    data=io.BytesIO()
    with zipfile.ZipFile(data,'w') as book:
        book.writestr('xl/worksheets/sheet1.xml',sheet)
        for name,raw in (extra or {}).items():book.writestr(name,raw)
    return data.getvalue()


@pytest.mark.parametrize('cell',['A20001','A9999999'])
def test_sparse_workbook_cannot_force_unbounded_allocation(cell,monkeypatch):
    raw=workbook(f'<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><sheetData><row r="1"><c r="{cell}"><v>1</v></c></row></sheetData></worksheet>')
    def allocate(*args):raise AssertionError('must reject before allocating rows')
    monkeypatch.setattr(document_read,'xlsx_tables',allocate)
    with pytest.raises(document_read.ReadError,match='20,000'):
        document_read.bounded_sheets(raw)


@pytest.mark.parametrize('name',['xl/workbook.xml','xl/sharedStrings.xml'])
def test_workbook_xml_entities_are_refused_in_every_part(name):
    raw=workbook('<worksheet/>',{name:'<!DOCTYPE x [<!ENTITY x "placeholder">]><x>&x;</x>'})
    with pytest.raises(document_read.ReadError,match='unsupported'):
        document_read.bounded_sheets(raw)


@pytest.mark.asyncio
async def test_settings_require_room_key_and_never_echo_values(monkeypatch):
    monkeypatch.setenv('TANK_KEY','placeholder-room-key')
    app=FastAPI();readiness.install(app)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url='http://room') as client:
        for key in ('','placeholder-wrong'):
            result=await client.get('/market/settings',headers={'X-Tank-Key':key})
            assert result.status_code==401
        result=await client.get('/market/settings',headers={'X-Tank-Key':'placeholder-room-key'})
        assert result.status_code==200 and 'placeholder-room-key' not in result.text
        for path in ('/docs','/redoc','/openapi.json'):
            assert (await client.get(path)).status_code==404


@pytest.mark.asyncio
async def test_shared_job_routes_require_auth_and_unexpected_errors_are_sanitized(monkeypatch,caplog):
    monkeypatch.setenv('TANK_KEY','placeholder-room-key')
    app=FastAPI();readiness.install(app);calls=[]
    @app.post('/jobs')
    async def enqueue():
        calls.append(True)
        raise RuntimeError('placeholder-private-database-url')
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url='http://room') as client:
        assert (await client.post('/jobs')).status_code==401
        assert calls==[]
        response=await client.post('/jobs',headers={'X-Tank-Key':'placeholder-room-key'})
        assert response.status_code==503 and 'Try again shortly' in response.text
        assert 'placeholder-private-database-url' not in response.text+caplog.text
        assert calls==[True]


def test_stalled_stream_has_total_deadline_closes_and_never_replays_partial_data():
    clock=[0.0];calls=[];closed=[]
    class Response:
        status=200
        def __iter__(self):
            yield b'first\n'
            clock[0]=100
            yield b'second\n'
        def close(self):closed.append(True)
    def open(request,**kwargs):
        calls.append(kwargs['timeout']);return Response()
    client=PoliteClient(opener=open,timeout=1,retries=3,delay=0,clock=lambda:clock[0])
    stream=client.iter_lines('https://publisher.example/records')
    assert next(stream)=='first\n'
    with pytest.raises(RuntimeError,match='failed'):next(stream)
    assert calls==[1] and closed==[True]


def test_transient_feed_failure_has_exact_retry_bound_and_redacted_error():
    calls=[]
    def fail(request,**kwargs):
        calls.append(kwargs['timeout'])
        raise TimeoutError('placeholder-private-query-value')
    client=PoliteClient(opener=fail,delay=0,sleep=lambda _:None)
    with pytest.raises(RuntimeError) as caught:client.get('https://publisher.example/data?key=placeholder-private-query-value')
    assert calls==[60.0]*3
    assert 'placeholder-private-query-value' not in str(caught.value)


@pytest.mark.asyncio
async def test_database_setup_failure_closes_connection_and_does_not_echo_url(monkeypatch):
    from unittest.mock import AsyncMock
    conn=SimpleNamespace(execute=AsyncMock(side_effect=TimeoutError()),close=AsyncMock())
    connect=AsyncMock(return_value=conn)
    monkeypatch.setattr(asyncpg,'connect',connect)
    with pytest.raises(TimeoutError):await database.connect('postgresql://placeholder.invalid/never-used')
    conn.close.assert_awaited_once()
    assert 'lock_timeout' in conn.execute.await_args.args[0]


@pytest.mark.asyncio
async def test_direct_connections_reuse_authenticated_tenant_scope_under_rls(tmp_path):
    import pgserver
    from chassis.tenant_db import tenant_scope
    from urllib.parse import urlsplit, urlunsplit
    server=pgserver.get_server(tmp_path/'rls')
    admin=await asyncpg.connect(server.get_uri())
    try:
        owner,other=uuid4(),uuid4()
        await admin.execute('''CREATE ROLE placeholder_market_user LOGIN;
            CREATE TABLE public.placeholder_tenant_data(tenant_id uuid);
            ALTER TABLE public.placeholder_tenant_data ENABLE ROW LEVEL SECURITY;
            CREATE POLICY own_rows ON public.placeholder_tenant_data
              USING (tenant_id=nullif(current_setting('app.tenant_id',true),'')::uuid);
            GRANT SELECT ON public.placeholder_tenant_data TO placeholder_market_user''')
        await admin.executemany('INSERT INTO public.placeholder_tenant_data VALUES($1)',[(owner,),(other,)])
        parts=urlsplit(server.get_uri())
        uri=urlunsplit(parts._replace(netloc='placeholder_market_user@'+(parts.netloc.split('@',1)[1] if '@' in parts.netloc else parts.netloc)))
        with tenant_scope(str(owner)):
            conn=await database.connect(uri)
            try:assert await conn.fetchval('SELECT tenant_id FROM public.placeholder_tenant_data')==owner
            finally:await conn.close()
        with tenant_scope(None):
            conn=await database.connect(uri)
            try:assert await conn.fetchval('SELECT count(*) FROM public.placeholder_tenant_data')==0
            finally:await conn.close()
    finally:
        await admin.close();server.cleanup()


@pytest.mark.asyncio
async def test_job_receipt_serializes_replays_and_rolls_back_code_work(tmp_path):
    import pgserver
    from chassis.db import ensure_schema
    from core.ledger import PostgresLedger
    server=pgserver.get_server(tmp_path/'claims')
    pool=await asyncpg.create_pool(server.get_uri(),min_size=1,max_size=4)
    try:
        async with pool.acquire() as conn:
            await ensure_schema(conn,'market_lab')
            await PostgresLedger(conn).apply_schema()
            await conn.execute('CREATE TABLE agent_market_lab.placeholder_effects (id uuid, tenant_id uuid)')
            owner,other,job=uuid4(),uuid4(),uuid4()
            await conn.execute("INSERT INTO agent_market_lab.jobs(id,tenant_id,kind,status,attempts) VALUES($1,$2,'opportunities','running',1)",job,owner)
        @asynccontextmanager
        async def connection(**kwargs):
            async with pool.acquire() as conn:yield PostgresLedger(conn)
        calls=[]
        async def action(ctx):
            calls.append(True)
            active=execution.active_ledger.get()
            await active.conn.execute('INSERT INTO agent_market_lab.placeholder_effects VALUES($1,$2)',job,owner)
            await asyncio.sleep(.05)
            async def notification():
                assert await pool.fetchval('SELECT count(*) FROM agent_market_lab.placeholder_effects')==1
            assert execution.defer(notification)
            return {'saved':True,'tenant_id':str(owner)}
        ctx=SimpleNamespace(job_id=str(job),tenant_id=str(owner),kind='opportunities',memory=None)
        guarded=execution.guarded(action,connection)
        a,b=await asyncio.gather(guarded(ctx),guarded(ctx))
        assert a==b and len(calls)==1
        from chassis.worker import _fail, _finish
        async with pool.acquire() as conn:
            # The chassis worker, not the handler, owns attempt completion.
            await _finish(conn,'market_lab',job,owner,a,1)
            await _fail(conn,'market_lab',job,owner,1,3,'TimeoutError')
            await _finish(conn,'market_lab',job,owner,{'wrong':True},1)
            completed=await conn.fetchrow('SELECT status,result FROM agent_market_lab.jobs WHERE tenant_id=$1 AND id=$2',owner,job)
            assert completed['status']=='done' and 'wrong' not in completed['result']
        assert await pool.fetchval('SELECT count(*) FROM agent_market_lab.placeholder_effects')==1
        foreign=SimpleNamespace(**{**vars(ctx),'tenant_id':str(other)})
        with pytest.raises(ValueError):await guarded(foreign)
        failed=uuid4()
        await pool.execute("INSERT INTO agent_market_lab.jobs(id,tenant_id,kind,status) VALUES($1,$2,'opportunities','running')",failed,owner)
        async def crash(ctx):
            await execution.active_ledger.get().conn.execute('INSERT INTO agent_market_lab.placeholder_effects VALUES($1,$2)',failed,owner)
            async def forbidden():raise AssertionError('must not publish rolled-back work')
            assert execution.defer(forbidden)
            raise TimeoutError()
        with pytest.raises(TimeoutError):
            await execution.guarded(crash,connection)(SimpleNamespace(**{**vars(ctx),'job_id':str(failed)}))
        assert await pool.fetchval('SELECT count(*) FROM agent_market_lab.placeholder_effects')==1
        assert await pool.fetchval('SELECT status FROM agent_market_lab.jobs WHERE id=$1',failed)=='running'
    finally:
        await pool.close();server.cleanup()


@pytest.mark.asyncio
async def test_parser_process_roundtrip_and_invalid_file_are_bounded():
    from core.document_process import extract
    parsed=await extract('inventory.csv',b'date,value,unit\n2026-11-05,4,cases\n')
    assert parsed['rows']==1 and parsed['tables'][0]['value']=='4'
    with pytest.raises(document_read.ReadError):await extract('broken.docx',b'not a package')


@pytest.mark.asyncio
async def test_parser_timeout_kills_reaps_and_has_no_credentials(monkeypatch):
    from core import document_process
    from unittest.mock import AsyncMock, Mock
    async def stuck(data=None):
        if data is None:return b'',None
        await asyncio.sleep(10)
    communicate=AsyncMock(side_effect=stuck)
    process=SimpleNamespace(communicate=communicate,kill=Mock(),wait=AsyncMock(),returncode=None)
    create=AsyncMock(return_value=process)
    monkeypatch.setattr(asyncio,'create_subprocess_exec',create)
    monkeypatch.setattr(document_process,'TIMEOUT',.01)
    monkeypatch.setenv('TANK_KEY','placeholder-private-credential')
    with pytest.raises(TimeoutError):await document_process.extract('inventory.csv',b'private document')
    process.kill.assert_called_once();process.wait.assert_awaited_once()
    assert communicate.await_count==2
    assert 'TANK_KEY' not in create.await_args.kwargs['env']


@pytest.mark.asyncio
@pytest.mark.parametrize('path,method,body',[
    ('/market/overview','POST',{'tenant_id':'00000000-0000-0000-0000-000000000031'}),
    ('/market/ml3/feeds','POST',{'tenant_id':'00000000-0000-0000-0000-000000000031'}),
    ('/market/warnings/read','POST',{'tenant_id':'00000000-0000-0000-0000-000000000031'}),
    ('/market/feeds?tenant_id=00000000-0000-0000-0000-000000000031&region=us-east','GET',None),
    ('/quarantine','GET',None),('/gold/candidates','GET',None),('/market/settings','GET',None),
    ('/jobs','POST',{'tenant_id':'00000000-0000-0000-0000-000000000031','kind':'refresh'})])
async def test_room_routes_refuse_unauthenticated_access_before_storage(monkeypatch,path,method,body):
    import importlib.util
    monkeypatch.setenv('TANK_KEY','placeholder-room-key')
    spec=importlib.util.spec_from_file_location('gate5_auth_room',ROOT/'agents/market_lab/app.py')
    room=importlib.util.module_from_spec(spec);spec.loader.exec_module(room)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=room.app),base_url='http://room') as client:
        response=await client.request(method,path,**({'json':body} if body else {}))
        assert response.status_code==401, response.text
