const assert = require('node:assert/strict');
const http = require('node:http');
const {once} = require('node:events');
const {workspace} = require('./command_acceptance_20261031/workspace_loader.cjs');

async function main() {
  let calls = 0;
  const server = http.createServer((_request, response) => {
    calls++;
    response.writeHead(401, {'content-type': 'text/plain'});
    response.write('placeholder refusal');
  });
  server.listen(0, '127.0.0.1');
  await once(server, 'listening');
  try {
    const {fetchWithDeadline} = workspace({env: {}, fetch: globalThis.fetch})('lib/request.ts');
    const response = await fetchWithDeadline(`http://127.0.0.1:${server.address().port}/placeholder`);
    assert.equal(response.status, 401);
    await response.body.cancel();
    assert.equal(response.status, 401);
    assert.equal(calls, 1, 'cancellation must not retry the request');
  } finally {
    server.closeAllConnections();
    await new Promise(resolve => server.close(resolve));
  }

  const failure = new Error('placeholder underlying cancellation failure');
  let signal;
  const broken = workspace({env: {}, fetch: async (_url, init) => {
    signal = init.signal;
    return new Response(new ReadableStream({cancel() { throw failure; }}));
  }})('lib/request.ts');
  const response = await broken.fetchWithDeadline('http://localhost/placeholder');
  await assert.rejects(response.body.cancel(), error => error === failure);
  assert.equal(signal.aborted, true, 'cancellation must still abort upstream work');

  const plain = workspace({env: {}, fetch: async () => new Response('placeholder complete')})('lib/request.ts');
  assert.equal(await (await plain.fetchWithDeadline('http://localhost/placeholder')).text(), 'placeholder complete');
  console.log('PASS actual HTTP 401 cancellation, single attempt, genuine error propagation, upstream abort and normal completion');
}

main().catch(error => { console.error(error); process.exitCode = 1; });
