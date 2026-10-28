"""Capture read-only production components against real local Tank/Postgres.

The temporary Next wrapper supplies a local founder identity, never live auth.
Screenshots are labelled in captions only. No fixture HTML replaces a product.
"""
from __future__ import annotations

import asyncio
import json
import subprocess
import sys
import tempfile
from pathlib import Path
from uuid import UUID, uuid5, NAMESPACE_URL

import asyncpg
import httpx
from server import ROOT, database_url, free_port, services, wait_ready

WORKSPACE = ROOT / 'workspace'
PLATFORM = UUID('00000000-0000-0000-0000-000000000001')


async def batches():
    from core.ledger import PostgresLedger
    conn = await asyncpg.connect(database_url())
    good, orphan, unknown = (str(uuid5(NAMESPACE_URL, 'local-live-page-proof:' + kind)) for kind in ('good', 'orphan', 'unknown'))
    try:
        ledger = PostgresLedger(conn)
        await ledger.apply_schema()
        await conn.execute('DELETE FROM agent_market_lab.batches WHERE tenant_id=$1 AND id=ANY($2::text[])', PLATFORM, [good, orphan, unknown])
        for ident, source, with_series in [(good, 'check_counts', True), (orphan, 'check_counts', False), (unknown, 'unknown_source', True)]:
            series = f'{PLATFORM}:{ident}'
            if with_series:
                await ledger.save_series({'id': series, 'tenant_id': str(PLATFORM), 'source': source,
                    'ref': 'total:AL', 'unit': 'checks', 'engine': 'ffl'})
            await conn.execute('''INSERT INTO agent_market_lab.batches
                (id,tenant_id,series_id,source,fetched_at,region,currency,unit,status,reason)
                VALUES($1,$2,$3,$4,'2026-10-27T00:00:00Z','us-east','none','checks','held','Value differs from earlier data')''',
                ident, PLATFORM, series, source)
    finally:
        await conn.close()
    return good, orphan, unknown


def prepare(folder: Path):
    def write(name, text):
        path = folder / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)
    (folder / 'node_modules').symlink_to(WORKSPACE / 'node_modules', target_is_directory=True)
    (folder / 'public').symlink_to(WORKSPACE / 'public', target_is_directory=True)
    write('package.json', json.dumps({'private': True, 'dependencies': json.loads((WORKSPACE / 'package.json').read_text())['dependencies']}))
    write('identity.ts', 'export async function auth(){return {userId:"proof-owner"};}')
    write('tsconfig.json', json.dumps({'compilerOptions': {'baseUrl': '.', 'target': 'ES2022', 'module': 'esnext', 'moduleResolution': 'bundler', 'jsx': 'preserve', 'strict': True, 'esModuleInterop': True, 'skipLibCheck': True, 'paths': {'@/*': [str(WORKSPACE / '*')]}}}))
    write('next.config.mjs', 'export default {experimental:{externalDir:true},devIndicators:false,webpack(config){config.resolve.alias={"@clerk/nextjs/server$":' + json.dumps(str(folder / 'identity.ts')) + ',"@":' + json.dumps(str(WORKSPACE)) + ',...config.resolve.alias};return config;}};')
    write('app/layout.tsx', f'''import {{jost, inter, mono}} from {json.dumps(str(WORKSPACE / 'app/fonts'))};
export default function Layout({{children}}:{{children:React.ReactNode}}){{return <html lang="en" className={{`${{jost.variable}} ${{inter.variable}} ${{mono.variable}}`}}><body style={{{{margin:0}}}}>{{children}}</body></html>}}''')
    write('app/autumbra/page.tsx', 'export {default} from "@/app/autumbra/page";')
    write('app/admin/autumbra/page.tsx', 'export {default} from "@/app/admin/autumbra/page";')
    write('app/moot/page.tsx', 'export {default} from "@/app/moot/page";')
    write('app/moot/[match]/page.tsx', 'export {default} from "@/app/moot/[match]/page";')
    write('app/market-lab/page.tsx', '''import {QuarantinePanel} from "@/app/market-lab/quarantine-view";
import {loadQuarantine} from "@/app/market-lab/quarantine-server";
import "@/app/market-lab/market-lab.css";
export const dynamic="force-dynamic";
export default async function Page(){const loaded=await loadQuarantine();return <main className="ml ml-source"><div className="ml-body">{loaded ? <QuarantinePanel {...loaded}/> : null}</div></main>;}''')


