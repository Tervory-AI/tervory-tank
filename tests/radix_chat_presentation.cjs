const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const root = path.resolve(__dirname, '..');
const base = path.join(root, 'workspace');
const ts = require(path.join(base, 'node_modules/typescript'));
require.extensions['.ts'] = (module, filename) => module._compile(ts.transpileModule(fs.readFileSync(filename, 'utf8'), { compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 } }).outputText, filename);
const {presentCard} = require('../workspace/app/chats/presentation.ts');
const findings = Array.from({length: 8}, (_, i) => ({tool:'zap', severity:'medium', rule:`rule-${i}`, file:'https://example.test/path', line:0, explanation:`Explanation ${i}`, remediation:`Fix ${i}`, tenant_id:'must-not-cross', raw_payload:{secret:'NEVER-EXPOSE'}}));
for (const founder of [false,true]) {
  const card = presentCard({summary:'Radix test',card_id:'one', kind:'other', tool:'radix.findings', arguments:{scan_id:'scan-123', tenant_id:'private'}, result:{findings, credential:'NEVER-EXPOSE'}, status:'confirmed'}, founder);
  assert.equal(card.radix.findings.length, 8);
  assert.equal(card.radix.findings[7].remediation, 'Fix 7');
  assert.equal(card.radix.scan_id, 'scan-123');
  assert(!JSON.stringify(card).includes('NEVER-EXPOSE'));
  assert(!JSON.stringify(card).includes('must-not-cross'));
  assert(!JSON.stringify(card).includes('first 5'));
  assert.equal(card.radix.status, undefined, 'findings response must not invent completion');
  const generic = presentCard({summary:'Radix test',card_id:'two', kind:'other', tool:'base.search', result:{findings}}, founder);
  assert.equal(generic.radix, undefined);
  assert(generic.results.some(item => item.value.includes('first 5')));
}
const proof = presentCard({summary:'Radix test',card_id:'p',kind:'other',tool:'radix.domain.prove',arguments:{domain:'example.test'},result:{name:'_tervory-verify.example.test',value:'tervory-public-proof',expires_at:'2026-11-02T00:00:00Z',TANK_API_KEY:'NEVER-EXPOSE'}},false);
assert.equal(proof.radix.value,'tervory-public-proof');assert.equal(proof.radix.domain,'example.test');assert(!JSON.stringify(proof).includes('NEVER-EXPOSE'));
const malformed = presentCard({summary:'Radix test',card_id:'x',kind:'other',tool:'radix.findings', result:{findings:[null, {explanation:{secret:'hidden'},remediation:'<script>alert(1)</script>'}]}},false);
assert.equal(malformed.radix.findings[1].explanation,undefined);
assert.equal(malformed.radix.findings[1].remediation,'<script>alert(1)</script>'); // React text, never markup.
console.log('PASS Radix allowlist, eight findings, no invented status, non-Radix compatibility, malformed/hostile data');

const scan = presentCard({summary:"Scan",card_id:"scan",kind:"other",tool:"radix.passive.scan",arguments:{url:"https://example.test/",commit:"abc"},result:{scan_id:"real-scan"}},false);
assert.equal(scan.radix.target,"https://example.test/");assert.equal(scan.radix.scan_id,"real-scan");
