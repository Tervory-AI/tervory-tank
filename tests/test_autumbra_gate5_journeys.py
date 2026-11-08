"""Actual Next pages -> actual Watch/queue -> fake provider. No live services."""
import asyncio
import os
from pathlib import Path
import shutil
import socket
from types import SimpleNamespace
from urllib.parse import parse_qs, urlencode, urlsplit

import httpx
import pytest
import pytest_asyncio
from fastapi import FastAPI, Request
from fastapi.responses import Response
import uvicorn

from acceptance.test_autumbra import box, engine, enqueue, settings, A, B, KEY
from agents.ghost.undo_token import sign_receipts_token, sign_undo_token

__all__ = ["box", "settings"]  # pytest fixture re-exports

ROOT = Path(__file__).resolve().parents[1]
SERVER = '''import {cookies} from "next/headers";
export {signinDirectory} from "./trigger-signin-directory";
export async function currentUser() { return {firstName:null as string | null}; }
export async function signinToken() { return "placeholder-offline-identity"; }
export async function auth() {
 const userId=(await cookies()).get("offline-user")?.value;
 return {userId:userId||null, orgId:userId?"org-a":null, tenantId:userId?"aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa":null, orgRole:null};
}
'''
CLIENT = '''"use client";
export function SessionProvider({children}: {children: React.ReactNode}) {return children;}
export function useSession() { return {data:null,status:"unauthenticated",update:async()=>null}; }
export async function signOut(_options?: unknown) { window.location.href="/autumbra"; }
export async function signIn(_provider: string, options: {callbackUrl:string}, params: {prompt:string}) {
 const query=new URLSearchParams({callbackUrl:options.callbackUrl,prompt:params.prompt});
 window.location.href="/api/auth/offline?"+query;
}
'''
AUTH_ROUTE = '''import {NextResponse} from "next/server";
export async function GET(request: Request) {
 const url=new URL(request.url), dest=new URL(url.searchParams.get("callbackUrl")||"/autumbra",url.origin);
 if(dest.origin!==url.origin) return new Response("Invalid callback",{status:400});
 const response=NextResponse.redirect(dest);
 response.cookies.set("offline-user","offline-founder",{httpOnly:true,sameSite:"lax",path:"/"});
 response.cookies.set("offline-prompt",url.searchParams.get("prompt")||"",{path:"/"});
 return response;
}
'''


