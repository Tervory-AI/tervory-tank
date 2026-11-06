"""Real product UI and route journeys; sign-in and Tank are explicit offline fakes."""
import asyncio
import json
import os
import signal
import socket
import subprocess

import httpx
import pytest

from test_market_lab_h7_browser import wrapper, WORKSPACE


def launch_fixture(folder):
    wrapper(folder)
    def write(name, value):
        p=folder/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_text(value)
    write('fixture-tenant.ts', '''import {cookies} from 'next/headers';
export async function activeTenant(){return (await cookies()).get('fixture-session')?{tenantId:'00000000-0000-0000-0000-000000000031',userId:'placeholder-user',orgName:'Private test workspace'}:null;}''')
    write('fixture-tank.ts', '''export const VAULT_OFF_MESSAGE='Plugins are not available yet.';
const state=globalThis as any; state.fixtureAttempts??=0; state.fixturePanel??={enabled:true,message:null,secrets:[],files:[],links:[],connections:[]}; export function fixturePanel(){return state.fixturePanel;}
export async function marketLabRequest(tenant:string,operation:string,body:any){
 if(body?.question==='Retry inventory' && state.fixtureAttempts++===0) throw Error('placeholder-private-upstream-error');
 if(body?.question==='Settings inventory') throw Error('placeholder-missing-TANK_KEY');
 return {content:'Stored inventory is 4 cases.',facts:[{text:'Inventory is 4 cases.',href:'/market-lab/sources/00000000-0000-0000-0000-000000000051#passage-0',name:'inventory.csv'}],sources:[{name:'inventory.csv',href:'/market-lab/sources/00000000-0000-0000-0000-000000000051#passage-0'}],ledger_id:'00000000-0000-0000-0000-000000000061',cost_usd:0};
}
export async function marketWarningRequest(){return {saved:true};}
export async function addVaultConnection(...a:any[]){state.fixturePanel.connections=[{id:'placeholder-connection',name:a[4],serverUrl:a[5],authType:a[6],status:'connected',lastUsed:null,hasToken:true}];}
export async function addVaultLink(...a:any[]){state.fixturePanel.links=[{id:'placeholder-link',url:a[4],label:a[5],frequency:a[6],status:'not_checked',lastChecked:null}];}
export async function removeVaultConnection(){state.fixturePanel.connections=[];}
export async function removeVaultFile(){state.fixturePanel.files=[];}
export async function removeVaultLink(){state.fixturePanel.links=[];}
export async function removeVaultSecret(){state.fixturePanel.secrets=[];}
export async function saveVaultSecret(...a:any[]){state.fixturePanel.secrets=[{name:a[4],purpose:a[5],mask:'••••••••',savedAt:'2026-11-05T00:00:00Z'}];}
export async function uploadVaultFiles(...a:any[]){const f=a[4].get('file');state.fixturePanel.files=[{id:'00000000-0000-0000-0000-000000000051',name:f.name,type:'csv',size:f.size,rows:1,pages:null,uploadedAt:'2026-11-05T00:00:00Z',reason:'',status:'Learned'}];}''')
    write('next.config.mjs','''export default {experimental:{externalDir:true,cpus:1},devIndicators:false,webpack(config){config.resolve.alias={...config.resolve.alias,
"../trigger-signin-provider$":'''+json.dumps(str(folder/'fixture-signin.tsx'))+''',
"@/lib/tenant$":'''+json.dumps(str(folder/'fixture-tenant.ts'))+''',
"@/lib/tank$":'''+json.dumps(str(folder/'fixture-tank.ts'))+''',
"@":'''+json.dumps(str(WORKSPACE))+'''};return config;}};''')
    write('tsconfig.json',json.dumps({'compilerOptions':{'target':'ES2022','module':'esnext','moduleResolution':'bundler','jsx':'preserve','strict':True,'esModuleInterop':True,'skipLibCheck':True,'baseUrl':'.','paths':{'@/*':[str(WORKSPACE/'*')]}}}))
    write('app/onboarding/page.tsx','''import {cookies} from 'next/headers';import {redirect} from 'next/navigation';
async function signup(){'use server';(await cookies()).set('fixture-session','placeholder-session',{httpOnly:true,sameSite:'lax'});redirect('/market-lab');}
export default function Page(){return <main><h1>Workspace setup</h1><form action={signup}><button>Sign in</button></form></main>;}''')
    write('app/market-lab/page.tsx',f'''import {{redirect}} from 'next/navigation';
import {{activeTenant}} from '../../fixture-tenant';
import {{fixturePanel}} from '../../fixture-tank';
import {{MarketLabView}} from {json.dumps(str(WORKSPACE/'app/market-lab/view'))};
import {{Warnings}} from {json.dumps(str(WORKSPACE/'app/market-lab/warnings'))};
import {{buildPage}} from {json.dumps(str(WORKSPACE/'app/market-lab/model'))};
import {{emptyFlags}} from {json.dumps(str(WORKSPACE/'app/market-lab/catalog'))};
import {json.dumps(str(WORKSPACE/'app/market-lab/market-lab.css'))};
async function refresh(){{'use server';}}
export default async function Page(){{const tenant=await activeTenant();if(!tenant)redirect('/onboarding');
return <MarketLabView model={{buildPage(emptyFlags(),{{}},{{}})}} plugins={{fixturePanel()}} envKeys={{emptyFlags()}} refresh={{refresh}} workspaceName={{tenant.orgName}} warnings={{<Warnings data={{{{warnings:fixturePanel().files.length?[{{id:'00000000-0000-0000-0000-000000000071',title:'Inventory changed',facts:[],status:'Watching',feedback:null}}]:[],history:[]}}}}/>}}/>;}}''')
    write('app/market-lab/ask/route.ts','export {POST} from '+json.dumps(str(WORKSPACE/'app/market-lab/ask/route'))+';')
    write('app/market-lab/warnings/feedback/route.ts','export {POST} from '+json.dumps(str(WORKSPACE/'app/market-lab/warnings/feedback/route'))+';')
    write('app/market-lab/files/route.ts','export {POST} from '+json.dumps(str(WORKSPACE/'app/market-lab/files/route'))+';')
    write('app/market-lab/sources/[id]/page.tsx',f'''import {{SourceDocumentView}} from {json.dumps(str(WORKSPACE/'app/market-lab/source-view'))};
export const dynamic='force-dynamic';
import {{notFound}} from 'next/navigation';import {{fixturePanel}} from '../../../../fixture-tank';
export default function Page(){{if(!fixturePanel().files.length)notFound();return <SourceDocumentView source={{{{kind:'uploaded_file',name:'inventory.csv',fetched_at:'2026-11-05T00:00:00Z',passages:[{{index:0,label:'Row 2',text:'Inventory is 4 cases.',usable:true}}],page_size:100,passage_count:1}} as any}}/>;}}''')
    # Shared receipt and sign-in services are boundary doubles, never changes to
    # those products. Product source links and answer routes above are real.
    write('app/ledger/page.tsx',"export default function Page(){return <main><h1>Usage</h1><p>00000000-0000-0000-0000-000000000061</p><p>Cost: $0.00</p></main>}")


