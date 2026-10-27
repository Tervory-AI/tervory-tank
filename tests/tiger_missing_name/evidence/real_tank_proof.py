"""Local, fixture page: real Tank + Tiger worker + Postgres + Chromium.

Run with DATABASE_URL pointing at a disposable local database named
`tiger_name_proof*`. No production credentials, model calls or live stores.
Only the browser's external fetch is replaced by saved HTML. The actual worker
calls Tank's installed price-extraction skill and persists through PgStore.
"""
from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path
import shutil
import sys
import tempfile
import uuid
from urllib.parse import urlsplit

import asyncpg
from fastapi import FastAPI
import httpx
from playwright.async_api import async_playwright
import uvicorn

ROOT = Path(__file__).resolve().parents[3]
sys.path[:0] = [str(ROOT / 'tests'), str(ROOT / 'tank')]
from tiger_works.evidence.local_proof import CLIENT, SERVER, browser, free_port, ready  # noqa: E402

URL = 'https://8.8.8.8/products/desk-lamp'
TENANT_A = str(uuid.uuid5(uuid.UUID('7f3b1c2e-9a4d-4c1e-8f2a-5b6d7e8f9a0b'), 'org_tiger_name_fixture'))
TENANT_B = '22222222-2222-2222-2222-222222222222'
FIXTURES = ROOT / 'tests/tiger_missing_name/fixtures'


