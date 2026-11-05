"""Execute the Workspace backend with fixture identity and Tank boundaries."""
import os
from pathlib import Path
import shutil
import subprocess

import pytest

ROOT = Path(__file__).resolve().parents[1]


def test_workspace_paid_settings_contract():
    node = shutil.which('node')
    typescript = next((p for p in (ROOT/'workspace/node_modules/typescript', ROOT/'cli/node_modules/typescript') if p.is_dir()),None)
    if not node or typescript is None:
        pytest.skip('Workspace/CLI Node dependencies required for the backend contract')
    subprocess.run([node,str(ROOT/'tests/paid_steps_settings.cjs')],cwd=ROOT,
        env={**os.environ,'PAID_STEP_TYPESCRIPT':str(typescript)},check=True,timeout=60)


@pytest.fixture(scope='module')
def paid_settings_bundle(tmp_path_factory):
    if not shutil.which('node') or not (ROOT/'workspace/node_modules/next').is_dir():
        pytest.skip('Workspace Node dependencies required for the settings browser')
    folder=tmp_path_factory.mktemp('placeholder-paid-browser')
    result=subprocess.run(['node',str(ROOT/'tests/paid_steps_browser_build.cjs'),str(folder)],cwd=ROOT,
        capture_output=True,text=True,timeout=180)
    assert result.returncode==0,result.stdout+result.stderr
    return (folder/'bundle.js').read_text()


@pytest.mark.asyncio
@pytest.mark.parametrize('width',[375,390,1440])
async def test_paid_settings_actual_browser(paid_settings_bundle,real_chromium,width):
    import asyncio
    import json
    from urllib.parse import urlsplit
    from playwright.async_api import expect
    steps=[{'step_id':f'base.placeholder.step_{n}','product':'base','kind':'model',
            'source':'placeholder route','task_type':'base.placeholder','model':f'placeholder model {n}','mode':'ask'} for n in range(3)]
    fixture={'founder':True,'paused':False}
    writes=[]
    failed=False
    outside=[]
    load_ready=asyncio.Event()
    css=':root{--font-inter:Inter;--font-jost:Jost}@font-face{font-family:Inter;src:url(/fixture-inter.woff2);font-weight:100 900}@font-face{font-family:Jost;src:url(/fixture-jost.woff2);font-weight:300}\n'+'\n'.join((ROOT/name).read_text() for name in ('workspace/app/trigger/trigger.css','workspace/app/settings/paid-steps/settings.css'))
    page=await real_chromium.new_page(viewport={'width':width,'height':946})
    async def serve(route):
        nonlocal failed
        request=route.request
        url=urlsplit(request.url)
        if url.hostname!='127.0.0.1':
            outside.append(request.url)
            await route.abort()
            return
        if url.path=='/bundle.js':
            await route.fulfill(content_type='application/javascript',body=paid_settings_bundle)
        elif url.path=='/fixture-jost.woff2':
            await route.fulfill(content_type='font/woff2',body=(ROOT/'workspace/app/fonts/Jost-300-latin.woff2').read_bytes())
        elif url.path=='/fixture-inter.woff2':
            await route.fulfill(content_type='font/woff2',body=(ROOT/'workspace/app/fonts/Inter-latin.woff2').read_bytes())
        elif url.path=='/trigger/wordmark.png':
            await route.fulfill(content_type='image/png',body=(ROOT/'workspace/public/trigger/wordmark.png').read_bytes())
        elif url.path=='/settings/paid-steps/api':
            if failed:
                await route.fulfill(status=500,json={})
            elif request.method=='PUT':
                value=request.post_data_json
                writes.append(value)
                await route.fulfill(json=value)
            else:
                await load_ready.wait()
                await route.fulfill(json={'steps':steps})
        else:
            await route.fulfill(content_type='text/html',body='<html><head><style>*{box-sizing:border-box}body{margin:0;font-family:Inter,Arial,sans-serif}</style><style>'+css+'</style></head><body><div id="root"></div><script>window.paidFixture='+json.dumps(fixture)+'</script><script src="/bundle.js"></script></body></html>')
    await page.route('**/*',serve)
    try:
        await page.goto('http://127.0.0.1:38991/settings/paid-steps')
        await expect(page.get_by_role('heading',name='Loading…',exact=True)).to_be_visible()
        load_ready.set()
        await expect(page.locator('.paid-step')).to_have_count(3)
        await expect(page.locator('.paid-step h3')).to_have_text([f'placeholder model {n}' for n in range(3)])
        await page.evaluate('document.fonts.ready')
        heading=page.get_by_role('heading',name='Paid steps settings',exact=True)
        await expect(heading).to_be_visible()
        assert await heading.evaluate('(el)=>getComputedStyle(el).fontSize') == ('32px' if width==1440 else '28px')
        assert (await heading.bounding_box())['y'] >= (64 if width<768 else 0)
        await expect(page.locator('.paid-modes button[aria-pressed=true]')).to_have_text(['Ask']*3)
        await page.screenshot(path=str(ROOT/'.tmp'/f'paid-settings-default-{width}.png'),full_page=True)
        await page.locator('.paid-step').nth(1).get_by_role('button',name='Auto',exact=True).click()
        await expect(page.locator('.paid-modes button[aria-pressed=true]')).to_have_text(['Ask','Auto','Ask'])
        await page.get_by_role('button',name='Save settings',exact=True).click()
        await expect(page.get_by_role('status')).to_have_text('Settings saved.')
        assert writes==[{'step_id':steps[1]['step_id'],'mode':'auto'}]
        await page.get_by_role('button',name='Pause all paid work',exact=True).click()
        await expect(page.get_by_role('heading',name='Paid work is paused.',exact=True)).to_be_visible()
        assert await page.evaluate('window.paidPauseCalls')==[True]
        await expect(page.locator('.paid-modes button[aria-pressed=true]')).to_have_text(['Ask','Auto','Ask'])
        assert await page.evaluate('document.documentElement.scrollWidth<=innerWidth')
        if width==1440:
            image=page.locator('.trigger-wordmark')
            assert await image.evaluate('(el)=>el.complete&&el.naturalWidth===2955&&el.getBoundingClientRect().width===208')
        failed=True
        await page.locator('.paid-step').nth(0).get_by_role('button',name='Auto',exact=True).click()
        await page.get_by_role('button',name='Save settings',exact=True).click()
        await expect(page.get_by_role('alert')).to_contain_text('Something went wrong')
        await expect(page.get_by_text('Settings saved.',exact=True)).to_have_count(0)
        failed=False
        steps.clear()
        await page.get_by_role('button',name='Try again',exact=True).click()
        await expect(page.get_by_role('heading',name='No paid steps yet.',exact=True)).to_be_visible()
        fixture['founder']=False
        steps.append({'step_id':'base.placeholder.admin.model.placeholder','product':'base','kind':'model','source':'placeholder route','mode':'ask'})
        await page.reload()
        await expect(page.locator('.paid-step')).to_have_count(1)
        await expect(page.get_by_text('Founder only',exact=True)).to_have_count(0)
        await expect(page.get_by_role('button',name='Pause all paid work',exact=True)).to_have_count(0)
        assert not outside
        destination=ROOT/'.tmp'/f'paid-settings-{width}.png'
        await page.screenshot(path=str(destination),full_page=True)
    finally:
        await page.close()
