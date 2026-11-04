const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const {createRequire} = require('node:module');
const root = path.resolve(__dirname, '..');
const ts = createRequire(path.join(root, 'workspace/package.json'))('typescript');
const source = ts.transpileModule(fs.readFileSync(path.join(root, 'workspace/app/base/download/route.ts'), 'utf8'), {compilerOptions: {module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022}}).outputText;
const id = '11111111-1111-4111-8111-111111111111';
const calls = [];
let status = 200;
const moduleValue = {exports: {}};
new Function('require', 'module', 'exports', source)(name => {
  if (name === '@/lib/tenant') return {currentTenant: async () => ({tenantId: id, userId: 'placeholder'})};
  if (name === '@/lib/workspace-origin') return {workspaceOrigin: () => 'https://app.tervory.com'};
  if (name === '@/lib/tank') return {commandRequest: async (_, route) => { calls.push(route); return new Response(status === 200 ? '\uFEFFname,website_source_url\r\nplaceholder,https://placeholder.example\r\n' : '{"detail":"placeholder"}', {status}); }};
  throw Error(name);
}, moduleValue, moduleValue.exports);
(async () => {
  let response = await moduleValue.exports.GET(new Request('https://app.tervory.com/base/download?campaign_id='+id));
  assert.equal(calls.at(-1), 'base/campaigns/csv?campaign_id='+id);
  assert.equal(response.headers.get('content-disposition'), 'attachment; filename="base-campaign.csv"');
  assert.equal(response.headers.get('cache-control'), 'private, no-store');
  assert.equal(response.headers.get('x-content-type-options'), 'nosniff');
  for (const failure of [403, 404, 409, 500]) {
    status = failure;
    response = await moduleValue.exports.GET(new Request('https://app.tervory.com/base/download?campaign_id='+id));
    assert.equal(response.status, failure);
    assert.equal(response.headers.get('content-disposition'), null);
  }
  const before = calls.length;
  response = await moduleValue.exports.GET(new Request('https://app.tervory.com/base/download?campaign_id=invalid'));
  assert.equal(response.status, 400);
  assert.equal(calls.length, before);
  console.log('Campaign download routes, private headers and errors verified.');
})();
