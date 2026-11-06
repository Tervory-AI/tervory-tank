const original = globalThis.fetch;
const base = new URL(process.env.TERVORY_TEST_RELEASE_BASE);
const origin = new URL(process.env.TERVORY_TEST_RELEASE_ORIGIN);
if (origin.protocol !== 'http:' || origin.hostname !== '127.0.0.1') throw Error('Loopback fixture required');
globalThis.fetch = (url, init) => {
  const target = new URL(url);
  if (target.origin !== base.origin || !target.pathname.startsWith(base.pathname.replace(/\/$/, '') + '/')) throw Error('Unexpected release host');
  return original(new URL(target.pathname, origin), init);
};