async def main():
    database = os.environ.get('DATABASE_URL', '')
    parsed = urlsplit(database)
    assert parsed.hostname in {'localhost', '127.0.0.1'} and parsed.path.startswith('/tiger_name_proof'), 'Use an isolated local tiger_name_proof database'
    output = Path(os.environ.get('TIGER_NAME_PROOF_DIR', ROOT / 'tests/tiger_missing_name/evidence/proof'))
    output.mkdir(parents=True, exist_ok=True)
    tank_port, tiger_port, browser_port, workspace_port = (free_port() for _ in range(4))
    tank_url = f'http://127.0.0.1:{tank_port}'
    tiger_url = f'http://127.0.0.1:{tiger_port}'
    origin = f'http://localhost:{workspace_port}'
    key, agent_key = 'local-fixture-workspace', 'local-fixture-tiger'
    processes, handles = [], []
    server = None
    server_task = None
    conn = None
    os.environ['ACCESS_ROOM'] = 'tiger'
    env = {**os.environ, 'DATABASE_URL': database, 'TANK_API_KEY': key, 'TANK_KEY_TIGER': agent_key,
           'TANK_KEY': agent_key, 'TANK_URL': tank_url, 'LITELLM_MASTER_KEY': 'local-fixture',
           'LITELLM_URL': 'http://127.0.0.1:1', 'REDIS_URL': 'redis://127.0.0.1:1',
           'TANK_REGION': 'us-east', 'DOMAIN_INTERVAL_S': '0', 'AGENT_NAME': 'tiger',
           'TIGER_URL': f'http://127.0.0.1:{browser_port}', 'NEXT_TELEMETRY_DISABLED': '1',
           'NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY': 'pk_test_ZHVtbXkuY2xlcmsuYWNjb3VudHMuZGV2JA==',
           'CLERK_SECRET_KEY': 'sk_test_dummy', 'NO_PROXY': os.environ.get('NO_PROXY', '') + ',localhost,127.0.0.1'}
    async def start(name, args, cwd, extra=None):
        handle = (output / f'{name}.log').open('w'); handles.append(handle)
        process = await asyncio.create_subprocess_exec(*args, cwd=cwd, env={**env, **(extra or {})}, stdout=handle, stderr=asyncio.subprocess.STDOUT)
        processes.append(process)
        return process
    try:
        async with async_playwright() as pw:
            chrome = await pw.chromium.launch(executable_path=os.environ.get('READ1_CHROMIUM_EXECUTABLE', '/usr/bin/chromium'), args=['--no-sandbox'])
            reader = await chrome.new_context(java_script_enabled=False)
            await reader.route('**/*', lambda route: route.abort())
            read_page = await reader.new_page()
            fixture = {'html': (FIXTURES / 'no-name.html').read_text()}
            service = FastAPI()
            @service.post('/render')
            async def render(body: dict):
                assert body.get('price_reader') is True and body['url'] == URL
                await read_page.set_content(fixture['html'])
                return await browser.public_result(read_page, {'ok': True, 'url': URL}, fixture['html'],
                    output, str(uuid.uuid4()), price_reader=True)
            server = uvicorn.Server(uvicorn.Config(service, host='127.0.0.1', port=browser_port, log_level='warning'))
            server_task = asyncio.create_task(server.serve())
            with tempfile.TemporaryDirectory(prefix='tiger-name-', dir='/tmp') as temp:
                temp = Path(temp)
                # This substitutes only the room's local deployment address.
                # Tank's app, startup/schema, HTTP proxy routes and skill code are unchanged.
                bootstrap = temp / 'tank_local.py'
                bootstrap.write_text(f'import main\nmain.TIGER_AGENT_URL = {tiger_url!r}\napp = main.app\n')
                tank = await start('tank', [sys.executable, '-m', 'uvicorn', 'tank_local:app', '--host', '127.0.0.1', '--port', str(tank_port)], ROOT,
                                   {'PYTHONPATH': f'{temp}:{ROOT / "tank"}'})
                await ready(tank_url + '/health', tank)
                conn = await asyncpg.connect(database)
                await conn.execute("UPDATE tank.skills SET state='approved' WHERE id='tiger.price_extract' AND version='1.1.0'")
                tiger = await start('tiger', [sys.executable, '-m', 'uvicorn', 'app:app', '--host', '127.0.0.1', '--port', str(tiger_port)], ROOT / 'agents/tiger',
                                    {'PYTHONPATH': str(ROOT / 'agents/_chassis'), 'DATA_DIR': str(temp / 'data')})
                await ready(tiger_url + '/health', tiger)
                async with httpx.AsyncClient(base_url=tank_url, headers={'X-Tank-Key': key}, trust_env=False, timeout=40) as client:
                    watches = {}
                    for tenant in (TENANT_A, TENANT_B):
                        response = await client.post('/v1/tiger/watchlist', json={'tenant_id': tenant, 'url': URL, 'label': '', 'every': '1h'})
                        assert response.status_code == 201, response.text
                        watches[tenant] = response.json()
                        # Explicit fixture steps use the same real queue/worker, without
                        # a minute-boundary dispatch adding an extra reading mid-proof.
                        await conn.execute('UPDATE agent_tiger.schedules SET enabled=false WHERE tenant_id=$1', uuid.UUID(tenant))
                    async def check(tenant, filename, replace=None):
                        html = (FIXTURES / filename).read_text()
                        for before, after in replace or []:
                            html = html.replace(before, after)
                        fixture['html'] = html
                        queued = await client.post(tiger_url + '/jobs', json={'tenant_id': tenant, 'kind': 'check', 'input': {'url': URL}})
                        assert queued.status_code == 201, queued.text
                        job_id = queued.json()['id']
                        for _ in range(160):
                            job = (await client.get(tiger_url + '/jobs/' + job_id, params={'tenant_id': tenant})).json()
                            if job.get('status') == 'done': return job['result']
                            assert job.get('status') != 'failed' and not job.get('error'), job
                            await asyncio.sleep(.25)
                        raise AssertionError(f'Fixture job did not finish: {job}')
                    async def rows(tenant, kind):
                        result = await client.get('/v1/tiger/' + kind, params={'tenant_id': tenant, 'url': URL})
                        assert result.status_code == 200, result.text
                        return result.json()[kind]
                    first = await check(TENANT_A, 'no-name.html')
                    assert first['observation']['issue'] == 'missing_name' and first['price'] is None and first['alerts'] == []
                    assert first['observation']['last_product_name'] is None
                    print('PASS nameless first check: issue=missing_name; price=null; alerts=0; URL and attempt time retained', flush=True)

                    # Workspace uses the actual Tank process. Clerk is replaced only
                    # in this throwaway copy; repository authentication is unchanged.
                    local = temp / 'workspace'
                    shutil.copytree(ROOT / 'workspace', local, ignore=shutil.ignore_patterns('node_modules', '.next', '.env*', '*.tsbuildinfo'))
                    (local / 'node_modules').symlink_to(ROOT / 'workspace/node_modules', target_is_directory=True)
                    (local / 'fixture-clerk-client.js').write_text(CLIENT)
                    (local / 'fixture-clerk-server.js').write_text(SERVER.replace('org_tiger_local_fixture', 'org_tiger_name_fixture'))
                    (local / 'next.config.ts').write_text('import path from "node:path"; export default {devIndicators:false,webpack(config){config.resolve.alias["@clerk/nextjs$"]=path.resolve("fixture-clerk-client.js");config.resolve.alias["@clerk/nextjs/server$"]=path.resolve("fixture-clerk-server.js");return config;}};')
                    ui = await start('workspace', ['node', str(local / 'node_modules/next/dist/bin/next'), 'dev', '--hostname', 'localhost', '--port', str(workspace_port)], local)
                    await ready(origin + '/tiger', ui)
                    context = await chrome.new_context(viewport={'width': 1440, 'height': 1100})
                    await context.route('**/*', lambda route: route.continue_() if route.request.url.startswith(origin) else route.abort())
                    page = await context.new_page()
                    reason = "Not checked — the product name wasn't found on the page"
                    async def screen(filename, expected_name):
                        await page.goto(origin + '/tiger', wait_until='networkidle')
                        assert await page.get_by_text(reason, exact=True).count() >= 1
                        row = page.locator('.overview-table tbody tr').first
                        assert await row.locator('td').nth(0).inner_text() == expected_name
                        assert await row.locator('td').nth(2).inner_text() == ''
                        assert await row.locator('td time').get_attribute('datetime')
                        assert await row.locator(f'a[href="{URL}"]').count() >= 1
                        assert 'Untitled page' not in await page.locator('body').inner_text()
                        await page.screenshot(path=str(output / filename), full_page=True)
                        await page.get_by_role('button', name='Watch list', exact=True).click()
                        assert await page.get_by_text(reason, exact=True).count() >= 1
                        await page.get_by_role('button', name='History', exact=True).click()
                        assert await page.get_by_text(reason, exact=True).count() >= 1
                    await screen('first-nameless.png', URL)
                    print('PASS Workspace: URL identifies nameless product; exact status, attempt time and link; no price or placeholder on Overview, Watch list or History', flush=True)
                    named = await check(TENANT_A, 'named.html')
                    assert named['observation']['product_name'] == 'Desk lamp' and named['price'] == '24.00'
                    changed = await check(TENANT_A, 'named.html', [('24.00', '23.00')])
                    assert len(changed['alerts']) == 1
                    missing = await check(TENANT_A, 'no-name.html')
                    assert missing['observation']['last_product_name'] == 'Desk lamp' and missing['price'] is None and not missing['alerts']
                    assert len(await rows(TENANT_A, 'alerts')) == 1
                    await screen('last-name-retained.png', 'Desk lamp')
                    print('PASS later nameless check: last name=Desk lamp; price=null; no new alert; Workspace retains name with current failure status', flush=True)
                    isolated = await check(TENANT_B, 'no-name.html')
                    assert isolated['observation']['last_product_name'] is None
                    assert len(await rows(TENANT_B, 'observations')) == 1 and not await rows(TENANT_B, 'alerts')
                    assert len(await rows(TENANT_A, 'observations')) == 4
                    print('PASS two tenants: same URL; tenant B has no name or alerts from tenant A', flush=True)
                    currency = await check(TENANT_A, 'no-currency.html')
                    assert currency['observation']['issue'] == 'missing_currency' and currency['price'] is None and not currency['alerts']
                    print('PASS missing currency: price=null; no guessed currency; no new alert', flush=True)
                    recovered = await check(TENANT_A, 'named.html', [('24.00', '22.00')])
                    assert recovered['price'] == '22.00' and len(recovered['alerts']) == 1
                    assert recovered['alerts'][0]['before'] == '23.00'
                    await page.goto(origin + '/tiger', wait_until='networkidle')
                    assert '$22.00' in await page.locator('body').inner_text()
                    print('PASS recovery: Desk lamp at USD 22.00; one confirmed alert compares the last complete price, USD 23.00', flush=True)
                    (output / 'observations.json').write_text(json.dumps({'label': 'local, fixture page', 'tenant_a': await rows(TENANT_A, 'observations'), 'tenant_b': await rows(TENANT_B, 'observations')}, indent=2))
                    print('PASS real job: actual Tank app, installed skill, Tiger queue/worker, PgStore, Chromium and Workspace; no model or external store call', flush=True)
                    await chrome.close()
    finally:
        for process in reversed(processes):
            if process.returncode is None:
                process.terminate()
                try: await asyncio.wait_for(process.wait(), 10)
                except TimeoutError: process.kill(); await process.wait()
        if conn: await conn.close()
        if server: server.should_exit = True
        if server_task: await server_task
        for handle in handles: handle.close()


if __name__ == '__main__':
    asyncio.run(main())
