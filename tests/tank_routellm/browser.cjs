// Render the production component with the real local Tank report, not a mock UI.
const fs = require('node:fs');
const path = require('node:path');
const http = require('node:http');
const assert = require('node:assert/strict');
const ts = require('../../workspace/node_modules/typescript');
const React = require('../../workspace/node_modules/react');
const { renderToStaticMarkup } = require('../../workspace/node_modules/react-dom/server');
const { chromium } = require('playwright');
const root = path.resolve(__dirname, '../..');
function load(relative) {
  const source = fs.readFileSync(path.join(root, relative), 'utf8');
  const compiled = ts.transpileModule(source, { compilerOptions: {
    module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022, jsx: ts.JsxEmit.ReactJSX,
  }}).outputText;
  const loaded = { exports: {} };
  const localRequire = name => name === './savings-types' ? load('workspace/app/tank/proof/savings-types.ts')
    : name === 'react/jsx-runtime' ? require('../../workspace/node_modules/react/jsx-runtime') : require(name);
  new Function('module', 'exports', 'require', compiled)(loaded, loaded.exports, localRequire);
  return loaded.exports;
}
(async () => {
  const { ProofView } = load('workspace/app/tank/proof/view.tsx');
  const data = JSON.parse(fs.readFileSync(path.join(__dirname, 'evidence/report.json'), 'utf8'));
  const markup = renderToStaticMarkup(React.createElement(ProofView, { data, task: 'routellm.proof' }));
  const css = fs.readFileSync(path.join(root, 'workspace/app/tank/proof/proof.css'), 'utf8');
  const server = http.createServer((req, res) => {
    res.setHeader('Content-Type', 'text/html; charset=utf-8');
    res.end(`<!doctype html><meta name="viewport" content="width=device-width, initial-scale=1"><style>body{margin:0;padding:16px;font-family:Arial;color:#001840}*{box-sizing:border-box}${css}</style>${markup}`);
  });
  await new Promise(resolve => server.listen(0, '127.0.0.1', resolve));
  const browser = await chromium.launch({ executablePath: process.env.CHROMIUM_PATH || '/usr/bin/chromium', args: ['--no-sandbox'] });
  try {
    const page = await browser.newPage();
    for (const width of [1440, 375]) {
      await page.setViewportSize({ width, height: 1000 });
      await page.goto(`http://127.0.0.1:${server.address().port}/tank/proof`);
      const comparison = page.locator('.proof-pair');
      assert.match(await comparison.innerText(), /\$0\.020000 − \$0\.002000 = \$0\.018000/);
      assert.match(await comparison.innerText(), /1 pairs · 100\.0% agreement/);
      await comparison.locator('a').last().click();
      assert.equal(new URL(page.url()).hash, '#shadows');
      assert.match(await page.locator('#shadows').innerText(), /routellm:flash-lite:/);
      await page.locator('.proof-task').filter({ has: page.locator('.proof-pair') }).screenshot({ path: path.join(__dirname, `evidence/savings-${width}.png`) });
    }
    console.log('Passed: production savings component, measured equation, agreement, evidence link; 1440px and 375px local screenshots.');
  } finally {
    await browser.close();
    await new Promise(resolve => server.close(resolve));
  }
})().catch(error => { console.error(error); process.exitCode = 1; });
