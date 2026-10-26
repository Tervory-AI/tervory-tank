// Browser proof over the real components and local Postgres fixture records.
import assert from 'node:assert/strict';
import fs from 'node:fs/promises';
import path from 'node:path';
import {fileURLToPath, pathToFileURL} from 'node:url';
import {parseArgs} from 'node:util';
const {values} = parseArgs({options:{playwright:{type:'string'},browser:{type:'string',default:'/usr/bin/chromium'},base:{type:'string',default:'http://127.0.0.1:3046'},output:{type:'string'}}});
const root=path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../../..');
const base=new URL(values.base);
assert(['127.0.0.1','localhost'].includes(base.hostname),'Fixture proof only runs on loopback');
assert(values.playwright,'Pass --playwright with the installed Playwright module path');
const playwright=await import(pathToFileURL(path.resolve(values.playwright)).href);
const {chromium}=playwright.default ?? playwright;
const output=path.resolve(values.output || path.join(root,'agents/market_lab/evidence'));
await fs.mkdir(output,{recursive:true});
const browser=await chromium.launch({executablePath:values.browser,headless:true,args:['--no-sandbox']});
const question='What are the latest population figures for California?';
const report={label:'local, fixture page',question,widths:[],screenshots:[],citations:[],browserErrors:[],externalRequests:[]};
const seenCitations=new Set();
try{
  for(const width of [1440,375]){
    const context=await browser.newContext({viewport:{width,height:1000}});
    await context.route('**/*',route=>{
      const url=new URL(route.request().url());
      if(['http:','https:'].includes(url.protocol) && url.origin!==base.origin){
        report.externalRequests.push(url.hostname);
        return route.abort();
      }
      return route.continue();
    });
    const page=await context.newPage();
    page.on('pageerror',error=>report.browserErrors.push(error.message));
    const screenshot=async(name)=>{
      assert(await page.getByText('local, fixture page',{exact:true}).isVisible());
      await page.screenshot({path:path.join(output,`${name}-${width}.png`)});
      report.screenshots.push(`${name}-${width}.png`);
    };
    assert.equal((await page.goto(new URL('/market-lab',base).href)).status(),200);
    await page.getByRole('heading',{name:'Market Lab',exact:true}).waitFor();
    await page.locator('.ml-card').first().waitFor();
    await page.evaluate(()=>document.fonts.ready);
    assert.equal(await page.locator('.ml-counts .ml-count').first().innerText(),'14');
    assert.equal(await page.locator('.ml-card').count(),14);
    await screenshot('feeds');
    await page.getByRole('textbox',{name:'Ask Market Lab',exact:true}).fill(question);
    await screenshot('question');
    const received=page.waitForResponse(r=>r.url()===new URL('/market-lab/ask',base).href&&r.request().method()==='POST');
    await page.getByRole('button',{name:'Send',exact:true}).click();
    const response=await received;
    assert.equal(response.status(),200);
    const brief=await response.json();
    assert(brief.facts.length>0,'Question must be answered from stored rows');
    await page.locator('.ml-answer .ml-lines a').first().waitFor();
    assert.equal(await page.locator('.ml-answer .ml-lines a').count(),brief.facts.length);
    // Every numeric statement in the brief is entirely inside its source link.
    const uncited=await page.locator('.ml-answer').evaluate(node=>{
      const copy=node.cloneNode(true);
      copy.querySelectorAll('a').forEach(link=>link.remove());
      return copy.textContent;
    });
    assert(!/\d/.test(uncited),'No uncited number may remain in the brief');
    await page.locator('.ml-chat').evaluate(node=>node.scrollIntoView({block:'start'}));
    await screenshot('brief');
    for(const fact of brief.facts){
      assert.match(fact.href,/^\/market-lab\/sources\/[0-9a-f-]+\?row=\d+#point-\d+$/);
      const source=await context.newPage();
      assert.equal((await source.goto(new URL(fact.href,base).href)).status(),200);
      const id=new URL(fact.href,base).hash;
      const row=source.locator(id);
      await row.waitFor();
      const cells=await row.locator('th,td').allTextContents();
      assert(fact.text.includes(cells[0]),'Cited title must match');
      assert(fact.text.includes(cells[2]),'Cited date must match');
      assert(fact.text.replaceAll(',','').includes(cells[3]),'Cited value must match');
      assert(fact.text.includes(cells[4]),'Cited unit must match');
      if(!seenCitations.has(fact.href)){
        seenCitations.add(fact.href);
        report.citations.push({statement:fact.text,href:fact.href,storedRow:cells});
      }
      await source.close();
    }
    // Open the real citation from the browser's answer and capture the source.
    await page.locator('.ml-answer .ml-lines a').first().click();
    await page.getByRole('heading',{name:'Stored observations'}).waitFor();
    await page.locator(':target').scrollIntoViewIfNeeded();
    await screenshot('source');
    assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),'No horizontal page overflow');
    report.widths.push(width);
    await context.close();
  }
  assert.deepEqual(report.browserErrors,[]);
  assert.deepEqual(report.externalRequests,[]);
  report.result='passed';
  await fs.writeFile(path.join(output,'browser-proof.json'),JSON.stringify(report,null,2)+'\n');
  console.log(`Local fixture page: ${report.screenshots.length} screenshots, ${report.citations.length} exact citations, no external browser requests or errors.`);
} finally { await browser.close(); }
