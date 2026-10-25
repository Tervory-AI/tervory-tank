// Exercise the real server helper without making a legal answer or a tenant fixture.
import assert from 'node:assert/strict';
import fs from 'node:fs';
import vm from 'node:vm';
import { createRequire } from 'node:module';

const require = createRequire(import.meta.url);
const ts = require('../workspace/node_modules/typescript');
const source = fs.readFileSync(new URL('../workspace/app/api/zenas/tank.ts', import.meta.url), 'utf8');
const code = ts.transpileModule(source, { compilerOptions: { target: ts.ScriptTarget.ES2022, module: ts.ModuleKind.CommonJS } }).outputText;
const question = 'Is a forum selection clause in a B2B supply contract enforceable in Delaware?';

for (const configured of [undefined, 'us-east', 'za', ' ZA ']) {
  const calls = [];
  const exports = {};
  const env = { TANK_REGION: configured, TANK_URL_ZA: 'https://za.tervory.com' };
  vm.runInNewContext(code, { exports, process: { env }, URL, URLSearchParams,
    fetch: async (url, options) => { calls.push({ url, options }); return new Response(null, { status: 204 }); } });
  assert.equal(exports.homeRegion(), 'us-east');
  assert.equal(exports.regionTank('za'), null);
  assert.equal(await exports.zenasIn('za', 'matters'), null);
  assert.equal(calls.length, 0);
  if (configured?.trim().toLowerCase() === 'za') {
    await assert.rejects(exports.zenas('answers', { method: 'POST', body: JSON.stringify({ question }) }));
    assert.equal(await exports.zenasIn('us-east', 'matters'), null);
    assert.equal(calls.length, 0);
    continue;
  }
  await exports.zenas('answers', { method: 'POST', body: JSON.stringify({ question }) });
  assert.equal(calls.length, 1);
  assert.equal(calls[0].url, 'http://tank:8000/v1/zenas/answers?home_region=us-east');
  assert.equal(JSON.parse(calls[0].options.body).home_region, 'us-east');
  assert.equal(JSON.parse(calls[0].options.body).question, question);
  assert.equal(calls[0].options.cache, 'no-store');
  for (const path of ['matters?home_region=za', 'matters?home_region=us-east&home_region=za']) {
    await assert.rejects(exports.zenas(path));
  }
  await assert.rejects(exports.zenas('matters', { method: 'POST', body: JSON.stringify({ home_region: 'za' }) }));
  assert.equal(calls.length, 1);
}
console.log('Zenas routing: Boston only; stopped ZA never reaches fetch.');
