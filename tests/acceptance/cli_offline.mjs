// Acceptance fixture preloader: real HTTP is limited to disposable loopback servers.
// CLI production origins still pass through each existing fixture's injected transport.
const realFetch = globalThis.fetch;
globalThis.fetch = (input, init) => {
  const url = new URL(typeof input === 'string' || input instanceof URL ? input : input.url);
  if (!['127.0.0.1', 'localhost', '[::1]'].includes(url.hostname)) {
    throw new Error('Acceptance fixture refused external HTTP.');
  }
  return realFetch(input, init);
};