@pytest_asyncio.fixture
async def journey(request, box, tmp_path):
    missing = getattr(request, 'param', False)
    fake = FastAPI()
    state = SimpleNamespace(fail=False, calls=[], failures=[])
    @fake.api_route('/{path:path}', methods=['GET', 'POST'])
    async def forward(path: str, req: Request):
        state.calls.append((req.method, path))
        if state.fail:
            return Response('placeholder-private-upstream', status_code=503)
        if path == 'v1/case-studies/ensure':
            return Response('{}', media_type='application/json')
        if not path.startswith('v1/ghost/'):
            return Response('{}', status_code=404, media_type='application/json')
        short = path.removeprefix('v1/ghost/')
        route = '/' + short if short in {'incidents', 'look', 'message'} or short.startswith('incidents/') else '/ghost/' + short
        route = {'shields/list':'/ghost/shields', 'shields/tile':'/ghost/summary'}.get(short, route)
        response = await box.client.request(req.method, route, params=req.query_params,
                                            content=await req.body(), headers={'X-Tank-Key': req.headers.get('x-tank-key',''),
                                                'Content-Type': req.headers.get('content-type','application/json')})
        if response.status_code >= 400:
            state.failures.append((route, response.status_code, response.text[:300], (await req.body()).decode()[:100]))
        if short == 'shields/tile' and response.status_code == 200:
            import json
            return Response(json.dumps({**response.json(), 'cost_this_month_usd':0,
                'receipts_this_month':box.receipts.record.await_count}), media_type='application/json')
        return Response(response.content, status_code=response.status_code, media_type='application/json')
    sock = socket.socket(); sock.bind(('127.0.0.1', 0)); sock.listen()
    provider = uvicorn.Server(uvicorn.Config(fake, log_level='error', lifespan='off'))
    task = asyncio.create_task(provider.serve(sockets=[sock]))
    local = tmp_path / 'workspace'
    shutil.copytree(ROOT / 'workspace', local, ignore=shutil.ignore_patterns('node_modules', '.next', '.env*', '*.tsbuildinfo'))
    (local / 'node_modules').symlink_to(ROOT / 'workspace/node_modules', target_is_directory=True)
    (local / 'lib/trigger-signin.ts').write_text(SERVER)
    (local / 'offline-session.tsx').write_text(CLIENT)
    (local / 'offline-jwt.ts').write_text('import type {NextRequest} from "next/server"; export async function getToken({req}: {req:NextRequest; secret?:string; cookieName?:string; secureCookie?:boolean}) {return req.cookies.get("offline-user") ? {principal:{expiresAt:Date.now()+60000}} : null;}')
    middleware = local / 'middleware.ts'
    middleware.write_text(middleware.read_text().replace('from "next-auth/jwt"','from "./offline-jwt"'))
    callback = local / 'app/api/auth/offline/route.ts'; callback.parent.mkdir(parents=True, exist_ok=True); callback.write_text(AUTH_ROUTE)
    (local / 'next.config.ts').write_text('''import path from "node:path";
import type {NextConfig} from "next";
const config: NextConfig = {devIndicators:false,experimental:{cpus:1},webpack(config){config.resolve ??= {}; config.resolve.alias={...config.resolve.alias,"next-auth/react$":path.resolve("offline-session.tsx")};return config;}};
export default config;
''')
    with socket.socket() as listen:
        listen.bind(('127.0.0.1', 0)); port = listen.getsockname()[1]
    internal_origin = f'http://localhost:{port}'
    proxy_socket = socket.socket(); proxy_socket.bind(('127.0.0.1', 0)); proxy_socket.listen()
    origin = f'http://localhost:{proxy_socket.getsockname()[1]}'
    env = {**os.environ, 'NEXT_TELEMETRY_DISABLED':'1', 'TERVORY_ADMIN_USER_IDS':'offline-founder',
           'TANK_URL':f'http://127.0.0.1:{sock.getsockname()[1]}', 'TANK_API_KEY':'' if missing else KEY,
           'AUTUMBRA_UNDO_TOKEN_SECRET':'fixture-undo-key',
           'TRIGGER_SIGNIN_WORKSPACE_SECRET':'placeholder-offline-signin-secret'}
    log_path = tmp_path / 'journey-next.log'
    process = None
    proxy_job = None
    proxy = None
    async with httpx.AsyncClient(trust_env=False, follow_redirects=False, timeout=30) as upstream:
        reverse = FastAPI()
        @reverse.api_route('/{path:path}', methods=['GET','HEAD','POST','PUT','PATCH','DELETE','OPTIONS'])
        async def local_host(path: str, req: Request):
            # Model the deployed virtual host without DNS or a public connection.
            # The ONLY destination is our loopback Next process. Foreign Origins
            # stay foreign, so production's real origin check still rejects them.
            headers = dict(req.headers)
            headers.update(host='app.tervory.com')
            headers.pop('x-forwarded-host', None)
            headers.pop('x-forwarded-proto', None)
            if headers.get('origin') == origin:
                headers['origin'] = 'https://app.tervory.com'
            target = internal_origin + req.url.path + ('?' + req.url.query if req.url.query else '')
            try:
                outgoing = upstream.build_request(req.method, target, content=await req.body(), headers=headers)
                # A reverse proxy must never carry cookies between browser requests.
                if "cookie" not in req.headers:
                    outgoing.headers.pop("cookie", None)
                response = await upstream.send(outgoing)
            except httpx.ConnectError:
                return Response("Application starting", status_code=503)
            forwarded = {k:v for k,v in response.headers.items()
                         if k not in {'content-encoding','content-length','transfer-encoding','connection','set-cookie'}}
            location = forwarded.get('location', '')
            for base in (internal_origin, 'http://app.tervory.com', 'https://app.tervory.com'):
                if location.startswith(base + '/'):
                    forwarded['location'] = origin + location[len(base):]
                    break
            result = Response(response.content, status_code=response.status_code, headers=forwarded)
            for value in response.headers.get_list("set-cookie"):
                result.raw_headers.append((b"set-cookie", value.encode("latin-1")))
            return result
        try:
            with log_path.open('w') as log:
                # Production assets avoid development/HMR payloads in the phone test.
                process = await asyncio.create_subprocess_exec('node', str(local / 'node_modules/next/dist/bin/next'),
                    'build', cwd=local, env=env, stdout=log, stderr=asyncio.subprocess.STDOUT)
                if await process.wait():
                    pytest.fail(log_path.read_text()[-4000:])
                process = await asyncio.create_subprocess_exec('node', str(local / 'node_modules/next/dist/bin/next'),
                    'start', '--hostname', 'localhost', '--port', str(port), cwd=local, env=env, stdout=log, stderr=asyncio.subprocess.STDOUT)
                proxy = uvicorn.Server(uvicorn.Config(reverse, log_level='error', lifespan='off'))
                proxy_job = asyncio.create_task(proxy.serve(sockets=[proxy_socket]))
                async with httpx.AsyncClient(trust_env=False) as client:
                    for _ in range(100):
                        if process.returncode is not None: pytest.fail(log_path.read_text()[-4000:])
                        try:
                            response = await client.get(origin + '/autumbra', timeout=2)
                            if response.status_code == 200:
                                expected = 'Workspace needs these settings: TANK_API_KEY.' if missing and (local/'lib/workspace-setup.ts').exists() else 'autumbra-public'
                                assert expected in response.text, 'Autumbra application did not become ready'
                                break
                        except httpx.HTTPError: pass
                        await asyncio.sleep(.3)
                    else: pytest.fail(log_path.read_text()[-4000:])
                yield SimpleNamespace(origin=origin, box=box, fake=state, log=log_path,
                                      setup_guard=(local/'lib/workspace-setup.ts').exists())
        finally:
            if process is not None and process.returncode is None:
                process.terminate(); await asyncio.wait_for(process.wait(), 15)
            if proxy_job is not None:
                proxy.should_exit=True; await asyncio.wait_for(proxy_job, 15)
            else:
                proxy_socket.close()
            provider.should_exit=True; await asyncio.wait_for(task, 15)


