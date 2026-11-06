// Execute the real middleware and host rewrite functions; mock only Trigger sign-in/Next transport.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const { createRequire } = require('node:module');
const ts = createRequire(process.cwd() + '/workspace/package.json')('typescript');
function load(file, dependencies) {
  const code = ts.transpileModule(fs.readFileSync(file, 'utf8'), {
    compilerOptions: { module: ts.ModuleKind.CommonJS },
  }).outputText;
  const module = { exports: {} };
  new Function('require', 'module', 'exports', code)(name => {
    assert.ok(Object.hasOwn(dependencies, name), `Unexpected dependency: ${name}`);
    return dependencies[name];
  }, module, module.exports);
  return module.exports;
}
const hosts = load('workspace/lib/product-hosts.ts', {});
const origin = load('workspace/lib/workspace-origin.ts', {'./product-hosts': hosts});
const setup = load('workspace/lib/workspace-setup.ts', {});
const requestHelpers = load('workspace/lib/request.ts', {});
let signed = true;
const middleware = load('workspace/middleware.ts', {
  '@/lib/product-hosts': hosts,
  './lib/workspace-origin': origin,
  './lib/request': requestHelpers,
  './lib/workspace-setup': { workspaceSetupMessage: () => setup.workspaceSetupMessage({ TANK_URL: 'http://tank:8000', TANK_API_KEY: 'placeholder-key', TRIGGER_SIGNIN_WORKSPACE_SECRET: 'placeholder-secret' }) },
  'next-auth/jwt': {getToken: async () => signed ? {principal: {expiresAt: Date.now() + 3600000}} : null},
  'next/server': { NextResponse: {
    rewrite: url => ({ type: 'rewrite', url: url.href }),
    redirect: (url, status) => ({ type: 'redirect', url, status }),
    next: () => undefined,
  } },
}).default;
function request(path, forwarded = true) {
  const nextUrl = new URL('http://0.0.0.0:3000' + path);
  nextUrl.clone = () => new URL(nextUrl);
  return { method: 'GET', nextUrl, cookies: {get: () => undefined}, headers: new Headers(forwarded ? { 'x-forwarded-host': 'rig.tervory.com', host: 'internal:3000' } : { host: 'rig.tervory.com' }) };
}
(async () => {
  for (const forwarded of [true, false]) {
    for (const [path, expected] of [['/?q=part', '/rig?q=part'], ['/admin?cart=orders', '/rig/admin?cart=orders'], ['/admin/three-d/', '/rig/admin/three-d']]) {
      signed = true;
      const result = await middleware(request(path, forwarded));
      assert.equal(result.type, 'rewrite');
      assert.equal(new URL(result.url).pathname + new URL(result.url).search, expected);
      signed = false;
      const guest = await middleware(request(path, forwarded));
      assert.equal(guest.type, 'redirect');
      assert.equal(guest.url.origin + guest.url.pathname, 'https://app.tervory.com/sign-in');
      assert.equal(guest.url.searchParams.get('callbackUrl'), 'https://rig.tervory.com' + path);
    }
  }
  for (const path of ['/rig/admin', '/rig/admin/api', '/rig/admin/three-d', '/_next/static/chunk.js', '/rig-cart/select-chevron.svg']) {
    signed = true;
    assert.equal(await middleware(request(path)), undefined);
  }
  for (const path of ['/sign-in', '/sign-up/continue', '/api/health']) {
    signed = false;
    assert.equal(await middleware(request(path)), undefined);
  }
  console.log('Rig middleware: root/admin rewrites, query strings and authentication passed');
})().catch(error => { console.error(error); process.exitCode = 1; });
