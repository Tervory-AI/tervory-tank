const assert = require('node:assert/strict');
const http = require('node:http');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const { browserChecks, proxyFor } = require('../agents/tisan/templates/next-site/scripts/quality-check.cjs');
const { chromium } = require('../agents/tisan/templates/next-site/node_modules/playwright');
const { visualChecks } = require('../agents/tisan/templates/next-site/scripts/visual-check.cjs');
(async () => {
  const server = http.createServer((_req, res) => {
    res.setHeader('Content-Type', 'text/html');
    res.end('<!DOCTYPE html><html lang="en"><head><title>placeholder</title></head><body><style>:root{--ink:#001840}body{margin:0}h1{position:absolute;left:16px;top:32px;width:200px;height:40px;margin:0;color:var(--ink)}</style><h1>placeholder</h1>');
  });
  await new Promise(resolve => server.listen(0, '127.0.0.1', resolve));
  const origin = `http://127.0.0.1:${server.address().port}`;
  const browser = await chromium.launch();
  const frames = [375, 1440].map(width => ({page:'/',frameId:`fixture-${width}`,width,height:900,
    tokens:{'--ink':'#001840'},elements:[{nodeId:'heading',selector:'h1',
      box:{x:16,y:32,width:200,height:40},text:'placeholder',colours:{color:'--ink'}}]}));
  try {
    assert.equal((await visualChecks(browser, origin, frames)).ok, true);
    const changed = structuredClone(frames);
    changed[0].elements[0].text = 'changed';
    assert.equal((await visualChecks(browser, origin, changed)).ok, false);
    changed[0].elements[0].text = 'placeholder';
    changed[1].elements[0].box.x = 50;
    assert.equal((await visualChecks(browser, origin, changed)).ok, false);
    assert.equal((await visualChecks(browser, origin, [])).ok, false);
    const directory = fs.mkdtempSync(path.join(os.tmpdir(), 'tisan-visual-'));
    const previous = process.cwd();
    const proxy = proxyFor(origin);
    await new Promise(resolve => proxy.listen(0, '127.0.0.1', resolve));
    try {
      process.chdir(directory);
      fs.mkdirSync('visual');
      fs.writeFileSync('visual/frames.json', JSON.stringify(changed));
      const [accessibility] = await browserChecks(origin, ['/'], `http://127.0.0.1:${proxy.address().port}`);
      assert.equal(accessibility.visual.ok, false);
      assert.equal(accessibility.ok, false);
      assert.equal(accessibility.summary, 'frame data incomplete');
    } finally {
      process.chdir(previous);
      await new Promise(resolve => { proxy.close(resolve); proxy.closeAllConnections(); });
      fs.rmSync(directory, {recursive:true});
    }
    console.log('visual comparisons passed');
  } finally {
    await browser.close();
    await new Promise(resolve => server.close(resolve));
  }
})().catch(error => { console.error(error); process.exitCode = 1; });
