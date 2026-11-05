// Execute the real middleware and host rewrite functions; mock only Clerk/Next transport.
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
const middleware = load('workspace/middleware.ts', {
  '@/lib/product-hosts': hosts,
  '@/lib/tank': {mobileRequest: async () => {throw Error('Unexpected mobile resolution without a cookie');}},
  '@clerk/nextjs/server': {
    clerkMiddleware: handler => handler,
    createRouteMatcher: () => req => ['/api/health', '/sign-in', '/sign-up'].some(p => req.nextUrl.pathname.startsWith(p)),
  },
  'next/server': { NextResponse: {
    rewrite: url => ({ type: 'rewrite', url: url.href }),
    redirect: (url, status) => ({ type: 'redirect', url, status }),
  } },
}).default;
function request(path, forwarded = true) {
  const nextUrl = new URL('http://0.0.0.0:3000' + path);
  nextUrl.clone = () => new URL(nextUrl);
  return { nextUrl, cookies: {get: () => undefined}, headers: new Headers(forwarded ? { 'x-forwarded-host': 'rig.tervory.com', host: 'internal:3000' } : { host: 'rig.tervory.com' }) };
}
(async () => {
  const signedIn = async () => ({ userId: 'fixture-user' });
  const signedOut = async () => ({ userId: null, redirectToSignIn: options => ({ type: 'signin', ...options }) });
  for (const forwarded of [true, false]) {
    for (const [path, expected] of [['/?q=part', '/rig?q=part'], ['/admin?cart=orders', '/rig/admin?cart=orders'], ['/admin/three-d/', '/rig/admin/three-d']]) {
      const result = await middleware(signedIn, request(path, forwarded));
      assert.equal(result.type, 'rewrite');
      assert.equal(new URL(result.url).pathname + new URL(result.url).search, expected);
      const guest = await middleware(signedOut, request(path, forwarded));
      assert.equal(guest.type, 'signin');
      assert.equal(guest.returnBackUrl, 'https://rig.tervory.com' + path);
    }
  }
  for (const path of ['/rig/admin', '/rig/admin/api', '/rig/admin/three-d', '/_next/static/chunk.js', '/rig-cart/select-chevron.svg']) {
    assert.equal(await middleware(signedIn, request(path)), undefined);
  }
  for (const path of ['/sign-in', '/sign-up/continue', '/api/health']) {
    assert.equal(await middleware(signedOut, request(path)), undefined);
  }
  console.log('Rig middleware: root/admin rewrites, query strings and authentication passed');
})().catch(error => { console.error(error); process.exitCode = 1; });
