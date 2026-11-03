// Offline protocol fixture, never a provider/model/account call. The Python
// identity suite separately verifies signed OIDC claims against its fake JWKS.
import test from 'node:test';
import assert from 'node:assert/strict';
import { createServer } from 'node:http';
import { mkdtemp, writeFile, readFile, rm } from 'node:fs/promises';
import { execFileSync } from 'node:child_process';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { run } from '../src/client.mjs';

const suffix = 'placeholder'.padEnd(43, 'x');
const grant = region => ({
  access_token: `tv1.${region}.${'0'.repeat(32)}.${suffix}`,
  refresh_token: `tvr1.${region}.${'0'.repeat(32)}.${suffix}`,
  expires_at: new Date(Date.now() + 3600000).toISOString(),
  refresh_expires_at: new Date(Date.now() + 86400000).toISOString(),
});

test('offline ZA OIDC device approval to keychain to ZA code, plugin Confirm and local undo', async () => {
  const root = await mkdtemp(join(tmpdir(), 'cli-w4-placeholder-'));
  execFileSync('git', ['init', '-q', root]);
  await writeFile(join(root, 'file.txt'), 'old\n');
  await writeFile(join(root, 'AGENTS.md'), 'Conventions: keep examples short.\n');
  let approved = false; let saved; let output = ''; let round = 0; let confirmed = false;
  const calls = []; const oidcCalls = [];
  const diff = '--- a/file.txt\n+++ b/file.txt\n@@ -1 +1 @@\n-old\n+new\n';
  const card = { card_id: 'placeholder-card', tool: 'plugins.list', arguments: {}, summary: 'List plugins', status: 'pending' };
  const server = createServer(async (req, res) => {
    try {
      const bytes = []; for await (const chunk of req) bytes.push(chunk);
      const body = Buffer.concat(bytes).toString();
      const json = body ? JSON.parse(body) : {};
      const send = (value, status = 200) => { res.writeHead(status, { 'Content-Type': 'application/json' }); res.end(JSON.stringify(value)); };
      // Fake OIDC server: approval is independent of polling, just as a browser
      // approves the user code while Tank alone exchanges the device code.
      if (req.url.startsWith('/oidc/')) {
        oidcCalls.push(req.url);
        if (req.url === '/oidc/device_authorization') return send({ device_code: 'placeholder-oidc-device', user_code: '1234-5678' });
        if (req.url === '/oidc/approve') { approved = true; return send({ approved: true }); }
        if (req.url === '/oidc/token') return send(approved ? { id_token: 'placeholder-verified-by-fake-tank' } : { error: 'authorization_pending' }, approved ? 200 : 400);
        return send({}, 404);
      }
      if (req.url.endsWith('/device/code')) {
        assert.equal(json.approval, 'zitadel');
        const start = await (await fetch(base + '/oidc/device_authorization', { method: 'POST' })).json();
        return send({ ...start, device_code: 'tzd1.placeholder', identity_provider: 'zitadel', interval: 1,
          verification_uri: 'https://auth-za.tervory.com/device',
          verification_uri_complete: 'https://auth-za.tervory.com/device?user_code=1234-5678' });
      }
      if (req.url.endsWith('/device/token')) {
        const result = await (await fetch(base + '/oidc/token', { method: 'POST' })).json();
        return result.error ? send(result, 400) : send(grant('za'));
      }
      assert.equal(req.headers.authorization, `Bearer ${grant('za').access_token}`);
      if (req.url.endsWith('/threads')) return send({ thread_id: 'placeholder-thread' });
      if (req.url.endsWith('/code-turn')) {
        assert(json.history.some(item => item.kind === 'project' && item.content.includes('Conventions:')));
        if (round === 0) { round++; return send({ answer: '', requests: [{ name: 'read_file', arguments: { path: 'file.txt' } }] }); }
        if (round === 1) { round++; assert(json.tool_results.at(-1).output.includes('old')); return send({ answer: '', requests: [{ name: 'propose_edit', arguments: { diff } }] }); }
        if (round === 2) { round++; assert(json.tool_results.at(-1).output.includes('"applied":true'), json.tool_results.at(-1).output); return send({ answer: 'Updated file.txt.', requests: [] }); }
        if (round === 3) { round++; assert.equal(await readFile(join(root, 'file.txt'), 'utf8'), 'old\n'); return send({ answer: '', requests: [{ name: 'tervory', arguments: { tool: card.tool, arguments: {} } }], cards: [card] }); }
        assert(confirmed); assert(json.tool_results.at(-1).output.includes('github')); return send({ answer: 'GitHub is installed.', requests: [] });
      }
      if (req.url.endsWith('/cards/placeholder-card')) { assert.equal(json.action, 'confirm'); confirmed = true; return send({ ...card, status: 'confirmed' }); }
      if (req.url.endsWith('/placeholder-thread')) return send({
        steps: [{ step_id: card.card_id, status: 'done', actor: 'plugins', label: 'Plugins listed' }],
        cards: [{ ...card, status: 'done', result: { plugins: [{ name: 'github', status: 'installed', count: 1 }] } }], receipts: [],
      });
      return send({}, 404);
    } catch { res.writeHead(500); res.end('{}'); }
  });
  await new Promise(resolve => server.listen(0, '127.0.0.1', resolve));
  const base = `http://127.0.0.1:${server.address().port}`;
  const transport = (url, init) => {
    calls.push(url);
    assert.equal(new URL(url).origin, 'https://za.tervory.com');
    return fetch(base + new URL(url).pathname, init);
  };
  const store = { get: async () => saved, set: async value => { saved = value; } };
  try {
    await run(['login', '--region', 'za'], { store, transport, io: {
      deviceName: () => 'placeholder-worker', write: value => { output += value; }, sleep: async () => {},
      open: async url => {
        assert.equal(new URL(url).origin, 'https://auth-za.tervory.com');
        await fetch(base + '/oidc/approve', { method: 'POST' });
      },
    } });
    assert.equal(JSON.parse(saved).region, 'za');
    const answers = ['Update file.txt.', 'y', '/undo', 'y', 'List plugins.', 'y', '/exit'];
    await run(['code', root], { store, transport, io: {
      interactive: true, write: value => { output += value; },
      prompt: async label => { const answer = answers.shift(); assert.notEqual(answer, undefined); output += label + answer + '\n'; return answer; },
    } });
    assert.equal(await readFile(join(root, 'file.txt'), 'utf8'), 'old\n');
    assert(calls.every(url => new URL(url).origin === 'https://za.tervory.com'));
    assert(!calls.some(url => url.includes('/undo')));
    assert.deepEqual(oidcCalls, ['/oidc/device_authorization', '/oidc/approve', '/oidc/token']);
    assert(!output.includes(suffix)); assert(!output.includes('tzd1.'));
    assert(output.includes('Undo [y/N] y')); assert(output.includes('Confirm [y/N] y'));
    if (process.env.CLI_W4_TRANSCRIPT) await writeFile(process.env.CLI_W4_TRANSCRIPT, output);
  } finally { server.closeAllConnections(); await new Promise(resolve => server.close(resolve)); await rm(root, { recursive: true, force: true }); }
});
