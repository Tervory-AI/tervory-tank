"""The shipped landing views contain decorative overflow without changing the viewport."""
from hashlib import sha256
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1] / 'agents/rig/rigbox/page/v5'


@pytest.mark.asyncio
@pytest.mark.parametrize('width', [375, 1440])
@pytest.mark.parametrize('skin', ['tervory', 'cn'])
@pytest.mark.parametrize('view', ['landing', 'idk'])
async def test_decorative_overflow_preserves_viewport(real_chromium, tmp_path, width, skin, view):
    page = await real_chromium.new_page(viewport={'width': width, 'height': 900})
    html = (ROOT / 'index.html').read_text().replace('__RIG_SKIN__', skin)
    html = html.replace('__RIG_KEY__', 'null').replace('__RIG_SHOP__', 'null')

    async def shipped_file(route):
        from urllib.parse import urlsplit
        path = urlsplit(route.request.url).path
        if path == '/':
            await route.fulfill(body=html, content_type='text/html')
        elif path.startswith('/page/v5/'):
            asset = ROOT / path.removeprefix('/page/v5/')
            if asset.is_file() and asset.resolve().is_relative_to(ROOT):
                await route.fulfill(path=str(asset))
            else:
                await route.abort()
        else:
            await route.abort()

    await page.route('**/*', shipped_file)
    await page.goto('http://rig.test/')
    await page.evaluate('''view => {
      document.body.dataset.view = view;
      document.querySelector('#landing').hidden = view !== 'landing';
      document.querySelector('#idk').hidden = view !== 'idk';
    }''', view)
    # Undo only the containment to reproduce the original shipped CSS, then
    # compare it to the repair in the same browser with identical fonts/assets.
    baseline = await page.add_style_tag(content='.landing, .idk { overflow-x: visible; }')
    geometry = '''() => [...document.querySelectorAll('body *')].filter(e =>
      e.getClientRects().length).map(e => { const r=e.getBoundingClientRect();
      return [e.tagName,e.id,r.x,r.y,r.width,r.height]; })'''
    before_geometry = await page.evaluate(geometry)
    before_accessible = await page.locator('body').aria_snapshot()
    before = await page.screenshot(path=str(tmp_path / 'before.png'))
    if width == 375:
        assert await page.evaluate('document.documentElement.scrollWidth > innerWidth')
    await baseline.evaluate('(e) => e.remove()')
    assert await page.evaluate('document.documentElement.scrollWidth <= document.documentElement.clientWidth')
    assert await page.evaluate('document.body.scrollWidth <= innerWidth')
    assert await page.evaluate(geometry) == before_geometry
    assert await page.locator('body').aria_snapshot() == before_accessible
    after = await page.screenshot(path=str(tmp_path / 'after.png'))
    # Keep exact equality while avoiding pytest's expensive binary sequence diff.
    # A mismatching PNG previously spent the entire test timeout in difflib.
    same_screenshot = after == before
    assert same_screenshot, (
        f"Screenshot changed: before_sha256={sha256(before).hexdigest()} "
        f"after_sha256={sha256(after).hexdigest()}; "
        f"files: {tmp_path / 'before.png'}, {tmp_path / 'after.png'}"
    )
    await page.close()
