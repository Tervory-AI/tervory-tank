// Exercise the actual access handler across Coolify's HTTPS-to-HTTP boundary.
const fs = require('node:fs'), path = require('node:path'), vm = require('node:vm');
const assert = require('node:assert/strict');
const root = path.resolve(__dirname, '..');
const ts = require(path.join(root, 'workspace/node_modules/typescript'));
const source = fs.readFileSync(path.join(root, 'workspace/app/access/api/[...path]/route.ts'), 'utf8');
const calls = [], moduleResult = { exports: {} };
vm.runInNewContext(ts.transpileModule(source, {compilerOptions: {module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022}}).outputText, {
  exports: moduleResult.exports, URL, require(name) {
    if (name === 'next/server') return {NextResponse: {json: (body, init) => Response.json(body, init)}};
    if (name === '@/lib/tank') return {accessRequest: async (actor, route, body) => {calls.push({actor, route, body}); return {ok: true};}};
    if (name === '../../identity') return {accessIdentity: async () => ({tenantId: 'server-tenant', userId: 'server-user'})};
    throw new Error('Unexpected import');
  },
});
(async () => {
  for (const origin of ['https://app.tervory.com', 'https://foreign.example', 'null', '', 'https://app.tervory.com:444']) {
    const url = new URL('http://workspace:3000/access/api/revoke');
    const request = new Request(url, {method: 'POST', headers: {origin, host: 'app.tervory.com'}, body: JSON.stringify({room: 'base', site: 'https://dealer.example'})});
    request.nextUrl = url;
    const response = await moduleResult.exports.POST(request, {params: Promise.resolve({path: ['revoke']})});
    assert.equal(response.status, origin === 'https://app.tervory.com' ? 200 : 403);
  }
  assert.equal(calls.length, 1);
  assert.equal(calls[0].actor.tenantId, 'server-tenant');
  console.log('Access route permits the public host through TLS termination and rejects foreign, missing and malformed origins.');
})().catch(error => {console.error(error.message); process.exitCode = 1;});