def capture(base: str, output: Path) -> dict:
    from playwright.sync_api import sync_playwright
    result = {'label': 'local, fixture page', 'screenshots': [], 'browser_errors': [], 'external_requests': []}
    with sync_playwright() as p:
        browser = p.chromium.launch(executable_path='/usr/bin/chromium', args=['--no-sandbox'])
        try:
            for width in (1440, 375):
                context = browser.new_context(viewport={'width': width, 'height': 1000})
                page = context.new_page()
                page.on('pageerror', lambda error: result['browser_errors'].append(str(error)))
                def route(request):
                    if not request.request.url.startswith(base + '/'):
                        result['external_requests'].append(request.request.url.split('/')[2])
                        request.abort()
                    else:
                        request.continue_()
                context.route('**/*', route)
                for name, path in [('quarantine','/market-lab'), ('autumbra','/autumbra'), ('autumbra-unavailable','/admin/autumbra'), ('moot-empty','/moot')]:
                    response = page.goto(base + path)
                    assert response.status == 200
                    text = page.locator('body').inner_text()
                    assert not any(word in text for word in ('Fixture', '[TEST]', 'CVE-2024-0000', 'ThreatPayload', '00000000-0000-0000-0000'))
                    if name == 'quarantine':
                        assert 'Monthly background-check counts by state and type · Alabama' in text
                        assert page.locator('tbody tr').count() == 1
                    elif name == 'autumbra':
                        watch = page.locator('article').filter(has=page.get_by_role('heading', name='Autumbra Watch', exact=True))
                        assert watch.inner_text() == 'Autumbra Watch'
                    elif name == 'autumbra-unavailable':
                        assert 'Room unavailable' in text and 'Shield numbers are unavailable.' in text
                    elif name == 'moot-empty':
                        assert 'No published matches yet.' in text
                    screenshot = f'{name}-{width}.png'
                    page.screenshot(path=str(output / screenshot), full_page=True)
                    result['screenshots'].append(screenshot)
                assert page.goto(base + '/moot/fixture-published').status == 404
                context.close()
        finally:
            browser.close()
    assert not result['browser_errors'], result['browser_errors']
    assert not result['external_requests'], result['external_requests']
    return result


def main():
    output = Path(sys.argv[1]).resolve()
    output.mkdir(parents=True, exist_ok=True)
    with (output / 'tank-startup.txt').open('w') as log, services(free_port(), log=log) as env:
        good, orphan, unknown = asyncio.run(batches())
        with httpx.Client(base_url=env['TANK_URL'], trust_env=False) as client:
            response = client.get('/v1/market/quarantine', headers={'x-tank-key': env['TANK_API_KEY'], 'x-tervory-user': 'proof-owner', 'x-tervory-tenant': str(PLATFORM)})
            assert response.status_code == 200, response.text
            assert [row['id'] for row in response.json()['batches']] == [good]
            assert client.get('/v1/market/quarantine', headers={'x-tank-key': env['TANK_API_KEY']}).status_code == 404
        with tempfile.TemporaryDirectory(prefix='live-page-proof-') as temp:
            folder = Path(temp)
            prepare(folder)
            port = free_port()
            with (output / 'next-server.txt').open('w') as next_log:
                web = subprocess.Popen(['node', str(WORKSPACE / 'node_modules/next/dist/bin/next'), 'dev', '--hostname', '127.0.0.1', '--port', str(port)], cwd=folder, env=env, stdout=next_log, stderr=next_log)
                try:
                    wait_ready(f'http://127.0.0.1:{port}/autumbra', web, timeout=60)
                    result = capture(f'http://127.0.0.1:{port}', output)
                    result.update(real_tank='passed', good_batches=1, skipped_batches=2, refresh_job='completed with saved provider inputs', founder_only='passed', watch_description='empty')
                    log.flush()
                    saved_log = (output / 'tank-startup.txt').read_text()
                    assert orphan in saved_log and 'series reference or engine missing' in saved_log
                    assert unknown in saved_log and 'series source unavailable' in saved_log
                    (output / 'job.json').write_text(json.dumps(result, indent=2) + '\n')
                    print(json.dumps(result, indent=2))
                finally:
                    web.terminate()
                    web.wait(timeout=10)


if __name__ == '__main__':
    main()
