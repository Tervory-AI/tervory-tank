"""Local fixture page: actual Market Lab view/actions and real Tank.

Only the isolated Next wrapper supplies a local identity, since no Clerk test
access exists. No production auth file is edited. Captions belong in README.
"""
import asyncio
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import time
from uuid import uuid4

from market_docs_proof import ROOT, services, prepare
from test_market_lab_documents import report_pdf

WORKSPACE = ROOT / 'workspace'


def next_app(folder):
    def write(name, value):
        path = folder / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(value)
    (folder / 'node_modules').symlink_to(WORKSPACE / 'node_modules', target_is_directory=True)
    (folder / 'public').symlink_to(WORKSPACE / 'public', target_is_directory=True)
    write('package.json', json.dumps({'private': True, 'dependencies': json.loads((WORKSPACE / 'package.json').read_text())['dependencies']}))
    write('fixture-tenant.ts', 'export async function activeTenant(){return {tenantId:process.env.MARKET_DOCS_TENANT!,userId:"local-owner",orgName:"Harbor Supply"};}')
    write('tsconfig.json', json.dumps({'compilerOptions': {'baseUrl': '.', 'target': 'ES2022', 'module': 'esnext', 'moduleResolution': 'bundler', 'jsx': 'preserve', 'strict': True, 'esModuleInterop': True, 'skipLibCheck': True,
        'paths': {'@/lib/tenant': [str(folder / 'fixture-tenant.ts')], '@/*': [str(WORKSPACE / '*')]}}}))
    write('next.config.mjs', 'export default {experimental:{externalDir:true},devIndicators:false,webpack(config){config.resolve.alias={"@/lib/tenant$":' + json.dumps(str(folder / 'fixture-tenant.ts')) + ',"@":' + json.dumps(str(WORKSPACE)) + ',...config.resolve.alias};return config;}};')
    write('app/layout.tsx', f'''import {{jost, inter, mono}} from {json.dumps(str(WORKSPACE / 'app/fonts'))};
import {json.dumps(str(WORKSPACE / 'app/market-lab/market-lab.css'))};
export default function Layout({{children}}:{{children:React.ReactNode}}){{return <html lang="en" className={{`${{jost.variable}} ${{inter.variable}} ${{mono.variable}}`}}><body style={{{{margin:0}}}}>{{children}}</body></html>}}''')
    write('app/market-lab/page.tsx', '''import {MarketLabView} from "@/app/market-lab/view";
import {loadMarketLab} from "@/app/market-lab/load";
import {loadLabPlugins} from "@/app/market-lab/vault-server";
import {emptyFlags} from "@/app/market-lab/catalog";
import {activeTenant} from "@/lib/tenant";
export const dynamic="force-dynamic";
export const metadata={title:"Market Lab · Tervory"};
async function refresh(){"use server";}
export default async function Page(){const tenant=await activeTenant();return <MarketLabView model={await loadMarketLab(tenant.tenantId)} plugins={await loadLabPlugins()} envKeys={emptyFlags()} refresh={refresh} workspaceName={tenant.orgName}/>;}''')
    for path in ('ask/route.ts', 'files/route.ts'):
        write('app/market-lab/' + path, 'export {POST} from "@/app/market-lab/' + path[:-3] + '";')
    write('app/market-lab/sources/[id]/page.tsx', 'export {default,metadata} from "@/app/market-lab/sources/[id]/page";')
    write('app/market-lab/sources/[id]/not-found.tsx', 'export {default} from "@/app/market-lab/source-not-found";')


