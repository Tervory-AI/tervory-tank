/* Reuse the actual Chromium screen/widget journey; extend its fake boundaries. */
const fs=require('node:fs'), path=require('node:path'), Module=require('node:module'), assert=require('node:assert/strict');
const filename=path.resolve(__dirname,'../trigger_w4/browser.cjs');
let source=fs.readFileSync(filename,'utf8');
function replace(oldText,newText){assert.equal(source.split(oldText).length,2,oldText);source=source.replace(oldText,newText);}
replace('let proposed = [],', "let mode='normal', executions=0; const completed=new Map();\nlet proposed = [],");
replace("detail=params.has('detail');", "detail=params.has('detail'),zero=params.has('zero');");
replace('{items:[record]}', '{items:zero?[]:[record]}');
replace("else{const data=", "else{let data=");
replace(';child=<View', ";if(zero)data={posts:[],reviews:[],sources:[],conversations:[],settings:{name:'placeholder store',enabled:false}};child=<View");
replace('return res.end(output);', 'res.setHeader("Content-Encoding","gzip");return res.end(require("node:zlib").gzipSync(output));');
replace('const data = body ? JSON.parse(body) : {};', `const data = body ? JSON.parse(body) : {};
    if(url.pathname==='/placeholder/control'){mode=data.mode;if(data.reset){completed.clear();executions=0;confirmed=0;}return json({mode,executions,confirmed});}
    if(url.pathname==='/placeholder/propose' && mode==='error'){res.statusCode=503;return json({error:'placeholder private provider credential'});}
    if(url.pathname==='/placeholder/confirm' && mode==='confirm-error'){res.statusCode=503;return json({error:'placeholder private provider credential'});}`);
