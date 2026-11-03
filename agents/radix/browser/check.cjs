// No clicks, consent, cookie values, HTML evidence, or external tool updates.
const { chromium } = require('playwright');
const AxeBuilder = require('@axe-core/playwright').default;
(async () => {
  const target = new URL(process.argv[2]);
  if (target.protocol !== 'https:' || target.port || target.pathname !== '/' || target.search || target.username || target.password) throw Error('invalid target');
  const browser = await chromium.launch({headless:true, proxy:{server:'http://radix-passive-proxy:8082'}, args:[
    '--proxy-bypass-list=<-loopback>','--disable-quic','--disable-background-networking','--disable-component-update',
    '--force-webrtc-ip-handling-policy=disable_non_proxied_udp',
    '--host-resolver-rules=MAP * ~NOTFOUND, EXCLUDE radix-passive-proxy'
  ]});
  try {
    const context = await browser.newContext({serviceWorkers:'block', ignoreHTTPSErrors:true});
    const observed = [];
    const firstParty = domain => target.hostname === domain.replace(/^\./,'') || target.hostname.endsWith('.'+domain.replace(/^\./,''));
    const metadata = (raw, url) => {
      const parts=raw.split(';').map(p=>p.trim()), u=new URL(url), attrs={};
      for (const p of parts.slice(1)) {const at=p.indexOf('='); attrs[(at<0?p:p.slice(0,at)).toLowerCase()]=at<0?'':p.slice(at+1);}
      const domain=attrs.domain || u.hostname;
      return {name:parts[0].split('=',1)[0],domain,path:attrs.path || u.pathname.slice(0,u.pathname.lastIndexOf('/')+1) || '/',
        expiry:attrs['max-age'] ? Date.now()/1000+Number(attrs['max-age']) : attrs.expires ? Date.parse(attrs.expires)/1000 : -1,
        Secure:'secure' in attrs,HttpOnly:'httponly' in attrs,SameSite:attrs.samesite || 'Lax',first_party:firstParty(domain)};
    };
    await context.addInitScript(() => {
      const original=Object.getOwnPropertyDescriptor(Document.prototype,'cookie'), events=[];
      Object.defineProperty(window,'__radix_cookie_metadata',{value:events});
      Object.defineProperty(document,'cookie',{get(){return original.get.call(this);},set(raw){
        original.set.call(this,raw);
        const parts=String(raw).split(';').map(p=>p.trim()),attrs={};
        for(const p of parts.slice(1)){const at=p.indexOf('=');attrs[(at<0?p:p.slice(0,at)).toLowerCase()]=at<0?'':p.slice(at+1);}
        events.push({name:parts[0].split('=',1)[0],domain:attrs.domain||location.hostname,
          path:attrs.path||location.pathname.slice(0,location.pathname.lastIndexOf('/')+1)||'/',
          expiry:attrs['max-age']?Date.now()/1000+Number(attrs['max-age']):attrs.expires?Date.parse(attrs.expires)/1000:-1,
          Secure:'secure' in attrs,HttpOnly:false,SameSite:attrs.samesite||'Lax'});
      }});
    });
    const page = await context.newPage();
    const responses=[];
    page.on('response', response=>responses.push((async()=>{
      for(const h of await response.headersArray()) if(h.name.toLowerCase()==='set-cookie') observed.push(metadata(h.value,response.url()));
    })()));
    let refused = 0, clientRefused = 0;
    await context.routeWebSocket('**/*', route => {clientRefused++; route.close();});
    await context.route('**/*', async route => {
      const u = new URL(route.request().url());
      if (u.protocol !== 'https:' || (u.port && u.port !== '443') || u.username || u.password) {
        clientRefused++; return route.abort();
      }
      return route.continue(); // Other hosts are attempted only via the exact-host proxy.
    });
    page.on('requestfailed', request => {
      const u = new URL(request.url());
      if (u.hostname !== target.hostname && u.protocol === 'https:' && !u.port) refused++;
    });
    const response = await page.goto(target.href, {waitUntil:'domcontentloaded',timeout:20000});
    if (!response || response.status() !== 200 || new URL(page.url()).hostname !== target.hostname) throw Error('page incomplete');
    await page.waitForTimeout(1000);
    const result = process.argv[3] === 'notice-only' ? {violations:[]} : await new AxeBuilder({page}).analyze();
    await Promise.all(responses);
    const scriptCookies=await page.evaluate(()=>window.__radix_cookie_metadata || []);
    observed.push(...scriptCookies.map(c=>({...c,first_party:firstParty(c.domain)})));
    const cookies = [...observed,...(await context.cookies()).map(c => ({name:c.name, domain:c.domain, path:c.path,
      expiry:c.expires, Secure:c.secure, HttpOnly:c.httpOnly, SameSite:c.sameSite,
      first_party:target.hostname === c.domain.replace(/^\./,'') || target.hostname.endsWith('.'+c.domain.replace(/^\./,''))}))];
    const findings = result.violations.filter(v=>['serious','critical'].includes(v.impact)).flatMap(v=>v.nodes.map(n=>({
      tool:'axe-core',rule:v.id,severity:v.impact,item:JSON.stringify(n.target),file:target.href,line:0,
      explanation:v.help,remediation:v.helpUrl,facts:{page:target.href,rule:v.id,element:n.target,help:v.help,helpUrl:v.helpUrl}
    })));
    process.stdout.write(JSON.stringify({findings,cookies,third_party_refused:refused,client_refused:clientRefused}));
    await context.close();
  } finally { await browser.close(); }
})().catch(()=>{process.stderr.write('browser check incomplete\n');process.exitCode=1;});
