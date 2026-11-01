"""Real Tank and Postgres. Only external R2 is local test storage.

No Tank object, route, auth dependency, pool or HTTP client is replaced.
"""
from __future__ import annotations

import asyncio
import base64
import http.client
import json
import os
from pathlib import Path
import secrets
import subprocess
import sys
import threading
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlsplit, parse_qsl
from uuid import UUID, uuid4

import asyncpg
import httpx

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / 'agents/market_lab'), str(ROOT / 'agents/_chassis'), str(ROOT / 'tests')]
from fixture_proof.server import database_url, free_port, wait_ready
from fixture_proof.boot_tank import verify_imported_cases
from test_market_lab_documents import report_pdf, spreadsheet


@contextmanager
def services(output):
    database_url()
    output.mkdir(parents=True, exist_ok=True)
    room_ports = {room: free_port() for room in ('market_lab', 'base')}
    children = []
    class Corridor(BaseHTTPRequestHandler):
        def log_message(self, *_args):
            pass
        def forward(self):
            dest = urlsplit(self.path)
            room = next((room for room in room_ports if dest.netloc == f'agent-{room.replace("_", "-")}:8000'), None)
            if dest.scheme != 'http' or room is None or not dest.path.startswith(('/market/', '/storage/')):
                self.send_error(502)
                return
            connection = http.client.HTTPConnection('127.0.0.1', room_ports[room], timeout=120)
            data = self.rfile.read(int(self.headers.get('content-length', 0)))
            try:
                connection.request(self.command, dest.path + ('?' + dest.query if dest.query else ''), data,
                    {'content-type': self.headers.get('content-type', 'application/octet-stream'), 'x-tank-key': self.headers.get('x-tank-key', '')})
                reply = connection.getresponse()
                result = reply.read()
                if reply.status >= 400:  # Tank turns room errors into a bare 503; keep the room's answer.
                    print(f'room {room} {self.command} {dest.path} -> {reply.status} {result[:500]!r}', flush=True)
                self.send_response(reply.status)
                self.send_header('Content-Type', reply.getheader('content-type', 'application/json'))
                self.send_header('Content-Length', str(len(result)))
                self.end_headers()
                self.wfile.write(result)
            finally:
                connection.close()
        do_POST = do_PUT = do_GET = do_DELETE = forward
    proxy = ThreadingHTTPServer(('127.0.0.1', 0), Corridor)
    thread = threading.Thread(target=proxy.serve_forever, daemon=True)
    thread.start()
    port = free_port()
    env = {k: v for k, v in os.environ.items() if not k.startswith(('R2_', 'TANK_KEY_', 'CLERK_', 'NEXT_PUBLIC_CLERK_'))}
    env.update(TANK_API_KEY='placeholder-market-docs-api-key', TANK_KEY_MARKET_LAB=secrets.token_hex(32), TANK_KEY_BASE=secrets.token_hex(32),
        TANK_VAULT_KEY=base64.urlsafe_b64encode(secrets.token_bytes(32)).decode(), LITELLM_MASTER_KEY=secrets.token_hex(32),
        TANK_REGION='us-east', TERVORY_ADMIN_USER_IDS='', REDIS_URL='redis://127.0.0.1:1/0',
        TANK_URL=f'http://127.0.0.1:{port}', MARKET_DOCS_PROOF_BUCKET=str(output / 'bucket'),
        PYTHONPATH=os.pathsep.join(str(ROOT / path) for path in ('tank', 'agents/market_lab', 'agents/_chassis', 'tests')))
    with (output / 'services.log').open('w+') as log:
        try:
            for room, room_port in room_ports.items():
                room_env = {**env, 'AGENT_NAME': room, 'TANK_KEY': env[f'TANK_KEY_{room.upper()}'],
                    'R2_ACCOUNT_ID': secrets.token_hex(16), f'R2_ACCESS_KEY_ID_{room.upper()}': secrets.token_hex(16), f'R2_SECRET_ACCESS_KEY_{room.upper()}': secrets.token_hex(32)}
                child = subprocess.Popen([sys.executable, '-m', 'uvicorn', 'market_docs_room:app', '--host', '127.0.0.1', '--port', str(room_port), '--lifespan', 'off', '--no-access-log'],
                    cwd=ROOT, env=room_env, stdout=log, stderr=log)
                children.append(child)
                wait_ready(f'http://127.0.0.1:{room_port}/openapi.json', child)
            tank_env = {**env, 'HTTP_PROXY': f'http://127.0.0.1:{proxy.server_port}', 'http_proxy': f'http://127.0.0.1:{proxy.server_port}',
                        'NO_PROXY': '127.0.0.1,localhost', 'no_proxy': '127.0.0.1,localhost'}
            child = subprocess.Popen([sys.executable, '-m', 'uvicorn', 'main:app', '--host', '127.0.0.1', '--port', str(port), '--no-access-log'],
                    cwd=ROOT / 'tank', env=tank_env, stdout=log, stderr=log)
            children.append(child)
            wait_ready(env['TANK_URL'] + '/health', child)
            asyncio.run(verify_imported_cases())
            yield env
        except Exception:
            log.flush()
            print((output / 'services.log').read_text())
            raise
        finally:
            for child in reversed(children):
                child.terminate()
                try:
                    child.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    child.kill()
                    child.wait()
            proxy.shutdown()
            proxy.server_close()
            thread.join(timeout=2)


