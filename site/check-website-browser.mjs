// Static public pages; use an isolated preview, never the production signup store.
// Sweeps every integer width, not just selected device presets.
import assert from "node:assert/strict";
import { mkdir, writeFile } from "node:fs/promises";
import { pathToFileURL } from "node:url";

const { chromium } = await import(pathToFileURL(process.env.PLAYWRIGHT_MODULE).href);
const browser = await chromium.launch({ executablePath: process.env.BROWSER_EXECUTABLE, args: ["--no-sandbox"] });
const origin = process.env.HOMEPAGE_URL || "http://127.0.0.1:8947";
const output = process.env.SCREENSHOT_DIR || "../docs/screenshots/homepage-wave4";
const routes = (process.env.WEBSITE_ROUTES || "/,/rig").split(",");
const context = await browser.newContext({ reducedMotion: "reduce", viewport: { width:1440, height:1000 } });
const page = await context.newPage();
const errors = [];
const posts = [];
page.on("pageerror", error => errors.push(error.message));
page.on("request", request => { if(request.method()==="POST") posts.push(request.url()); });
const results = [];
await mkdir(output,{recursive:true});

// Ignore the homepage receipt's intentional horizontal table scroller. Artwork
// can bleed outside its box; text and controls cannot. checkVisibility excludes
// the desktop/mobile alternative that CSS hides at the current width.
function layoutFailures() {
  const failures = [];
  if(document.documentElement.scrollWidth > innerWidth) failures.push("Page wider than viewport");
  const walker = document.createTreeWalker(document.body,NodeFilter.SHOW_TEXT);
  while(walker.nextNode()) {
    const node = walker.currentNode;
    const element = node.parentElement;
    if(!node.textContent.trim() || element.closest("script,style,.skip,.visually-hidden,table") || !element.checkVisibility()) continue;
    const range = document.createRange(); range.selectNodeContents(node);
    const bounds = element.getBoundingClientRect();
    for(const rect of range.getClientRects()) {
      if(rect.width===0 || rect.height===0) continue;
      if(rect.left < -.5 || rect.right > innerWidth+.5) failures.push(`Text outside viewport: ${node.textContent.trim()}`);
      if(rect.left < bounds.left-.5 || rect.right > bounds.right+.5) failures.push(`Text outside its element: ${node.textContent.trim()}`);
      const panel = element.closest(".rp-panel,.rp-step,.rp-supplier,.rp-outcome");
      if(panel) { const box=panel.getBoundingClientRect(); if(rect.left<box.left-.5 || rect.right>box.right+.5) failures.push(`Text outside Rig panel: ${node.textContent.trim()}`); }
    }
  }
  for(const element of document.querySelectorAll("button,input,a.rp-button")) {
    if(!element.checkVisibility() || element.closest("table")) continue;
    const box=element.getBoundingClientRect();
    if(box.left<-.5 || box.right>innerWidth+.5) failures.push(`Control outside viewport: ${element.textContent.trim() || element.id}`);
  }
  if(document.querySelector(".homepage")) {
    const tags=[...document.querySelectorAll('.rig-switches .tag')];
    if(tags.length!==4 || tags.some(tag=>!tag.checkVisibility())) failures.push("Four Optional tags must remain visible");
  }
  return [...new Set(failures)];
}

try {
  for(const route of routes) {
    assert.equal((await page.goto(origin+route,{waitUntil:"networkidle"})).status(),200);
    await page.evaluate(()=>document.fonts.ready);
    await page.locator("img").evaluateAll(async images=>{ for(const image of images) image.loading="eager"; await Promise.all(images.map(image=>image.decode())); });
    const name=route==="/"?"homepage":"rig-product";
    if(route==="/rig") {
      assert.equal(await page.locator('link[rel="canonical"]').getAttribute("href"),"https://tervory.com/rig");
      assert.equal(await page.locator("h1").count(),1);
      assert.equal(await page.locator(".rp-primary").evaluate(e=>getComputedStyle(e).backgroundColor),"rgb(232, 0, 8)");
      assert.equal(await page.locator(".rp-benefit-list article").count(),4);
      assert.equal(await page.locator(".rp-step>button").count(),7);
      for(const link of await page.locator('a[href^="#"]').all()) assert.equal(await page.locator(await link.getAttribute("href")).count(),1);
      for(const width of [320,375,390,430,767,768,1000,1199,1200,1440]) {
        await page.setViewportSize({width,height:1000});
        for(let stage=0;stage<7;stage++) {
          await page.locator(".rp-step>button").nth(stage).click();
          assert.equal(await page.locator(".rp-step>button").nth(stage).getAttribute("aria-pressed"),"true");
          assert.deepEqual(await page.evaluate(layoutFailures),[],`${name}, stage ${stage+1}, width ${width}`);
        }
        await page.locator(".rp-step>button").nth(2).click();
        await page.locator(".rp-step>button").nth(2).focus();
        await page.keyboard.press("ArrowRight");
        assert.equal(await page.locator(".rp-step>button").nth(3).getAttribute("aria-pressed"),"true");
        await page.keyboard.press("Home");
        assert.equal(await page.locator(".rp-step>button").first().getAttribute("aria-pressed"),"true");
        await page.keyboard.press("End");
        assert.equal(await page.locator(".rp-step>button").last().getAttribute("aria-pressed"),"true");
      }
      await page.locator(".rp-step>button").nth(2).click();
      await page.getByRole("button",{name:"Accept & secure stock",exact:true}).click();
      assert.equal(await page.locator(".rp-step>button").nth(3).getAttribute("aria-pressed"),"true");
      await page.locator(".rp-step>button").nth(2).click();
      await page.locator("#basket-value").fill("900");
      assert.equal(await page.locator('label[for="basket-value"] output').textContent(),"$900");
      await page.locator("#basket-value").fill("690");
    }
    for(let width=320;width<=1440;width++) {
      await page.setViewportSize({width,height:1000});
      const failures=await page.evaluate(layoutFailures);
      assert.deepEqual(failures,[],`${name}: ${width}px`);
      if([320,375,390,430,767,768,1000,1199,1200,1440].includes(width)) {
        await page.screenshot({path:`${output}/${name}-${width}.png`,fullPage:true});
      }
    }
    const result={route,widths:{from:320,to:1440,step:1,count:1121},result:"pass"};
    results.push(result);
    await writeFile(`${output}/${name}-width-sweep.json`,JSON.stringify(result,null,2)+"\n");
    console.log(`${name}: all 1,121 widths passed (320–1440)`);
  }
  assert.deepEqual(errors,[]);
  assert.deepEqual(posts,[],"Illustrations must never send a payment/order/model request");
  await writeFile(`${output}/width-sweep.json`,JSON.stringify({results,consoleErrors:errors,illustrationPosts:posts},null,2)+"\n");
} finally { await browser.close(); }
