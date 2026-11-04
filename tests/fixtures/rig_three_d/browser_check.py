"""Offline packaged-widget proof. Run against the disposable viewer fixture on :8035."""
import json
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
        browser = p.chromium.launch(executable_path='/opt/google/chrome/chrome', args=[
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
        browser.close()
    (OUT / 'comparison.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