async def prepare(owner, other):
    from core.ledger import PostgresLedger
    from core.jobs import perform_refresh
    from chassis.db import ensure_schema
    conn = await asyncpg.connect(database_url())
    try:
        # The room runs with --lifespan off, so do its startup step here (chassis/app.py):
        # the jobs and schedules tables. Without it the links PUT failed whenever no other
        # Market Lab proof had created them in this database first.
        await ensure_schema(conn, 'market_lab')
        ledger = PostgresLedger(conn)
        await ledger.apply_schema()
        await ledger.apply_schema()
        for tenant in (owner, other):
            for room in ('market_lab', 'base'):
                await conn.execute('INSERT INTO tank.tenant_squad(tenant_id,agent,enabled_by) VALUES($1,$2,$3)', UUID(tenant), room, 'local-owner')
        job = await perform_refresh(tenant_id=owner, engine='ffl', ledger=ledger, fixtures=str(ROOT / 'tests/fixtures/feeds'))
        return {'job': 'refresh', 'sources_with_rows': sum(r['rows'] > 0 for r in job['feeds'])}
    finally:
        await conn.close()


def check(env, output):
    owner, other, denied = (str(uuid4()) for _ in range(3))
    job = asyncio.run(prepare(owner, other))
    with httpx.Client(base_url=env['TANK_URL'], trust_env=False, timeout=120) as client:
        def vault(method, suffix, *, tenant=owner, room='market_lab', value=None, files=None):
            name = 'lab.vault' if room == 'market_lab' else room + '.vault'
            headers = {'x-tank-key': env['TANK_API_KEY'], 'x-tervory-user': 'local-owner', 'x-tervory-squad': room}
            kwargs = {'headers': headers}
            if value is not None:
                kwargs['json'] = {'tenant_id': tenant, **value}
            else:
                kwargs['params'] = {'tenant_id': tenant, **dict(parse_qsl(urlsplit(suffix).query))}
            if files:
                kwargs['files'] = files
            return client.request(method, f'/v1/vaults/{name}/{suffix}', **kwargs)
        def listing(tenant=owner, room='market_lab'):
            response = vault('GET', 'plugins', tenant=tenant, room=room)
            assert response.status_code == 200, response.text
            return response.json()
        def ask(tenant=owner, operation='ask', **fields):
            return client.post('/v1/market-lab/' + operation, json={'tenant_id': tenant, **fields}, headers={'x-tank-key': env['TANK_API_KEY']})
        assert vault('GET', 'plugins', tenant=denied).status_code == 403
        assert client.get(f'/v1/vaults/lab.vault/plugins?tenant_id={owner}').status_code == 401
        wrong = client.get(f'/v1/vaults/lab.vault/plugins?tenant_id={owner}', headers={'x-tank-key': env['TANK_API_KEY'], 'x-tervory-user': 'local-owner', 'x-tervory-squad': 'base'})
        assert wrong.status_code == 403
        value = secrets.token_hex(32)
        assert vault('POST', 'secrets', value={'name': 'REPORT_KEY', 'purpose': 'Reports', 'value': value}).status_code == 200
        assert value not in json.dumps(listing())
        async def sealed_record():
            conn = await asyncpg.connect(database_url())
            try:
                row = await conn.fetchrow("SELECT sealed, metadata FROM tank.vault_items WHERE tenant_id=$1 AND vault='lab.vault' AND kind='secrets' AND name='REPORT_KEY'", UUID(owner))
                assert row['sealed'] and value not in row['sealed'] and value not in row['metadata']
            finally:
                await conn.close()
        asyncio.run(sealed_record())
        assert vault('POST', 'secrets/resolve', value={'name': 'REPORT_KEY'}).json() == {'found': True, 'value': value}
        assert vault('POST', 'secrets/resolve', tenant=other, value={'name': 'REPORT_KEY'}).json() == {'found': False}
        added = vault('POST', 'links', value={'url': 'https://example.com/reports', 'label': 'Reports', 'frequency': 'weekly'})
        assert added.status_code == 200, added.text
        added = vault('POST', 'connections', value={'name': 'Reports', 'server_url': 'https://example.com/connect', 'auth_type': 'token', 'token': value})
        assert added.status_code == 200, added.text
        assert value not in json.dumps(listing())
        assert listing(other)['connections'] == listing(other)['links'] == listing(other)['secrets'] == []
        for kind in ('links', 'connections'):
            ident = listing()[kind][0]['id']
            assert vault('DELETE', f'{kind}/{ident}', tenant=other).status_code == 404
            assert ident in {str(item['id']) for item in listing()[kind]}
            assert vault('DELETE', f'{kind}/{ident}').status_code == 200
        # A link saved before #421 moved links into the room still sits in tank.vault_items (never
        # migrated). The listing shows it, so its owner must be able to delete it; others get 404.
        legacy = str(uuid4())
        async def legacy_rows(insert=False):
            conn = await asyncpg.connect(database_url())
            try:
                if insert:
                    await conn.execute("INSERT INTO tank.vault_items(tenant_id,vault,kind,name,metadata) VALUES($1,'lab.vault','links',$2,$3::jsonb)", UUID(owner), legacy,
                        json.dumps({'id': legacy, 'url': 'https://example.com/old', 'label': 'Old', 'frequency': 'weekly', 'last_checked': None, 'status': 'not_checked'}))
                return await conn.fetchval("SELECT count(*) FROM tank.vault_items WHERE tenant_id=$1 AND vault='lab.vault' AND kind='links' AND name=$2", UUID(owner), legacy)
            finally:
                await conn.close()
        assert asyncio.run(legacy_rows(insert=True)) == 1
        assert legacy in {str(item['id']) for item in listing()['links']}
        assert vault('DELETE', f'links/{legacy}', tenant=other).status_code == 404
        assert asyncio.run(legacy_rows()) == 1
        assert vault('DELETE', f'links/{legacy}').status_code == 200
        assert asyncio.run(legacy_rows()) == 0
        assert legacy not in {str(item['id']) for item in listing()['links']}
        assert vault('DELETE', f'links/{legacy}').status_code == 404
        assert vault('DELETE', f'links/{uuid4()}').status_code == 404
        assert vault('DELETE', 'secrets?name=REPORT_KEY').status_code == 200  # The client contract puts the name in the query.
        upload = vault('POST', 'files', files=[('file', ('report.pdf', report_pdf(), 'application/pdf'))])
        assert upload.status_code == 200, upload.text
        file = listing()['files'][0]
        assert file['status'] == 'learned' and file['pages'] == 2
        assert listing(other)['files'] == []
        async def grant(enabled):
            conn = await asyncpg.connect(database_url())
            try:
                if enabled:
                    await conn.execute("INSERT INTO tank.tenant_squad(tenant_id,agent,enabled_by) VALUES($1,'market_lab','local-owner')", UUID(owner))
                else:
                    await conn.execute("DELETE FROM tank.tenant_squad WHERE tenant_id=$1 AND agent='market_lab'", UUID(owner))
            finally:
                await conn.close()
        asyncio.run(grant(False))
        assert vault('GET', 'plugins').status_code == 403
        assert vault('DELETE', 'files/' + file['id']).status_code == 403
        asyncio.run(grant(True))
        response = ask(question='What was warehouse inventory?')
        assert response.status_code == 200, response.text
        fact = response.json()['facts'][0]
        assert fact['name'] == 'report.pdf · Page 2' and '14474' in fact['text']
        doc = ask(operation='document', document_id=file['id'], row=1).json()
        assert doc['passages'][1]['page'] == 2
        assert ask(other, question='warehouse inventory').json()['facts'] == []
        assert ask(other, operation='document', document_id=file['id']).status_code == 404
        assert vault('DELETE', 'files/' + file['id'], tenant=other).status_code == 404
        assert vault('DELETE', 'files/' + file['id']).status_code == 200
        assert ask(question='warehouse inventory').json()['facts'] == []
        assert ask(operation='document', document_id=file['id']).status_code == 404
        assert not (output / 'bucket/tervory-market-lab/us-east' / owner / 'uploads' / file['id']).exists()
        assert vault('POST', 'files', files=[('file', ('broken.pdf', b'bad pdf', 'application/pdf'))]).status_code == 200
        broken = listing()['files'][0]
        assert broken['status'] == 'failed' and broken['reason']
        assert vault('DELETE', 'files/' + broken['id']).status_code == 200
        async def stored_points(ident):
            conn = await asyncpg.connect(database_url())
            try:
                return await conn.fetchval('''SELECT count(*) FROM agent_market_lab.points p
                    JOIN agent_market_lab.series s ON p.series_id=s.id WHERE s.tenant_id=$1 AND s.source=$2''', UUID(owner), 'upload:' + ident)
            finally:
                await conn.close()
        rows = [['date', 'value', 'unit', 'series'], ['2026-09-01', '100', 'cartons', 'warehouse'], ['2026-09-08', '110', 'cartons', 'warehouse']]
        for name, data, mime in [('history.csv', '\n'.join(','.join(row) for row in rows).encode(), 'text/csv'), ('history.xlsx', spreadsheet(rows), 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')]:
            assert vault('POST', 'files', files=[('file', (name, data, mime))]).status_code == 200
            meta = listing()['files'][0]
            assert meta['status'] == 'learned' and meta['rows'] == 2
            assert ask(question='warehouse').json()['facts']
            assert asyncio.run(stored_points(meta['id'])) == 2
            assert vault('DELETE', 'files/' + meta['id']).status_code == 200
            assert not ask(question='warehouse').json()['facts']
            assert asyncio.run(stored_points(meta['id'])) == 0
        assert vault('POST', 'files', room='base', files=[('file', ('records.csv', b'one,two\n1,2', 'text/csv'))]).status_code == 200
        base = listing(room='base')['files'][0]
        assert (output / 'bucket/tervory-base/us-east' / owner / 'uploads' / base['id']).exists()
        assert listing()['files'] == []
        assert vault('DELETE', 'files/' + base['id'], room='base').status_code == 200
    async def calls():
        conn = await asyncpg.connect(database_url())
        try:
            return await conn.fetchval('SELECT count(*) FROM tank.ledger WHERE tenant_id=$1', UUID(owner))
        finally:
            await conn.close()
    ledger_rows = asyncio.run(calls())
    assert ledger_rows == 0
    result = {**job, 'model_calls': ledger_rows, 'result': 'passed', 'pdf_citation': fact['name'], 'pdf_pages': 2, 'xlsx_and_csv_guarded': True,
              'deletion_removes_answer_and_object': True, 'other_tenant_files_and_answers': 0, 'squad_checks': 'passed',
              'secrets_and_connection_tokens': 'sealed, metadata only', 'storage': 'external R2 transport fixture; real room client'}
    (output / 'job.json').write_text(json.dumps(result, indent=2) + '\n')
    return result


if __name__ == '__main__':
    output = Path(sys.argv[1]).resolve()
    with services(output) as env:
        print(json.dumps(check(env, output), indent=2))