def capture(base, output):
    from playwright.sync_api import sync_playwright
    report = {'label': 'local, fixture page', 'identity': 'local Next wrapper; not Clerk proof', 'screenshots': [], 'browser_errors': [], 'external_requests': []}
    with sync_playwright() as p:
        browser = p.chromium.launch(executable_path='/usr/bin/chromium', args=['--no-sandbox'])
        try:
            for width in (1440, 375):
                context = browser.new_context(viewport={'width': width, 'height': 1000})
                def route(request):
                    from urllib.parse import urlsplit
                    if urlsplit(request.request.url).netloc != urlsplit(base).netloc:
                        report['external_requests'].append(urlsplit(request.request.url).hostname)
                        request.abort()
                    else:
                        request.continue_()
                context.route('**/*', route)
                page = context.new_page()
                page.on('pageerror', lambda error: report['browser_errors'].append(str(error)))
                def shot(name):
                    path = f'{name}-{width}.png'
                    page.screenshot(path=str(output / path))
                    report['screenshots'].append(path)
                def plugins():
                    if width < 700:
                        page.get_by_role('button', name='Menu', exact=True).click()
                    page.get_by_role('button', name='Plugins', exact=True).click()
                    page.get_by_role('tab', name='Files', exact=True).click()
                page.goto(base + '/market-lab')
                plugins()
                page.locator('input[type=file]').set_input_files({'name': 'report.pdf', 'mimeType': 'application/pdf', 'buffer': report_pdf()})
                page.get_by_role('link', name='report.pdf', exact=True).wait_for()
                assert 'Learned' in page.locator('.ml-prow').filter(has_text='report.pdf').inner_text()
                shot('uploaded')
                page.keyboard.press('Escape')
                page.get_by_role('textbox', name='Ask Market Lab', exact=True).fill('What was warehouse inventory?')
                page.get_by_role('button', name='Send', exact=True).click()
                citation = page.locator('.ml-ref').filter(has_text='report.pdf · Page 2').get_by_role('link', name='Open stored source')
                citation.wait_for()
                page.locator('.ml-chat').scroll_into_view_if_needed()
                shot('answer')
                href = citation.get_attribute('href')
                page.goto(base + href)
                assert page.title() == 'Market Lab · Tervory'
                assert page.locator(':target').inner_text().startswith('Page 2')
                shot('source')
                page.goto(base + '/market-lab')
                plugins()
                page.locator('.ml-prow').filter(has_text='report.pdf').get_by_role('button', name='Remove', exact=True).click()
                page.get_by_role('link', name='report.pdf', exact=True).wait_for(state='detached')
                shot('deleted')
                page.keyboard.press('Escape')
                page.get_by_role('textbox', name='Ask Market Lab', exact=True).fill('What was warehouse inventory?')
                page.get_by_role('button', name='Send', exact=True).click()
                page.get_by_text('No stored data matches this question', exact=True).wait_for()
                page.locator('.ml-chat').scroll_into_view_if_needed()
                shot('after-delete')
                context.close()
        finally:
            browser.close()
    assert not report['browser_errors'], report['browser_errors']
    (output / 'browser.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report, indent=2))


def main():
    output = Path(sys.argv[1]).resolve()
    with services(output) as env, tempfile.TemporaryDirectory(prefix='market-docs-web-') as temp:
        tenant, other = str(uuid4()), str(uuid4())
        asyncio.run(prepare(tenant, other))
        folder = Path(temp)
        next_app(folder)
        env.update(MARKET_DOCS_TENANT=tenant, NEXT_TELEMETRY_DISABLED='1')
        port = 3053
        with (output / 'next.log').open('w') as log:
            web = subprocess.Popen(['node', str(WORKSPACE / 'node_modules/next/dist/bin/next'), 'dev', '--hostname', '127.0.0.1', '--port', str(port)], cwd=folder, env=env, stdout=log, stderr=log)
            try:
                from urllib.request import ProxyHandler, build_opener
                opener = build_opener(ProxyHandler({}))
                deadline = time.monotonic() + 60
                while time.monotonic() < deadline:
                    try:
                        opener.open(f'http://127.0.0.1:{port}/market-lab', timeout=5).close()
                        break
                    except OSError:
                        time.sleep(.2)
                capture(f'http://127.0.0.1:{port}', output)
            finally:
                web.terminate()
                web.wait(timeout=10)


if __name__ == '__main__':
    main()