@pytest.mark.asyncio
async def test_client_journeys_keyboard_errors_receipts_and_slow_phone(real_chromium,tmp_path):
    folder=tmp_path/'journeys';launch_fixture(folder)
    with socket.socket() as sock:
        sock.bind(('127.0.0.1',0));port=sock.getsockname()[1]
    base=f'http://127.0.0.1:{port}'
    with (tmp_path/'next.log').open('w') as log:
        process=subprocess.Popen(['node',str(WORKSPACE/'node_modules/next/dist/bin/next'),'dev','--hostname','127.0.0.1','--port',str(port)],cwd=folder,
            env={**os.environ,'NEXT_TELEMETRY_DISABLED':'1','RAYON_NUM_THREADS':'1','UV_THREADPOOL_SIZE':'2'},stdout=log,stderr=log,start_new_session=True)
        try:
            async with httpx.AsyncClient(trust_env=False) as client:
                for _ in range(180):
                    try:
                        if (await client.get(base+'/onboarding',timeout=2)).status_code==200:break
                    except httpx.HTTPError:pass
                    if process.poll() is not None:raise AssertionError((tmp_path/'next.log').read_text())
                    await asyncio.sleep(.5)
                else:raise AssertionError((tmp_path/'next.log').read_text())
            context=await real_chromium.new_context(viewport={'width':375,'height':812},reduced_motion='reduce')
            errors=[];external=[];asks=[];feedbacks=[]
            async def restrict(route):
                if route.request.url.startswith(base+'/'):
                    if route.request.url.endswith('/market-lab/ask'):asks.append(route.request.post_data)
                    if route.request.url.endswith('/market-lab/warnings/feedback'):feedbacks.append(route.request.post_data)
                    await route.continue_()
                else:
                    external.append(route.request.url);await route.abort()
            await context.route('**/*',restrict)
            page=await context.new_page();page.on('pageerror',lambda error:errors.append(str(error)))
            await page.goto(base+'/market-lab',wait_until='networkidle')
            assert page.url.endswith('/onboarding')
            await page.get_by_role('button',name='Sign in',exact=True).focus();await page.keyboard.press('Enter')
            await page.get_by_role('heading',name='Market Lab',exact=True).wait_for()
            await page.wait_for_load_state('networkidle')
            assert await page.locator('.ml-count').first.inner_text()=='0'
            assert 'No feed data yet' in await page.inner_text('body')
            assert await page.evaluate('document.documentElement.scrollWidth<=innerWidth')
            response=await page.request.post(base+'/market-lab/ask',data={'question':'Inventory'},headers={'Origin':'https://untrusted.example'})
            assert response.status==403
            response=await page.request.post(base+'/market-lab/ask',data={'question':'Inventory','tenant_id':'00000000-0000-0000-0000-000000000032'})
            assert response.status==400
            response=await page.request.post(base+'/market-lab/files',data='placeholder',headers={'Origin':'https://untrusted.example'})
            assert response.status==403
            # Modal entry, keyboard tab cycle, escape and return focus.
            await page.get_by_role('button',name='Menu',exact=True).click()
            trigger=page.get_by_role('button',name='Plugins',exact=True)
            await trigger.focus();await page.keyboard.press('Enter')
            dialog=page.get_by_role('dialog',name='Plugins')
            await dialog.wait_for()
            assert await dialog.get_by_role('button',name='Close',exact=True).evaluate('(el)=>el===document.activeElement')
            await page.keyboard.press('Shift+Tab')
            assert await dialog.evaluate('(el)=>el.contains(document.activeElement)')
            tab=dialog.get_by_role('tab',name='Access keys',exact=True)
            await tab.focus();await page.keyboard.press('ArrowRight')
            assert await dialog.get_by_role('tab',name='Files',exact=True).get_attribute('aria-selected')=='true'
            ratio=await dialog.locator('.ml-or').evaluate('''el=>{
              const rgb=s=>s.match(/[0-9.]+/g).map(Number).slice(0,3).map(x=>{x/=255;return x<=.04045?x/12.92:((x+.055)/1.055)**2.4});
              const lum=s=>rgb(s).reduce((sum,v,i)=>sum+v*[.2126,.7152,.0722][i],0);
              let ancestor=el,bg='rgb(255,255,255)';while(ancestor){const color=getComputedStyle(ancestor).backgroundColor;if(color!=='rgba(0, 0, 0, 0)' && color!=='transparent'){bg=color;break;}ancestor=ancestor.parentElement;}
              const a=lum(getComputedStyle(el).color),b=lum(bg);return (Math.max(a,b)+.05)/(Math.min(a,b)+.05);
            }''')
            assert ratio>=4.5
            for name in ('Source links','Connections','Access keys'):

                await dialog.get_by_role('tab',name=name,exact=True).click()
                assert await dialog.get_by_role('tab',name=name,exact=True).get_attribute('aria-selected')=='true'
                assert await dialog.locator('input,select,textarea').evaluate_all('els=>els.every(el=>el.getAttribute("aria-label") || el.labels?.length)')
            supplier=dialog.locator('.ml-supplier')
            await supplier.get_by_label('Supplier name',exact=True).fill('Recorded supplier')
            await supplier.get_by_label('Key',exact=True).fill('placeholder-hidden-credential')
            await supplier.get_by_role('button',name='Save key',exact=True).click()
            await dialog.get_by_text('Saved. The key is hidden and will not be shown again.',exact=True).wait_for()
            assert 'placeholder-hidden-credential' not in await page.inner_text('body')
            await dialog.get_by_role('tab',name='Source links',exact=True).click()
            await dialog.get_by_label('Link',exact=True).fill('https://www.federalreserve.gov/feeds/press_all.xml')
            await dialog.get_by_label('Label (optional)',exact=True).fill('Recorded RSS')
            await dialog.get_by_role('button',name='Add link',exact=True).click()
            await dialog.get_by_text('Recorded RSS',exact=True).wait_for()
            await dialog.locator('.ml-prow').filter(has_text='Recorded RSS').get_by_role('button',name='Remove',exact=True).click()
            await dialog.get_by_text('No links stored. Use Add link to connect a public source.',exact=True).wait_for()
            await dialog.get_by_role('tab',name='Connections',exact=True).click()
            await dialog.get_by_label('Name',exact=True).fill('Recorded connector')
            await dialog.get_by_label('Server address',exact=True).fill('https://connector.example/mcp')
            await dialog.get_by_label('Access key',exact=True).fill('placeholder-hidden-connector')
            await dialog.get_by_role('button',name='Add connection',exact=True).click()
            await dialog.get_by_text('Recorded connector',exact=True).wait_for()
            assert 'placeholder-hidden-connector' not in await page.inner_text('body')
            await dialog.locator('.ml-prow').filter(has_text='Recorded connector').get_by_role('button',name='Remove',exact=True).click()
            await dialog.get_by_text('No connections stored. Add a connection to read your source.',exact=True).wait_for()
            await dialog.get_by_role('tab',name='Files',exact=True).click()
            await dialog.locator('input[type=file]').set_input_files({'name':'inventory.csv','mimeType':'text/csv','buffer':b'date,value,unit\n2026-11-05,4,cases\n'})
            await dialog.get_by_role('link',name='inventory.csv',exact=True).wait_for()
            await page.keyboard.press('Escape');await dialog.wait_for(state='hidden')
            assert await trigger.evaluate('(el)=>el===document.activeElement')
            if await page.get_by_role('button',name='Menu',exact=True).get_attribute('aria-expanded')=='true':
                await page.keyboard.press('Escape')
            await page.get_by_role('button',name='Useful',exact=True).dblclick()
            await page.get_by_text('Your choice is saved.',exact=True).wait_for()
            assert len(feedbacks)==1
            await page.get_by_role('button',name='Not useful',exact=True).click()
            await page.wait_for_function("[...document.querySelectorAll('button')].some(el=>el.textContent.trim()==='Not useful' && el.getAttribute('aria-pressed')==='true')")
            question=page.get_by_role('textbox',name='Ask Market Lab',exact=True)
            await question.fill('Inventory')
            before=len(asks)
            await page.get_by_role('button',name='Send',exact=True).dblclick()
            await page.get_by_text('Stored inventory is 4 cases.',exact=True).wait_for()
            assert len(asks)==before+1
            source=page.get_by_role('link',name='Open stored source',exact=True)
            await source.click();await page.locator('#passage-0').wait_for()
            assert 'Inventory is 4 cases.' in await page.inner_text('body')
            await page.go_back(wait_until='networkidle')
            await question.fill('Retry inventory');await page.get_by_role('button',name='Send',exact=True).click()
            await page.locator('.ml-answer [role=alert]').last.wait_for()
            await page.wait_for_function("document.querySelector('#ml-ask').value==='Retry inventory'")
            assert await question.input_value()=='Retry inventory'
            assert 'placeholder-private-upstream-error' not in await page.inner_text('body')
            await page.get_by_role('button',name='Send',exact=True).click()
            await page.get_by_text('Stored inventory is 4 cases.',exact=True).wait_for()
            await question.fill('Settings inventory');await page.get_by_role('button',name='Send',exact=True).click()
            await page.locator('.ml-answer [role=alert]').last.wait_for()
            await page.wait_for_function("document.querySelector('#ml-ask').value==='Settings inventory'")
            assert await question.input_value()=='Settings inventory'
            # Stalled fetch must abort, restore the draft and allow manual retry.
            await page.evaluate('''() => { const timeout=AbortSignal.timeout.bind(AbortSignal); AbortSignal.timeout=()=>timeout(50); const fetch=window.fetch; window.fetch=(url,init)=>String(url).endsWith('/market-lab/ask')?new Promise((resolve,reject)=>init.signal.addEventListener('abort',()=>reject(new DOMException('timeout','AbortError')))):fetch(url,init); }''')
            await question.fill('Inventory timeout');await page.get_by_role('button',name='Send',exact=True).click()
            await page.wait_for_function("document.querySelector('#ml-ask').value==='Inventory timeout'")
            assert await page.get_by_role('button',name='Send',exact=True).is_enabled()
            await page.reload(wait_until='networkidle')
            # Warm-page CPU throttling, no horizontal overflow or initial layout shifts.
            session=await context.new_cdp_session(page)
            await session.send('Emulation.setCPUThrottlingRate',{'rate':4})
            await session.send('Network.emulateNetworkConditions',{'offline':False,'latency':150,'downloadThroughput':200000,'uploadThroughput':100000})
            await page.add_init_script("window.fixtureCLS=0;new PerformanceObserver(list=>{for(const e of list.getEntries())if(!e.hadRecentInput)window.fixtureCLS+=e.value}).observe({type:'layout-shift',buffered:true});")
            await page.reload(wait_until='networkidle')
            assert await page.evaluate('document.documentElement.scrollWidth<=innerWidth')
            assert await page.evaluate('window.fixtureCLS')<.1
            assert await page.evaluate("performance.getEntriesByType('navigation')[0].domContentLoadedEventEnd")<15000
            # All interactive controls are named; focus outline is visible in light theme.
            unnamed=await page.locator('button,input,select').evaluate_all("els=>els.filter(e=>e.getClientRects().length && !e.textContent.trim() && !e.getAttribute('aria-label') && !e.id && !e.getAttribute('placeholder')).length")
            assert unnamed==0
            await page.keyboard.press('Tab')
            await page.get_by_role('button',name='Send',exact=True).focus()
            assert await page.get_by_role('button',name='Send',exact=True).evaluate("el=>getComputedStyle(el).outlineStyle")!='none'
            await page.get_by_role('button',name='Menu',exact=True).click()
            await page.get_by_role('link',name='Usage',exact=True).click()
            await page.get_by_role('heading',name='Usage',exact=True).wait_for()
            assert '00000000-0000-0000-0000-000000000061' in await page.inner_text('body')
            assert 'Cost: $0.00' in await page.inner_text('body')
            await page.goto(base+'/market-lab',wait_until='networkidle')
            await page.get_by_role('button',name='Menu',exact=True).click()
            await page.get_by_role('button',name='Plugins',exact=True).click()
            await dialog.get_by_role('tab',name='Files',exact=True).click()
            await dialog.locator('.ml-prow').filter(has_text='inventory.csv').get_by_role('button',name='Remove',exact=True).click()
            await dialog.get_by_text('No files stored. Choose files to upload your first source.',exact=True).wait_for()
            removed=await page.goto(base+'/market-lab/sources/00000000-0000-0000-0000-000000000051')
            assert removed.status==404
            assert not external and not errors, (external,errors)
            await context.close()
        finally:
            try:os.killpg(process.pid,signal.SIGTERM)
            except ProcessLookupError:pass
            try:process.wait(timeout=15)
            except subprocess.TimeoutExpired:os.killpg(process.pid,signal.SIGKILL);process.wait()