async def open_browser(browser, origin):
    context = await browser.new_context(viewport={'width':360,'height':780}, reduced_motion='reduce')
    await context.route('**/*', lambda route: route.continue_() if route.request.url.startswith(origin+'/') else route.abort())
    page = await context.new_page()
    page.set_default_timeout(20000)
    return context, page


async def accessible(page, selector):
    """Check actual rendered text contrast, names, geometry and keyboard targets."""
    assert await page.locator('main').count() == 1
    result = await page.locator(selector).evaluate('''root => {
      const problems=[], rgb=s=>s.match(/[\\d.]+/g)?.map(Number)||[0,0,0];
      const lum=c=>c.slice(0,3).map(n=>n/255).map(n=>n<=.04045?n/12.92:((n+.055)/1.055)**2.4).reduce((v,n,i)=>v+n*[.2126,.7152,.0722][i],0);
      for(const el of root.querySelectorAll('*')) {
        const s=getComputedStyle(el), r=el.getBoundingClientRect();
        if(!r.width||!r.height||s.visibility==='hidden'||s.display==='none') continue;
        if(el.matches('button,select,input:not([type=hidden]),a[href],summary') && !el.disabled) {
          if(!el.textContent.trim()&&!el.getAttribute('aria-label')&&!el.labels?.length) problems.push('unnamed '+el.tagName);
          if(el.tabIndex<0) problems.push('keyboard '+el.tagName);
        }
        if(![...el.childNodes].some(n=>n.nodeType===3&&n.textContent.trim())) continue;
        let parent=el, bg;
        while(parent) {bg=rgb(getComputedStyle(parent).backgroundColor); if(bg.length<4||bg[3]===1)break; parent=parent.parentElement;}
        if(!parent) bg=[255,255,255];
        const fg=rgb(s.color), ratio=(Math.max(lum(fg),lum(bg))+.05)/(Math.min(lum(fg),lum(bg))+.05);
        const large=parseFloat(s.fontSize)>=24||(parseFloat(s.fontSize)>=18.66&&parseInt(s.fontWeight)>=700);
        if(!el.matches(':disabled')&&ratio<(large?3:4.5)) problems.push('contrast '+el.tagName+' '+ratio.toFixed(2)+' '+el.textContent.slice(0,30));
      }
      if(document.documentElement.scrollWidth>innerWidth+1) problems.push('horizontal overflow');
      return problems;
    }''')
    assert result == []


