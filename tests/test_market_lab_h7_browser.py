"""Local fixture pages use the real H7 components; no production auth changes."""
import asyncio
import json
import os
from pathlib import Path
import socket
import subprocess
import signal

import httpx
import pytest

ROOT = Path(__file__).resolve().parents[1]
WORKSPACE = ROOT / 'workspace'


def wrapper(folder):
    folder.mkdir()
    (folder / 'node_modules').symlink_to(WORKSPACE / 'node_modules', target_is_directory=True)
    (folder / 'public').symlink_to(WORKSPACE / 'public', target_is_directory=True)
    def write(name, text):
        path = folder / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)
    write('package.json', json.dumps({'private': True, 'dependencies': json.loads((WORKSPACE / 'package.json').read_text())['dependencies']}))
    write('tsconfig.json', json.dumps({'compilerOptions': {'target': 'ES2022', 'module': 'esnext', 'moduleResolution': 'bundler', 'jsx': 'preserve', 'strict': True, 'esModuleInterop': True, 'skipLibCheck': True}}))
    # Only the isolated visual fixture doubles the shared native identity widget.
    # The production page uses the authenticated Workspace sign-in provider.
    write('fixture-signin.tsx', 'export function OrganisationSwitcher(){return <button aria-label="Business">⌄</button>}')
    write('next.config.mjs', 'export default {experimental:{externalDir:true,cpus:1},devIndicators:false,webpack(config){config.resolve.alias={...config.resolve.alias,"../trigger-signin-provider$":' +
          json.dumps(str(folder / 'fixture-signin.tsx')) + '};return config;}};')
    write('app/layout.tsx', f'''import {{inter}} from {json.dumps(str(WORKSPACE / 'app/fonts'))};
import {json.dumps(str(WORKSPACE / 'app/market-lab/h7.css'))};
export default function Layout({{children}}:{{children:React.ReactNode}}){{return <html lang="en" className={{inter.variable}}><body style={{{{margin:0}}}}>{{children}}</body></html>}}''')
    # Saved fixture shape is the exact route contract proved by test_market_lab_h7.
    brief = {'report_id': '00000000-0000-0000-0000-000000000041', 'name': 'placeholder saved brief',
             'summary': 'placeholder inventory claim', 'made_at': '2026-11-04T00:00:00Z', 'status': 'email:sent / webhook:held',
             'deliveries': [{'channel': 'email', 'status': 'sent'}, {'channel': 'webhook', 'status': 'held'}],
             'sources': [{'claim': 'placeholder inventory claim', 'date': '2026-11-03',
                          'url': 'https://placeholder.example/source',
                          'stored_href': '/market-lab/sources/00000000-0000-0000-0000-000000000051?row=0#passage-0'},
                         {'claim': 'placeholder removed source', 'url': 'https://placeholder.example/removed', 'stored_href': None}],
             'signals': [], 'history': []}
    curves = [{'kind': 'placeholder_pair', 'feed': 'placeholder_feed', 'horizon_seconds': days * 86400,
               'count': 2, 'mean_confidence': probability, 'realised_rate': rate, 'hits': hits, 'misses': 2-hits,
               'bins': [{'lower': 0, 'upper': 1, 'count': 2, 'mean_confidence': probability, 'realised_rate': rate}]}
              for days, probability, rate, hits in ((30, .75, .5, 1), (7, .25, 1, 2))]
    write('data.json', json.dumps({'brief': brief, 'curves': curves}))
    write('app/page.tsx', f'''import {{H7Shell}} from {json.dumps(str(WORKSPACE / 'app/market-lab/h7-shell'))};
import {{BriefView,CalibrationView}} from {json.dumps(str(WORKSPACE / 'app/market-lab/h7-view'))};
import data from '../data.json';
export default async function Page({{searchParams}}:{{searchParams:Promise<{{screen?:string,state?:string}}>}}){{
const p=await searchParams;const state=p.state==='empty'||p.state==='error'||p.state==='loading'?p.state:'ready';
return <H7Shell>{{p.screen==='calibration'?<CalibrationView value={{state==='ready'?{{state,data:data.curves}}:{{state}}}}/>:<BriefView value={{state==='ready'?{{state,data:data.brief}}:{{state}}}}/>}}</H7Shell>}}''')
    write('app/market-lab/sources/[id]/page.tsx', 'export default function Source(){return <main id="passage-0">placeholder stored passage</main>}')


