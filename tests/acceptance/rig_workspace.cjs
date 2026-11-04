// Execute the shipped Rig server actions; mock only actor and Tank transport.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const { createRequire } = require('node:module');
const ts = createRequire(process.cwd() + '/workspace/package.json')('typescript');
function load(path, dependencies) {
  const code = ts.transpileModule(fs.readFileSync(path, 'utf8'), { compilerOptions: { module: ts.ModuleKind.CommonJS } }).outputText;
  const module = { exports: {} };
  new Function('require', 'module', 'exports', code)(name => {
    assert.ok(Object.hasOwn(dependencies, name), name);
    return dependencies[name];
  }, module, module.exports);
  return module.exports;
}
const operation = process.argv[2];
const calls = [];
const wire = { enabled: operation !== 'plugins-off',
  secrets: [{ name: 'fixture-key', purpose: 'Acceptance', mask: '••••••••', value: 'private-fixture-value' }],
  files: [{ id: 'fixture-file', name: 'fixture.csv', type: 'text/csv', size: 9 }],
};
global.fetch = async (url, init) => {
  calls.push({ url, init });
  assert.ok(url.includes('/v1/vaults/rig.vault/'));
  assert.equal(init.headers.get('x-tervory-user'), 'fixture-admin');
  assert.equal(init.headers.get('x-tervory-squad'), 'rig');
  assert.equal(init.cache, 'no-store');
  return Response.json(wire);
};
const model = load('workspace/app/rig/vault-model.ts', {});
const vault = load('workspace/app/rig/vault-server.ts', {
  '@/lib/tenant': { activeTenant: async () => ({ tenantId: 'fixture-tenant', userId: 'fixture-admin' }) },
  './vault-model': model,
});
(async () => {
  const panel = await vault.loadRigPlugins();
  if (operation === 'plugins-off') {
    assert.equal(panel.enabled, false);
    assert.equal(panel.message, 'This vault is off. Turn it on in Tank.');
    assert.deepEqual(panel.secrets, []);
    assert.deepEqual(panel.files, []);
    return;
  }
  assert.equal(panel.enabled, true);
  assert.equal(panel.secrets[0].name, 'fixture-key');
  assert.equal(panel.secrets[0].mask, '••••••••');
  assert.ok(!JSON.stringify(panel).includes('private-fixture-value'));
  assert.equal(panel.files[0].name, 'fixture.csv');
  if (operation === 'plugins-key') {
    await vault.saveRigSecret('fixture-key', 'Acceptance', 'synthetic-only-value');
    const data = JSON.parse(calls.at(-1).init.body);
    assert.deepEqual(data, { tenant_id: 'fixture-tenant', name: 'fixture-key', purpose: 'Acceptance', value: 'synthetic-only-value' });
    await vault.removeRigSecret('fixture-key');
    assert.equal(calls.at(-1).init.method, 'DELETE');
    assert.ok(calls.at(-1).url.includes('tenant_id=fixture-tenant'));
    return;
  }
  assert.equal(operation, 'plugins-data');
  const form = new FormData();
  form.append('file', new Blob(['sku,price']), 'fixture.csv');
  await vault.uploadRigFiles(form);
  assert.equal(calls.at(-1).init.body, form);
  assert.ok(calls.at(-1).url.includes('/files?tenant_id=fixture-tenant'));
  await vault.addRigLink('https://fixture.example.test/catalogue', 'Fixture link', 'weekly');
  assert.deepEqual(JSON.parse(calls.at(-1).init.body), { tenant_id: 'fixture-tenant', url: 'https://fixture.example.test/catalogue', label: 'Fixture link', frequency: 'weekly' });
  await vault.addRigConnection('Fixture connection', 'https://fixture.example.test/mcp', 'bearer', 'synthetic-only-token');
  assert.equal(JSON.parse(calls.at(-1).init.body).tenant_id, 'fixture-tenant');
  await vault.removeRigFile('fixture-file');
  await vault.removeRigLink('fixture-link');
  await vault.removeRigConnection('Fixture connection');
  for (const call of calls.filter(c => c.init.method === 'DELETE')) assert.ok(call.url.includes('tenant_id=fixture-tenant'));
})().catch(error => { console.error(error); process.exitCode = 1; });