@pytest.mark.asyncio
async def test_signup_day_zero_first_action_result_receipt_error_retry_and_undo(journey, real_chromium):
    from playwright.async_api import expect
    j = journey
    context, page = await open_browser(real_chromium, j.origin)
    errors=[]; page.on('pageerror', lambda e: errors.append(str(e)))
    try:
        async with httpx.AsyncClient(trust_env=False,follow_redirects=False) as client:
            response=await client.get(j.origin+'/admin/autumbra')
            assert response.status_code==307 and '/sign-in?' in response.headers['location']
            response=await client.get(j.origin+'/admin/autumbra',cookies={'offline-user':'other-owner'})
            assert response.status_code==404
            if j.setup_guard:
                # Current Tank adds a Workspace-wide origin guard; vendor predates it.
                response=await client.post(j.origin+'/admin/autumbra',headers={'Origin':'https://foreign.invalid'},cookies={'offline-user':'offline-founder'})
                assert response.status_code==403
        await page.goto(j.origin+'/autumbra'); await accessible(page, '.autumbra-public')
        weekly = '/autumbra/receipts/weekly/'+A
        await page.goto(j.origin+'/sign-up?'+urlencode({'callbackUrl':weekly}))
        await expect(page.get_by_text('Create your account through Trigger sign-in.')).to_be_visible()
        button=page.get_by_role('button',name='Continue to Trigger sign-in'); await button.focus(); await page.keyboard.press('Enter')
        await expect(page).to_have_url(j.origin+weekly)
        await expect(page.get_by_text('0 recorded',exact=True)).to_be_visible()
        await expect(page.get_by_text("No receipts for this week yet. Connect your site's log feed to start a check.")).to_be_visible()
        assert next(c['value'] for c in await context.cookies() if c['name']=='offline-prompt')=='create'
        await accessible(page,'main')
        await page.goto(j.origin+'/admin/autumbra')
        await expect(page.get_by_text('No issues recorded yet. Use Look to start a check.')).to_be_visible()
        await accessible(page,'.ghost-panel')
        await page.get_by_label('Where',exact=True).select_option('workspace')
        await page.get_by_label('What to check',exact=True).select_option('health')
        look=page.get_by_role('button',name='Look',exact=True); await look.focus(); await page.keyboard.press('Enter')
        try:
            await expect(page.locator('.ghost-issue')).to_have_count(1)
        except AssertionError:
            pytest.fail(str(j.fake.failures) + '\n' + str(errors) + '\n' + await page.locator('body').inner_text())
        await page.get_by_text('Investigation receipts',exact=True).click()
        assert await page.locator('.ghost-receipts li').count() > 0
        await page.get_by_text('Confirm a completed fix',exact=True).click()
        await page.get_by_role('button',name='Verify and remember').click()
        await expect(page.get_by_text('The issue could not be verified. It has not been marked solved.')).to_be_visible()
        j.box.app.state.failing=False
        await page.get_by_role('button',name='Verify and remember').click()
        await expect(page.locator('.ghost-state')).to_have_text('solved')
        j.fake.fail=True
        await look.click()
        await expect(page.get_by_text('Autumbra could not finish the investigation. Check its room and Tank connection.')).to_be_visible()
        assert 'placeholder-private-upstream' not in await page.locator('body').inner_text()
        j.fake.fail=False
        await look.click()
        await expect(page.locator('.ghost-issue')).to_have_count(2)
        proposed = await j.box.client.post('/ghost/shields/propose', json={
            'site':'coolify.tervory.com', 'kind':'block_multipart_post'})
        assert proposed.status_code == 200
        await page.reload()
        await page.get_by_role('button',name='Shield',exact=True).click()
        await expect(page.locator('.ghost-shield .ghost-state')).to_have_text('Staged')
        await page.locator('.ghost-shield').get_by_text('Receipts',exact=True).click()
        assert await page.locator('.ghost-shield .ghost-receipts li').count() > 0
        await accessible(page,'.ghost-panel')
        await page.get_by_role('button',name='Undo',exact=True).click()
        await expect(page.locator('.ghost-shield .ghost-state')).to_have_text('Withdrawn')
        # Real queue and edge control, with a fake provider response and fake health observer.
        api, queue, drain = await engine(j.box)
        await enqueue(j.box)
        receipt=await drain(); assert receipt['outcome']=='applied'
        await page.goto(j.origin+weekly+'?'+urlencode({'token':sign_receipts_token(tenant_id=A)}))
        await expect(page.get_by_text('1 recorded',exact=True)).to_be_visible()
        await accessible(page,'main')
        link=urlsplit(await page.get_by_role('link',name='Undo this block',exact=True).get_attribute('href'))
        assert link.scheme=='https' and link.hostname=='protect.tervory.com'
        token=parse_qs(link.query)['token'][0]
        # Keep the real email link path/token; substitute this local origin only.
        undo=link.path+'?'+link.query
        await page.goto(j.origin+undo)
        assert await page.locator('meta[name=referrer]').get_attribute('content') == 'no-referrer'
        await accessible(page,'main')
        button=page.get_by_role('button',name='Undo this shield',exact=True)
        before=await button.bounding_box()
        j.fake.fail=True
        await button.click()
        await expect(page.locator('p[role=alert]')).to_have_text('Could not undo that shield right now.')
        assert await button.bounding_box()==before
        j.fake.fail=False
        # Two DOM clicks in one turn must issue one write.
        await button.evaluate('b=>{b.click();b.click();}')
        await expect(page.get_by_role('status')).to_have_text('Done. That shield is being removed.')
        assert len(list((queue.root/'inbox').glob('*.json')))==1
        assert (await drain())['outcome']=='undone'
        await page.reload()
        await expect(page.get_by_role('button')).to_have_count(0)
        assert 'already undone' in await page.locator('body').inner_text()
        await page.goto(j.origin+'/autumbra/undo/wrong?'+urlencode({'token':token}))
        await expect(page.get_by_text('This link is invalid or has expired.',exact=True)).to_be_visible()
        await page.goto(j.origin+'/autumbra/receipts/weekly/'+B+'?'+urlencode({'token':sign_receipts_token(tenant_id=A)}))
        await expect(page.get_by_text('This link is invalid or has expired.',exact=True)).to_be_visible()
        assert not errors
        # Production assets, unchanged 20-second network-idle limit; real Chrome emulates a slow phone.
        cdp=await context.new_cdp_session(page)
        await cdp.send('Emulation.setCPUThrottlingRate',{'rate':4})
        await cdp.send('Network.emulateNetworkConditions',{'offline':False,'latency':150,'downloadThroughput':200000,'uploadThroughput':100000})
        pending = {}
        started = __import__('time').monotonic
        page.on('request', lambda req: pending.update({req: (req.method, urlsplit(req.url).path, started())}))
        page.on('requestfinished', lambda req: pending.pop(req, None))
        page.on('requestfailed', lambda req: pending.pop(req, None))
        for path in ['/autumbra',weekly,'/admin/autumbra',undo]:
            try:
                await page.goto(j.origin+path,wait_until='networkidle')
            except Exception:
                # Paths/timings only: never log signed query strings or headers.
                print('READINESS', path.split('?')[0], [(method, url, round(started()-stamp, 2))
                      for method, url, stamp in pending.values()])
                print('NAVIGATION', await page.evaluate('performance.getEntriesByType("navigation").map(n=>({dom:n.domContentLoadedEventEnd,load:n.loadEventEnd,bytes:n.transferSize}))'))
                raise
            await page.wait_for_timeout(100)
            timing=await page.evaluate('performance.getEntriesByType("navigation")[0].toJSON()')
            assert timing['loadEventEnd'] > 0
            print('PHONE', path.split('?')[0], {key:round(timing[key]) for key in ('responseStart','domContentLoadedEventEnd','loadEventEnd')})
            assert timing['responseStart']-timing['startTime']<5000
            assert timing['domContentLoadedEventEnd']-timing['startTime']<10000
            assert await page.evaluate('document.documentElement.scrollWidth<=innerWidth+1')
    finally:
        await context.close()


