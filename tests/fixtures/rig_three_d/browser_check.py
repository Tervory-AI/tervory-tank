"""Offline packaged-widget proof. Run against the disposable viewer fixture on :8035."""
import json
import os
from pathlib import Path
from urllib.parse import urlsplit

from PIL import Image, ImageChops, ImageStat
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT / 'docs/rig/3d-implementation'
BASE = 'http://127.0.0.1:8035'


def enter(page, terminal=False):
    page.goto(BASE + '/viewer-test')
    page.get_by_placeholder('Search a make, model or part', exact=True).fill('Centre')
    page.get_by_role('button', name='Complete my setup', exact=True).click()
    page.get_by_role('button', name='Open terminal' if terminal else 'Open 3D', exact=True).click()
    page.locator('.rig-3d[data-state=ready]').wait_for()
    page.evaluate('document.fonts.ready')


def compare(page, name, width):
    target = OUT / 'screenshots' / f'{name}-{width}.png'
    reference = Image.open(OUT / 'reference' / f'{name}-{width}.png').convert('RGB')
    reference = reference.crop((0, 56, reference.width, reference.height))  # design review ribbon
    page.screenshot(path=str(target), full_page=True)
    actual = Image.open(target).convert('RGB')
    # Compare unchanged frame scaffold, not the explicitly excluded review shapes,
    # fixture caption, or API product/part names and repriced total.
    regions = [(0, 0, width, 96 if width == 375 else 128),
               (16 if width == 375 else 48, 96 if width == 375 else 128, width - 16 if width == 375 else width - 48, 216 if width == 375 else 272)]
    if name.startswith('07'):
        regions.append((16, 584, 359, 808) if width == 375 else (48, 648, 1008, 872))
        regions.append((16, 832, 359, min(1392, reference.height)) if width == 375 else (1032, 272, 1392, 888))
    else:
        regions.append((16, 564, 359, 740) if width == 375 else (48, 628, 1008, 804))
    results = []
    for region in regions:
        diff = ImageChops.difference(actual.crop(region), reference.crop(region))
        changed = sum(max(pixel) > 24 for pixel in diff.getdata())
        ratio = changed / (diff.width * diff.height)
        mean_error = sum(ImageStat.Stat(diff).mean) / 3
        assert mean_error < 10, (name, width, region, mean_error)
        results.append({'region': region, 'changed_pixel_fraction': ratio, 'mean_channel_error_255': mean_error})
    return results