@pytest.mark.asyncio
async def test_both_pages_states_menu_and_cohort_selection(real_chromium, tmp_path):
    folder = tmp_path / 'next-app'
    wrapper(folder)
    with socket.socket() as sock:
        sock.bind(('127.0.0.1', 0))
        port = sock.getsockname()[1]
    base = f'http://127.0.0.1:{port}'
    output = Path(os.environ.get('MARKET_LAB_H7_SCREENSHOTS', str(tmp_path / 'screenshots')))
    output.mkdir(parents=True, exist_ok=True)
    with (tmp_path / 'next.log').open('w') as log:
        process = subprocess.Popen(['node', str(WORKSPACE / 'node_modules/next/dist/bin/next'),
            'dev', '--hostname', '127.0.0.1', '--port', str(port)], cwd=folder,
            env={**os.environ, 'NEXT_TELEMETRY_DISABLED': '1',
                 'RAYON_NUM_THREADS': '1', 'UV_THREADPOOL_SIZE': '2'}, stdout=log, stderr=log,
            start_new_session=True)
        try:
            async with httpx.AsyncClient(trust_env=False) as client:
                for _ in range(120):
                    try:
                        if (await client.get(base, timeout=2)).status_code == 200:
                            break
                    except httpx.HTTPError:
                        pass
                    if process.poll() is not None:
                        raise AssertionError((tmp_path / 'next.log').read_text())
                    await asyncio.sleep(.5)
                else:
                    raise AssertionError((tmp_path / 'next.log').read_text())
            errors, external = [], []
            for width in (1440, 375):
                context = await real_chromium.new_context(viewport={'width': width, 'height': 1000})
                async def restrict(route):
                    if route.request.url.startswith(base + '/'):
                        await route.continue_()
                    else:
                        external.append(route.request.url)
                        await route.abort()
                await context.route('**/*', restrict)
                page = await context.new_page()
                page.on('pageerror', lambda error: errors.append(str(error)))
                for screen in ('brief', 'calibration'):
                    for state in ('ready', 'empty', 'loading', 'error'):
                        await page.goto(base + f'/?screen={screen}&state={state}', wait_until='networkidle')
                        await page.evaluate('document.fonts.ready')
                        assert await page.evaluate('document.documentElement.scrollWidth <= innerWidth')
                        assert await page.get_by_role('heading', name='Market Lab', exact=True).count() == 1
                        content = await page.locator('.h7-content').bounding_box()
                        assert content['x'] == (0 if width == 375 else 240)
                        assert await page.locator('.h7-content').evaluate('(element)=>parseFloat(getComputedStyle(element).paddingLeft)') == (24 if width == 375 else 64)
                        if screen == 'brief' and state == 'ready':
                            assert await page.get_by_role('link', name='Open stored source', exact=True).count() == 1
                            assert await page.get_by_role('button', name='Open stored source', exact=True).is_disabled()
                            await page.get_by_role('link', name='Open stored source', exact=True).click()
                            await page.locator('#passage-0').wait_for()
                            assert await page.locator('#passage-0').inner_text() == 'placeholder stored passage'
                            await page.go_back(wait_until='networkidle')
                        if screen == 'calibration' and state == 'ready':
                            dot = page.locator('.h7-plot.mobile img[data-confidence]' if width == 375 else '.h7-plot.desktop img[data-confidence]')
                            assert await dot.get_attribute('data-confidence') == '0.75'
                            plot = page.locator('.h7-plot.mobile' if width == 375 else '.h7-plot.desktop')
                            assert await plot.locator('img').evaluate_all('(images)=>images.every(image=>image.complete && image.naturalWidth>0)')
                            assert await dot.evaluate('(image)=>image.getBoundingClientRect().width') == 8
                            axis = await plot.locator('img[src$="imgAxis1.svg"]').bounding_box()
                            midpoint = await plot.locator('.h7-x-label').nth(1).bounding_box()
                            endpoint = await plot.locator('.h7-x-label').nth(2).bounding_box()
                            assert abs(midpoint['x'] + midpoint['width']/2 - (axis['x'] + axis['width']/2)) < 1
                            assert abs(endpoint['x'] + endpoint['width'] - (axis['x'] + axis['width'])) < 1
                            await page.get_by_role('button', name='placeholder_pair · Horizon: 7 days', exact=True).click()
                            assert await dot.get_attribute('data-confidence') == '0.25'
                            assert await dot.get_attribute('data-actual') == '1'
                            await page.get_by_role('button', name='placeholder_pair · Horizon: 30 days', exact=True).click()
                        await page.screenshot(path=str(output / f'{screen}-{state}-{width}.png'), full_page=True)
                if width == 375:
                    await page.get_by_role('button', name='Menu', exact=True).click()
                    assert await page.locator('#h7-menu').is_visible()
                    await page.keyboard.press('Escape')
                    assert not await page.locator('#h7-menu').is_visible()
                    assert await page.get_by_role('button', name='Menu', exact=True).evaluate('(element)=>element===document.activeElement')
                await context.close()
            assert not errors, errors
            assert not external, external
            (output / 'proof.json').write_text(json.dumps({'label': 'local fixture page', 'widths': [1440,375],
                'screenshots': 16, 'external_requests': external, 'browser_errors': errors}, indent=2))
        finally:
            try:
                os.killpg(process.pid, signal.SIGTERM)
            except ProcessLookupError:
                pass
            try:
                process.wait(timeout=15)
            except subprocess.TimeoutExpired:
                os.killpg(process.pid, signal.SIGKILL)
                process.wait()