@pytest.mark.asyncio
@pytest.mark.parametrize('journey',[True],indirect=True)
async def test_missing_setting_signed_out_and_other_owner_have_no_unsafe_action(journey, real_chromium):
    from playwright.async_api import expect
    j=journey; context,page=await open_browser(real_chromium,j.origin)
    try:
        weekly='/autumbra/receipts/weekly/'+A+'?'+urlencode({'token':sign_receipts_token(tenant_id=A)})
        await page.goto(j.origin+weekly)
        token=sign_undo_token(tenant_id=A,receipt_id='receipt-one',site='tervory.com')
        if j.setup_guard:
            # Current Tank stops the entire Workspace before rendering product controls.
            await expect(page.get_by_role('status')).to_have_text('Workspace needs these settings: TANK_API_KEY.')
            await expect(page.get_by_role('button')).to_have_count(0)
            await page.goto(j.origin+'/autumbra/undo/receipt-one?'+urlencode({'token':token}))
            await expect(page.get_by_role('status')).to_have_text('Workspace needs these settings: TANK_API_KEY.')
            await expect(page.get_by_role('button')).to_have_count(0)
            # The actual API also refuses the signed write independently of the layout.
            response=await context.request.post(j.origin+'/api/autumbra/undo', data={'token':token})
            assert response.status==503
            assert (await response.json())['error']=='Workspace needs these settings: TANK_API_KEY.'
        else:
            # Keep the original product guard assertions on the byte-pinned vendor baseline.
            await expect(page.get_by_text('Missing setting: TANK_API_KEY. Connect Autumbra to load receipts.')).to_be_visible()
            await page.goto(j.origin+'/autumbra/undo/receipt-one?'+urlencode({'token':token}))
            await page.get_by_role('button',name='Undo this shield',exact=True).click()
            await expect(page.locator('p[role=alert]')).to_have_text('Undo is not configured on this host yet.')
        assert j.fake.calls==[]
        async with httpx.AsyncClient(trust_env=False,follow_redirects=False) as client:
            response=await client.get(j.origin+'/admin/autumbra')
            if j.setup_guard:
                assert response.status_code==200 and 'Workspace needs these settings: TANK_API_KEY.' in response.text
            else:
                assert response.status_code==307 and '/sign-in?' in response.headers['location']
            response=await client.get(j.origin+'/admin/autumbra',cookies={'offline-user':'other-owner'})
            if j.setup_guard:
                assert response.status_code==200 and 'Workspace needs these settings: TANK_API_KEY.' in response.text
            else:
                assert response.status_code==404
        assert j.fake.calls==[]
        await accessible(page,'main')
    finally:
        await context.close()