def main():
    report = {}
    with sync_playwright() as p:
        browser = p.chromium.launch(executable_path=os.environ.get('READ1_CHROMIUM_EXECUTABLE', '/opt/google/chrome/chrome'), args=[
            '--no-sandbox', '--use-gl=angle', '--use-angle=swiftshader', '--enable-unsafe-swiftshader'])
        for width in (1440, 375):
            page = browser.new_page(viewport={'width': width, 'height': 852 if width == 1440 else 1212}, reduced_motion='reduce')
            requests, errors = [], []
            page.on('pageerror', lambda error: errors.append(str(error)))
            page.on('request', lambda request: requests.append(request.url))
            page.route('**/*', lambda route: route.continue_() if urlsplit(route.request.url).hostname == '127.0.0.1' else route.abort())
            page.goto(BASE + '/viewer-test')
            page.get_by_placeholder('Search a make, model or part', exact=True).fill('Centre')
            page.get_by_role('button', name='Complete my setup', exact=True).click()
            assert not any('/3d/assets/' in url or '/3d/widget-entry' in url for url in requests)
            page.get_by_role('button', name='Open 3D', exact=True).click()
            frame = page.locator('.rig-3d[data-state=ready]'); frame.wait_for()
            page.evaluate('document.fonts.ready')
            assert frame.get_attribute('data-models') == '3'
            bounds = page.locator('.rig-3d-viewport').bounding_box()
            assert bounds == ({'x': 16, 'y': 208, 'width': 343, 'height': 300} if width == 375 else {'x': 48, 'y': 272, 'width': 960, 'height': 300})
            assert page.locator('.rig-3d').evaluate('(e)=>e.scrollWidth <= innerWidth')
            assert 'design review only' not in frame.inner_text().lower()
            before = json.loads(frame.get_attribute('data-positions'))
            page.get_by_role('button', name='Exploded view', exact=True).click()
            assert json.loads(frame.get_attribute('data-positions')) != before
            page.get_by_role('button', name='Exploded view', exact=True).click()
            assert json.loads(frame.get_attribute('data-positions')) == before
            page.get_by_role('button', name='Rotate right', exact=True).click()
            page.get_by_role('button', name='Zoom in', exact=True).click()
            report[f'06-ready-{width}'] = compare(page, '06-ready', width)
            page.get_by_role('button', name='Back to setups', exact=True).click()
            assert page.locator('.rig-3d').count() == 0
            # An entitled account without a complete approved assembly never imports the renderer.
            requests.clear()
            page.route('**/v1/rig/3d/assembly', lambda route: route.fulfill(json={'available': False, 'photo': ''}))
            page.get_by_role('button', name='Open 3D', exact=True).click()
            page.locator('.rig-3d[data-state=photos]').wait_for()
            assert not any('/3d/assets/viewer-' in url or '/v1/rig/3d/assets/' in url for url in requests)
            assert not errors, errors
            page.close()
            page = browser.new_page(viewport={'width': width, 'height': 968 if width == 1440 else 1392}, reduced_motion='reduce')
            page.route('**/*', lambda route: route.continue_() if urlsplit(route.request.url).hostname == '127.0.0.1' else route.abort())
            page.clock.install()
            enter(page, terminal=True)
            page.get_by_role('button', name='Full screen', exact=True).click()
            page.wait_for_function('document.fullscreenElement !== null')
            page.evaluate('document.exitFullscreen()')
            page.get_by_role('button', name='Request a quote', exact=True).click()
            page.locator('input[name=name]').fill('')
            page.wait_for_function('''() => {
                const e = document.querySelector('tervory-rig').shadowRoot;
                return !e.querySelector('.contact button[type=submit]').disabled;
            }''')
            assert page.locator('input[name=phone]').is_visible()
            assert not page.locator('input[name=email]').is_visible()
            report[f'07-phone-{width}'] = compare(page, '07-phone', width)
            page.get_by_role('button', name='Email', exact=True).click()
            assert page.locator('input[name=email]').is_visible()
            assert not page.locator('input[name=phone]').is_visible()
            report[f'07-email-{width}'] = compare(page, '07-email', width)
            page.locator('input[name=name]').fill('Offline Fixture')
            page.locator('input[name=email]').fill('fixture@example.test')
            page.context.set_offline(True)
            page.wait_for_function('''() => document.querySelector('tervory-rig').shadowRoot.querySelector('.contact button[type=submit]').disabled''')
            page.context.set_offline(False)
            page.wait_for_function('''() => !document.querySelector('tervory-rig').shadowRoot.querySelector('.contact button[type=submit]').disabled''')
            page.route('**/v1/rig/3d/quote', lambda route: route.fulfill(status=503, json={'error': 'fixture unavailable'}))
            page.get_by_role('button', name='Request a quote', exact=True).click()
            page.get_by_text('The quote could not be confirmed. Reconnect and try again.', exact=True).wait_for()
            report[f'07-error-quote-{width}'] = compare(page, '07-error-quote', width)
            page.unroute('**/v1/rig/3d/quote')
            page.route('**/v1/rig/3d/quote', lambda route: route.fulfill(json={'request_id': 'offline_fixture_receipt'}))
            page.get_by_role('button', name='Request a quote', exact=True).click()
            page.get_by_text('Your quote request was saved. Delivery to the retailer is pending.', exact=True).wait_for()
            assert page.locator('input[name=name]').input_value() == ''
            report[f'07-saved-{width}'] = compare(page, '07-saved', width)
            # Reset refreshes the assembly asynchronously; the old ready state is
            # not evidence that reset finished. Wait for its response and attract state.
            with page.expect_response(lambda response: response.url.endswith('/v1/rig/3d/assembly')) as reset_response:
                page.get_by_role('button', name='Start again', exact=True).last.click()
            assert reset_response.value.ok
            reset_response.value.finished()
            page.locator('.rig-3d[data-state=ready]').wait_for()
            page.wait_for_function('''() => document.querySelector('tervory-rig').shadowRoot.querySelector('.rig-3d-body>h2').textContent === 'Touch the product to explore a setup.' ''')
            assert page.locator('.contact').is_hidden()
            page.get_by_role('button', name='Request a quote', exact=True).click()
            assert page.locator('input[name=name]').input_value() == ''
            assert page.locator('input[name=phone]').input_value() == ''
            page.locator('input[name=name]').fill('Inactivity Fixture')
            page.clock.fast_forward(60_100)
            page.locator('.contact').wait_for(state='hidden')
            assert page.locator('input[name=name]').input_value() == ''
            assert page.locator('.rig-3d-body>h2').inner_text() == 'Touch the product to explore a setup.'
            page.close()
        for failure in ('entitlement', 'expired', 'integrity', 'foreign-url'):
            page = browser.new_page()
            requested = []
            page.on('request', lambda request: requested.append(request.url))
            page.route('**/*', lambda route: route.continue_() if urlsplit(route.request.url).hostname == '127.0.0.1' else route.abort())
            if failure == 'entitlement':
                page.route('**/v1/rig/3d/capabilities', lambda route: route.fulfill(json={'rig_3d': False}))
            else:
                def corrupt(route):
                    response = route.fetch()
                    data = response.json()
                    if failure == 'expired':
                        data['valid_until'] = 1
                    elif failure == 'integrity':
                        data['models'][0]['sha256'] = '0' * 64
                    else:
                        data['models'][0]['url'] = 'https://untrusted.test/model.glb'
                    route.fulfill(json=data)
                page.route('**/v1/rig/3d/assembly', corrupt)
            page.goto(BASE + '/viewer-test')
            page.get_by_placeholder('Search a make, model or part', exact=True).fill('Centre')
            page.get_by_role('button', name='Complete my setup', exact=True).click()
            if failure == 'entitlement':
                assert page.get_by_role('button', name='Open 3D', exact=True).count() == 0
                assert not any(url.startswith(BASE + '/3d/') or '/v1/rig/3d/assets/' in url for url in requested)
            else:
                page.get_by_role('button', name='Open 3D', exact=True).click()
                page.locator('.rig-3d[data-state=' + ('photos' if failure == 'expired' else 'error') + ']').wait_for()
                assert page.locator('.rig-3d').get_attribute('data-models') is None
                assert not any('untrusted.test' in url for url in requested)
                if failure == 'expired':
                    assert not any('/3d/assets/viewer-' in url or '/v1/rig/3d/assets/' in url for url in requested)
            page.close()
        browser.close()
    (OUT / 'comparison.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    import os
    import subprocess
    import sys
    import tempfile
    import time
    from urllib.request import urlopen

    if '--serve' not in sys.argv:
        main()
    else:
        database = os.environ.get('RIG_3D_TEST_DATABASE_URL', '')
        if urlsplit(database).hostname not in {'127.0.0.1', 'localhost'}:
            raise SystemExit('--serve requires an explicit disposable loopback database')
        env = dict(os.environ, PYTHONPATH=os.pathsep.join(str(ROOT / p) for p in ('agents/rig', 'agents/_chassis', 'tests')))
        with tempfile.TemporaryFile(mode='w+') as log:
            server = subprocess.Popen([sys.executable, '-m', 'uvicorn', 'fixtures.rig_three_d.viewer:app',
                '--host', '127.0.0.1', '--port', '8035', '--log-level', 'warning'], cwd=ROOT, env=env, stdout=log, stderr=log)
            try:
                for _ in range(300):
                    if server.poll() is not None:
                        log.seek(0)
                        raise RuntimeError(log.read())
                    try:
                        with urlopen(BASE + '/health', timeout=1) as response:
                            if response.status == 200:
                                break
                    except OSError:
                        time.sleep(.1)
                else:
                    raise RuntimeError('The offline fixture server did not start')
                main()
            finally:
                server.terminate()
                try:
                    server.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    server.kill()
                    server.wait()
