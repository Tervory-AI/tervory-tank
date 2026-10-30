"""Exercise the actual Base proxy behind Coolify, with mocked tenant/Tank only."""

import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_base_product_proxy_origin_and_tenant_boundary():
    result = subprocess.run(["node", "-"], cwd=ROOT, capture_output=True, text=True, timeout=60, input=r"""
const assert = require('node:assert/strict');
const fs = require('node:fs');
const { createRequire } = require('node:module');
const workspaceRequire = createRequire(process.cwd() + '/workspace/package.json');
const ts = workspaceRequire('typescript');
const calls = [];
let signedIn = true;
const mocks = {
  '@/lib/tenant': { currentTenant: async () => {
    if (!signedIn) throw new Error('signed out');
    return { tenantId: 'authenticated-tenant', userId: 'authenticated-user' };
  } },
  '@/lib/tank': { baseProductRequest: async (...args) => {
    calls.push(args);
    return Response.json({ ok: true });
  } },
};
const code = ts.transpileModule(fs.readFileSync('workspace/app/base/product/[...path]/route.ts', 'utf8'), {
  compilerOptions: { module: ts.ModuleKind.CommonJS },
}).outputText;
const loaded = { exports: {} };
new Function('require', 'module', 'exports', code)((name) => {
  assert.ok(Object.hasOwn(mocks, name), `Unexpected dependency ${name}`);
  return mocks[name];
}, loaded, loaded.exports);
const paths = ['reference/batches', 'uploads', 'comparison'];
async function post(path, headers, requestUrl = 'https://0.0.0.0:3000/base/product/' + path) {
  return loaded.exports.POST(new Request(requestUrl, {
    method: 'POST', headers,
    body: JSON.stringify({ tenant_id: 'forged-tenant', created_by: 'forged-user', states: ['DC'] }),
  }), { params: Promise.resolve({ path: path.split('/') }) });
}
(async () => {
  let accepted = 0, rejected = 0;
  for (const path of paths) {
    for (const host of ['base.tervory.com', 'app.tervory.com']) {
      const before = calls.length;
      const response = await post(path, { host, origin: 'https://' + host,
        'x-forwarded-host': 'untrusted.example', 'x-forwarded-proto': 'http' });
      assert.equal(response.status, 200, `${host}/${path} behind internal bind`);
      assert.equal(calls.length, before + 1);
      const [tenant, target, , body] = calls.at(-1);
      assert.equal(tenant, 'authenticated-tenant');
      assert.equal(target, path);
      assert.ok(!Object.hasOwn(body, 'tenant_id'));
      if (path !== 'comparison') assert.equal(body.created_by, 'authenticated-user');
      accepted++;
      for (const origin of [undefined, '', 'null', 'not a URL', 'https://evil.example',
        'https://' + host + '.evil.example', 'http://' + host, 'https://' + host + ':444',
        'https://0.0.0.0:3000', 'https://' + (host === 'base.tervory.com' ? 'app.tervory.com' : 'base.tervory.com')]) {
        const headers = { host, 'x-forwarded-host': 'evil.example', 'x-forwarded-proto': 'https' };
        if (origin !== undefined) headers.origin = origin;
        const before = calls.length;
        const response = await post(path, headers);
        assert.equal(response.status, 403, `${host}/${path} rejects ${origin}`);
        assert.equal(calls.length, before, 'Rejected request must never reach Tank');
        assert.deepEqual(await response.json(), { detail: 'Open this form in your workspace.' });
        rejected++;
      }
      // A spoofed forwarded host must not override the actual public Host.
      const beforeForged = calls.length;
      assert.equal((await post(path, { host, origin: 'https://evil.example',
        'x-forwarded-host': 'evil.example' })).status, 403);
      assert.equal(calls.length, beforeForged);
      rejected++;
    }
  }
  // Existing local development and ordinary same-origin requests still work.
  assert.equal((await post('uploads', { host: 'localhost:3000', origin: 'http://localhost:3000' },
    'http://localhost:3000/base/product/uploads')).status, 200);
  signedIn = false;
  const beforeSignedOut = calls.length;
  assert.equal((await post('uploads', { host: 'base.tervory.com', origin: 'https://base.tervory.com' })).status, 401);
  assert.equal(calls.length, beforeSignedOut);
  console.log(`${accepted} public-host writes accepted; ${rejected} unsafe writes refused; local and signed-out checks passed`);
})().catch(error => { console.error(error); process.exitCode = 1; });
""")
    assert result.returncode == 0, result.stdout + result.stderr
    print(result.stdout.strip())