replace('if (data.action === "confirm") confirmed++;', `if(data.action==='confirm') {confirmed++;if(!completed.has(id)){completed.set(id,true);executions++;}}`);
replace('status: data.action === "confirm" ? "confirmed" : "cancelled",', 'status: data.action === "confirm" ? "confirmed" : "cancelled", ledger_id:id,');
replace("return(await fetch('/placeholder/propose',{method:'POST',body:JSON.stringify({tool,arguments_})})).json()", "const r=await fetch('/placeholder/propose',{method:'POST',body:JSON.stringify({tool,arguments_})});if(!r.ok)throw Error(await r.text());return r.json()");
replace("return(await fetch('/placeholder/confirm',{method:'POST',body:JSON.stringify({action})})).json()", "const r=await fetch('/placeholder/confirm',{method:'POST',body:JSON.stringify({action})});if(!r.ok)throw Error(await r.text());return r.json()");
replace('executablePath: "/usr/bin/google-chrome"', 'executablePath: process.env.READ1_CHROMIUM_EXECUTABLE || "/usr/bin/chromium"');
replace('const evidence = path.join(__dirname, "evidence");', 'const evidence=process.env.TRIGGER_LAUNCH_EVIDENCE_DIR;');
replace('assert.deepEqual(errors, []);', `assert.deepEqual(errors, []);
    await page.route('**/*', route => new URL(route.request().url()).hostname==='127.0.0.1' || new URL(route.request().url()).hostname==='localhost' ? route.continue() : route.abort());
    const cdp=await page.context().newCDPSession(page);
    await cdp.send('Network.enable');
    await page.addInitScript(()=>{window.launchShift=0;new PerformanceObserver(list=>{for(const e of list.getEntries())if(!e.hadRecentInput)window.launchShift+=e.value;}).observe({type:'layout-shift',buffered:true});});
    for(const width of [1440,375]) {
      await cdp.send('Emulation.setCPUThrottlingRate',{rate:width===375?4:1});
      await cdp.send('Network.emulateNetworkConditions',{offline:false,latency:width===375?150:0,downloadThroughput:width===375?200000:-1,uploadThroughput:width===375?93750:-1});
      await page.setViewportSize({width,height:812});
      for(const kind of ['leads','contacts','estimates','invoices','channels','calendar','composer','reviews','inbox','settings']) {
        const started=Date.now();
        await page.goto(origin+'/?kind='+kind+'&zero=1');
        await page.locator('h1').waitFor();
        await page.evaluate(()=>document.fonts.ready);
        assert(Date.now()-started<10000,kind+' exceeds existing 10s read budget');
        assert(await page.evaluate(()=>window.launchShift<=.1),kind+' layout shift');
        const badContrast=await page.locator('.trigger-field-label,button:not(:disabled),a').evaluateAll(nodes=>{
          const rgb=s=>s.slice(s.indexOf('(')+1,s.indexOf(')')).split(',').slice(0,3).map(Number);
          const luminance=c=>c.map(x=>{x/=255;return x<=.04045?x/12.92:((x+.055)/1.055)**2.4;}).reduce((sum,x,i)=>sum+x*[.2126,.7152,.0722][i],0);
          return nodes.filter(n=>{if(!n.getClientRects().length||n.closest('[aria-disabled=true]'))return false;let p=n,bg;while(p){const s=getComputedStyle(p);if(s.backgroundColor!=='rgba(0, 0, 0, 0)'&&s.backgroundColor!=='transparent'){bg=rgb(s.backgroundColor);break;}p=p.parentElement;}bg=bg||[255,255,255];const s=getComputedStyle(n),fg=rgb(s.color);if(!fg.every(Number.isFinite)||!bg.every(Number.isFinite))throw Error('Unsupported computed color');const a=luminance(fg),b=luminance(bg);return (Math.max(a,b)+.05)/(Math.min(a,b)+.05)<4.5;}).map(n=>n.textContent.trim());
        });
        assert.deepEqual(badContrast,[],kind+' contrast');
        assert.equal(await page.locator('.trigger-first-action output').textContent(),'0');
        assert(await page.locator('.trigger-first-action').textContent());
        assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),true,kind+' day-zero overflow');
        if(['composer','settings','calendar'].includes(kind)) {
          const unlabelled=await page.locator('input:not([type=hidden]),textarea,select').evaluateAll(nodes=>nodes.filter(n=>!n.getAttribute('aria-label')&&!n.getAttribute('aria-labelledby')&&!n.labels?.length).length);
          assert.equal(unlabelled,0,kind+' unlabelled control');
        }
        if(width===375){
          await page.getByRole('button',{name:'Menu',exact:true}).focus();
          await page.keyboard.press('Enter');
          await page.getByRole('dialog',{name:'Trigger',exact:true}).waitFor();
          await page.keyboard.press('Escape');
          assert.equal(await page.getByRole('button',{name:'Menu',exact:true}).evaluate(n=>document.activeElement===n),true);
        }
      }
    }
    await cdp.send('Emulation.setCPUThrottlingRate',{rate:1});
    await cdp.send('Network.emulateNetworkConditions',{offline:false,latency:0,downloadThroughput:-1,uploadThroughput:-1});
    await page.setViewportSize({width:375,height:812});
    await page.goto(origin+'/?kind=settings&zero=1');
    await page.getByLabel('Greeting',{exact:true}).fill('placeholder authored greeting');
    await page.getByLabel('Time zone',{exact:true}).fill('America/Los_Angeles');
    await page.request.post(origin+'/placeholder/control',{data:{mode:'error',reset:true}});
    await page.getByRole('button',{name:'Save settings',exact:true}).click();
    await page.getByRole('alert').waitFor();
    assert(!(await page.locator('body').innerText()).includes('private provider credential'));
    await page.request.post(origin+'/placeholder/control',{data:{mode:'normal'}});
    await page.getByRole('button',{name:'Save settings',exact:true}).click();
    await page.getByRole('heading',{name:'Confirm · Settings'}).waitFor();
    await page.request.post(origin+'/placeholder/control',{data:{mode:'confirm-error'}});
    await page.getByRole('button',{name:'Confirm',exact:true}).click();
    await page.getByRole('alert').waitFor();
    assert.equal(await page.getByRole('heading',{name:'Confirm · Settings'}).count(),1);
    await page.request.post(origin+'/placeholder/control',{data:{mode:'normal'}});
    await page.getByRole('button',{name:'Confirm',exact:true}).evaluate(n=>{n.click();n.click();});
    await page.getByRole('heading',{name:'Settings',exact:true}).waitFor();
    await page.locator('a[href="/ledger?entry='+id+'"]').first().waitFor();
    const result=await(await page.request.post(origin+'/placeholder/control',{data:{mode:'normal'}})).json();
    assert.equal(result.executions,1,'same durable card executes once');
    assert.equal(result.confirmed,1,'double click sends one confirmation');
    assert.deepEqual(errors,[]);
    console.log('PASS launch journeys: zero-data, first action/result/receipt, provider error, safe retry, keyboard labels and mobile screens');`);
const script=new Module(filename);script.filename=filename;script.paths=Module._nodeModulePaths(path.dirname(filename));script._compile(source,filename);
