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
const proof = presentCard({summary:'Radix test',card_id:'p',kind:'other',tool:'radix.domain.prove',arguments:{domain:'example.test'},result:{name:'_tervory-verify.example.test',value:'tervory-public-proof',expires_at:'2026-11-02T00:00:00Z',TANK_API_KEY:'placeholder-NEVER-EXPOSE'}},false);
assert.equal(proof.radix.value,'tervory-public-proof');assert.equal(proof.radix.domain,'example.test');assert(!JSON.stringify(proof).includes('NEVER-EXPOSE'));
const malformed = presentCard({summary:'Radix test',card_id:'x',kind:'other',tool:'radix.findings', result:{findings:[null, {explanation:{secret:'hidden'},remediation:'<script>alert(1)</script>'}]}},false);
assert.equal(malformed.radix.findings[1].explanation,undefined);
assert.equal(malformed.radix.findings[1].remediation,'<script>alert(1)</script>'); // React text, never markup.
console.log('PASS Radix allowlist, eight findings, no invented status, non-Radix compatibility, malformed/hostile data');

const scan = presentCard({summary:"Scan",card_id:"scan",kind:"other",tool:"radix.passive.scan",arguments:{url:"https://example.test/",commit:"abc"},result:{scan_id:"real-scan"}},false);
assert.equal(scan.radix.target,"https://example.test/");assert.equal(scan.radix.scan_id,"real-scan");

for (const founder of [false, true]) {
  const repo = presentCard({summary:'radix.repo.findings',card_id:'repo',kind:'other',tool:'radix.repo.findings',arguments:{scan_id:'placeholder-repo-id'},status:'confirmed',result:{
    scan_id:'placeholder-repo-id',status:'complete',findings:[...findings,{tool:'scan.iac',severity:'unknown',rule:'CKV_AWS_24',file:'open.tf',line:7,remediation:'placeholder Checkov text'}],
    summary:'placeholder-summary-hidden',critical:98765,tools:['placeholder-hidden-tools'],tool_status:{'scan.iac':'run'},scan_complete:true,
    ledger_id:'placeholder-hidden-ledger',cost_usd:0,
  }},founder);
  assert.equal(repo.radix.kind,'findings');
  assert.equal(repo.radix.findings.length,9);
  assert.equal(repo.radix.findings[8].severity,'unknown');
  assert.equal(repo.radix.findings[8].remediation,'placeholder Checkov text');
  assert.equal(repo.radix.critical,undefined);
  assert.deepEqual(repo.results,[]);
  for (const hidden of ['placeholder-summary-hidden','98765','placeholder-hidden-tools','tool_status','scan_complete','placeholder-hidden-ledger']) assert(!JSON.stringify(repo).includes(hidden));
  for (const status of ['pending','running','failed','complete']) {
    const projected = presentCard({summary:'radix.repo.findings',card_id:'state',kind:'other',tool:'radix.repo.findings',result:{scan_id:'placeholder-id',status}},founder);
    assert.equal(projected.radix.status,status);
    assert.equal(projected.radix.findings,undefined);
  }
  const queued = presentCard({summary:'radix.repo.scan',card_id:'queued',kind:'other',tool:'radix.repo.scan',result:{scan_id:'placeholder-job-id',status:'pending'}},founder);
  assert.equal(queued.radix.kind,'scan');
  assert.equal(queued.radix.scan_id,'placeholder-job-id');
  assert.equal(queued.radix.status,'pending');
  const empty = presentCard({summary:'radix.repo.findings',card_id:'empty',kind:'other',tool:'radix.repo.findings',result:{scan_id:'placeholder-job-id',status:'complete',findings:[]}},founder);
  assert.deepEqual(empty.radix.findings,[]);
}
console.log('PASS repo tools reuse approved states, unknown severity, nine findings and hidden operational fields');

for (const founder of [false, true]) {
  for (const [scan_complete, rows, expected] of [[false, [], 'failed'], [true, [], 'complete'], [false, findings, 'complete']]) {
    const card = presentCard({summary:'radix.repo.findings',card_id:'placeholder-completion',kind:'other',tool:'radix.repo.findings',status:'confirmed',result:{
      scan_id:'placeholder-id',status:'complete',scan_complete,findings:rows,
      tool_status:{'scan.iac':scan_complete?'run':'not run'},
    }},founder);
    assert.equal(card.radix.status,expected);
    assert.equal(card.radix.findings.length,rows.length);
    assert(!JSON.stringify(card).includes('scan_complete'));
  }
}
console.log('PASS empty incomplete scans use failed state; complete empty scans and partial findings retain their approved states');
