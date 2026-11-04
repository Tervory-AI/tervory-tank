// Existing client-response cases use an unregistered legacy tenant. Handle the
// separate metadata read while keeping their content/authority assertions intact.
// Registered homes and failure cases use platform_region_contract.cjs instead.
const assert = require('node:assert/strict');
module.exports = original => async (raw, init, ...rest) => {
  let url;
  try { url = new URL(String(raw)); } catch { /* Original fixture handles it. */ }
  if (url && /^\/v1\/tenants\/[^/]+\/home$/.test(url.pathname) && init?.method === 'GET') {
    assert.equal(init.body, undefined);
    assert.equal(init.cache, 'no-store');
    assert.equal(init.redirect, 'manual');
    assert(init.signal instanceof AbortSignal);
    assert(new Headers(init.headers).get('x-tank-key'));
    return Response.json({detail: {code: 'tenant_home_missing'}}, {status: 404});
  }
  return original(raw, init, ...rest);
};
