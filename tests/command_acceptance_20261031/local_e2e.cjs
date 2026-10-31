/* Local end-to-end run on one machine: actual CLI -> (us-east: actual Workspace
 * public adapter | za: Tank directly) -> real uvicorn Tank -> real Postgres ->
 * a LiteLLM proxy. The browser step (Clerk-signed-in user clicks Approve) is the
 * actual Workspace approval module called with an injected signed-in identity,
 * because Next cannot run here without Clerk keys. The Chats API turn uses the
 * actual /chats/api route module with the same injected identity.
 *
 * Inputs (env): E2E_TANK_US, E2E_TANK_ZA (loopback http), E2E_TANK_KEY (local
 * service key, never printed), E2E_TENANT, E2E_PIN (pinned model), E2E_PSQL
 * (psql connection args for the two local databases, comma separated).
 * Never point this at a deployed Tank or database. */
const assert = require('node:assert/strict');
const path = require('node:path');
const { execFileSync } = require('node:child_process');
const { pathToFileURL } = require('node:url');
const { workspace } = require('./workspace_loader.cjs');
const root = path.resolve(__dirname, '../..');
const env = process.env;
const TANK = { 'us-east': env.E2E_TANK_US, za: env.E2E_TANK_ZA };
for (const url of Object.values(TANK)) assert.equal(new URL(url).hostname, '127.0.0.1', 'local Tank only');
const DB = { 'us-east': env.E2E_DB_US, za: env.E2E_DB_ZA };
const KEY = env.E2E_TANK_KEY; const TENANT = env.E2E_TENANT; const PIN = env.E2E_PIN;
const ZA_TANK = 'https://za-tank.local-e2e';
const redact = text => String(text).replace(/\btv[rd]?1\.[\w.-]+/g, '[credential]');
const sql = (region, query) => execFileSync('psql', ['-h', '127.0.0.1', '-p', '55471', '-U', 'postgres', '-d', DB[region],
  '-AtF', '|', '-c', query], { encoding: 'utf8' }).trim();
const log = (...parts) => process.stdout.write(parts.join(' ') + '\n');

function rig(region, founder) {
  const load = workspace({
    env: { TANK_URL: TANK['us-east'], TANK_API_KEY: KEY, TANK_URL_ZA: ZA_TANK, TANK_API_KEY_ZA: KEY, TANK_DEVICE_APPROVAL_KEY_ZA: KEY },
    fetch: async (url, init) => {
      const target = new URL(url);
      const base = target.origin === ZA_TANK ? TANK.za : target.origin;
      return fetch(base + target.pathname + target.search, init);
    },
    mocks: {
      '@/lib/trigger': { triggerIdentity: async tenant => tenant && { ...tenant, tenantAdmin: false } },
      '@/lib/tenant': { activeTenant: async () => ({ tenantId: TENANT, userId: 'e2e-founder', orgName: 'Local E2E', orgId: 'org_local' }) },
      '@/lib/admin': { isFounder: () => founder },
    },
  });
  const adapter = load('lib/tank.ts').personalCommandRequest;
  const approval = load('lib/device-login.ts');
  const transport = async (url, init) => {
    const target = new URL(url);
    if (region === 'za') {
      assert.equal(target.origin, 'https://za.tervory.com');
      return fetch(TANK.za + target.pathname + target.search, init); // za.tervory.com is Tank
    }
    assert.equal(target.origin, 'https://app.tervory.com');
    return adapter(new Request(url, init), target.pathname.slice('/v1/command/'.length).split('/'));
  };
  return { load, approval, transport };
}

async function deviceLogin(cli, region) {
  const { approval, transport, load } = rig(region, true);
  let saved = null; let output = ''; const opened = []; let shown;
  const store = { get: async () => saved, set: async value => { saved = value; }, remove: async () => { saved = null; } };
  const identity = { tenantId: TENANT, userId: 'e2e-founder', tenantAdmin: true };
  const io = {
    write: value => { output += value; }, prompt: async () => 'N', deviceName: () => `e2e-laptop-${region}`,
    open: url => { opened.push(url); },
    sleep: async () => {
      if (shown) return;
      const page = new URL(opened.at(-1));
      shown = await approval.deviceApproval(identity, region, page.searchParams.get('code'));
      assert(shown.ok, JSON.stringify(shown));
      log(`  approval page would show: code=${shown.device.user_code} org=Local E2E device=${shown.device.device_name} region=${shown.device.region} status=${shown.device.status}`);
      const decided = await approval.deviceApproval(identity, region, shown.device.user_code, 'approve');
      assert(decided.ok && decided.device.status === 'approved');
      log(`  user clicked Approve -> ${decided.device.status}`);
    },
  };
  const t0 = Date.now();
  await cli.run(region === 'za' ? ['login', '--region', 'za'] : ['login'], { store, transport, io });
  log(`  CLI opened: ${opened[0]}`);
  log(`  CLI said: ${redact(output.trim().split('\n').at(-1))} (${Date.now() - t0} ms)`);
  return { get saved() { return saved; }, set saved(v) { saved = v; }, store, io, transport, output: () => output, load,
    clear: () => { output = ''; } };
}

(async () => {
  const cli = await import(pathToFileURL(path.join(root, 'cli/src/client.mjs')).href);
  for (const region of ['us-east', 'za']) {
    log(`\n== ${region}: ${region === 'za' ? 'CLI -> za.tervory.com (Tank only)' : 'CLI -> app.tervory.com Workspace adapter -> Tank'} ==`);
    const s = await deviceLogin(cli, region);
    const cred = JSON.parse(s.saved);
    log(`  keychain entry keys: ${Object.keys(cred).join(',')}; access expires ${cred.expires_at}; refresh expires ${cred.refresh_expires_at}`);
    log('  DB personal_tokens:', sql(region, `SELECT region,user_id,device_name,length(token_hash),length(refresh_hash),expires_at-created_at,refresh_expires_at-created_at,revoked_at IS NULL FROM tank.personal_tokens WHERE device_name='e2e-laptop-${region}' ORDER BY created_at DESC LIMIT 1`));
    log('  DB device_authorizations:', sql(region, `SELECT status,region,device_name,user_id,token_id IS NOT NULL,length(device_hash) FROM tank.device_authorizations ORDER BY created_at DESC LIMIT 1`));

    // CLI chat turn, pinned model: streamed answer + receipt with Tank's Auto comparison.
    s.clear();
    const deltas = [];
    const io = { ...s.io, write: v => { s.io.write(v); deltas.push(v); }, preview: v => deltas.push(`[preview]${v}`) };
    await cli.run(['ask', '--model', PIN, `Local e2e CLI turn (${region})`], { store: s.store, transport: s.transport, io });
    const out = s.output();
    log('  CLI ask output:\n' + redact(out).trim().split('\n').map(line => '    ' + line).join('\n'));
    assert.match(out, /Auto would have cost/);
    const thread = /Thread ([0-9a-f-]{36})/.exec(out)[1];
    log('  DB ledger row (region|model|tokens_in|tokens_out|cost_usd|cost_status|baseline_model|baseline_cost_usd|baseline_status):',
      sql(region, `SELECT region,model,tokens_in,tokens_out,cost_usd,cost_status,baseline_model,baseline_cost_usd,baseline_status FROM tank.ledger WHERE tenant_id='${TENANT}' AND task_type='command.turn' ORDER BY ts DESC LIMIT 1`));
    log('  DB receipt Auto fields (requested|auto_model|auto_cost_usd|status|priced_at):', sql(region, `SELECT r->>'requested_model',r->>'auto_model',r->>'auto_cost_usd',r->>'auto_cost_status',r->>'auto_priced_at' FROM tank.command_threads t, jsonb_array_elements(t.state::jsonb->'receipts') r WHERE t.thread_id='${thread}'`));
    log('  DB thread owner:', sql(region, `SELECT user_id FROM tank.command_threads WHERE thread_id='${thread}'`));

    // last_used_at is recorded.
    log('  last_used_at set:', sql(region, `SELECT last_used_at IS NOT NULL FROM tank.personal_tokens WHERE device_name='e2e-laptop-${region}' AND revoked_at IS NULL ORDER BY created_at DESC LIMIT 1`));

    // Access-token expiry on the server: refused; the CLI refreshes and rotates.
    sql(region, `UPDATE tank.personal_tokens SET expires_at=now()-interval '1 second' WHERE device_name='e2e-laptop-${region}' AND revoked_at IS NULL`);
    await assert.rejects(() => new cli.Tank(cred.access_token, s.transport).json('/v1/command/tools'), /Personal token refused/);
    log('  expired access token refused by Tank: yes');
    s.saved = JSON.stringify({ ...cred, expires_at: new Date(Date.now() - 1000).toISOString() });
    s.clear();
    await cli.run(['threads'], { store: s.store, transport: s.transport, io: s.io });
    const rotated = JSON.parse(s.saved);
    assert.notEqual(rotated.refresh_token, cred.refresh_token);
    assert(s.output().includes(thread));
    log('  CLI refreshed and rotated both tokens; `threads` lists the new thread: yes');
    const reuse = await cli.deviceCall(region, 'refresh', { refresh_token: cred.refresh_token }, s.transport);
    log(`  reusing the old refresh token: ${reuse.error}`);

    if (region === 'us-east') {
      // Chats API turn (browser path) on the same box, Auto and pinned, streamed.
      const route = s.load('app/chats/api/[...path]/route.ts');
      const call = (target, method = 'GET', body) => route[method](new Request(`https://app.tervory.com/chats/api/${target}`, {
        method, headers: { origin: 'https://app.tervory.com', host: 'app.tervory.com', 'content-type': 'application/json' },
        body: body === undefined ? undefined : JSON.stringify(body) }), { params: Promise.resolve({ path: target.split('/') }) });
      const created = await (await call('threads', 'POST', { title: 'Local e2e Chats API' })).json();
      const { modelValue } = s.load('app/chats/models.ts');
      for (const model of ['auto', modelValue(PIN)]) {
        const response = await call(`threads/${created.thread_id}/turn`, 'POST', { text: `Chats API turn (${model})`, model });
        assert.equal(response.status, 200);
        assert.match(response.headers.get('content-type'), /event-stream/);
        const reader = response.body.getReader(); const decoder = new TextDecoder(); let wire = ''; let chunks = 0;
        for (;;) { const { value, done } = await reader.read(); if (done) break; chunks++; wire += decoder.decode(value, { stream: true }); }
        const types = [...wire.matchAll(/^event: (\w+)/gm)].map(m => m[1]);
        const tokens = [...wire.matchAll(/^event: token\ndata: (.*)$/gm)].map(m => JSON.parse(m[1]).text).join('');
        const receipt = JSON.parse(/^event: receipt\ndata: (.*)$/m.exec(wire)[1]);
        log(`  Chats API ${model === 'auto' ? 'auto' : 'pinned ' + PIN}: ${chunks} stream chunks; events ${[...new Set(types)].join(',')}; answer "${tokens.trim()}"`);
        log(`    receipt totals ${JSON.stringify(receipt.totals)}`);
        const row = receipt.rows[0];
        log(`    receipt row model=${row.model} requested=${row.requested_model} cost=${row.cost_usd} auto_model=${row.auto_model} auto_cost_usd=${row.auto_cost_usd} auto_cost_status=${row.auto_cost_status}`);
      }
      log('  DB ledger (Chats API turns: model|tokens_in|tokens_out|cost_usd|cost_status):\n' + sql(region, `SELECT model,tokens_in,tokens_out,cost_usd,cost_status FROM tank.ledger WHERE tenant_id='${TENANT}' AND task_type='command.turn' ORDER BY ts DESC LIMIT 2`).split('\n').map(l => '    ' + l).join('\n'));
      const snap = await (await call(`threads/${created.thread_id}`)).json();
      log(`  Chats API snapshot: ${snap.messages.length} messages; thread spent_usd=${snap.thread.spent_usd} saved_usd=${snap.thread.saved_usd}`);
    }

    // Refresh-token expiry: refresh refused, the CLI asks to sign in again.
    sql(region, `UPDATE tank.personal_tokens SET expires_at=now()-interval '1 second', refresh_expires_at=now()-interval '1 second' WHERE device_name='e2e-laptop-${region}' AND revoked_at IS NULL`);
    s.saved = JSON.stringify({ ...rotated, expires_at: new Date(Date.now() - 1000).toISOString() });
    await assert.rejects(() => cli.run(['threads'], { store: s.store, transport: s.transport, io: s.io }), /Login expired or revoked/);
    log('  expired refresh token: CLI says "Login expired or revoked. Run tervory login."');

    // Revoke: sign in again, then logout revokes on Tank.
    const s2 = await deviceLogin(cli, region);
    const fresh = JSON.parse(s2.saved);
    await cli.run(['logout'], { store: s2.store, transport: s2.transport, io: s2.io });
    await assert.rejects(() => new cli.Tank(fresh.access_token, s2.transport).json('/v1/command/tools'), /Personal token refused/);
    const after = await cli.deviceCall(region, 'refresh', { refresh_token: fresh.refresh_token }, s2.transport);
    log(`  logout: keychain entry ${s2.saved === null ? 'removed' : 'KEPT'}; access refused; refresh -> ${after.error}`);
    log('  DB revoked_at set:', sql(region, `SELECT revoked_at IS NOT NULL FROM tank.personal_tokens WHERE device_name='e2e-laptop-${region}' ORDER BY created_at DESC LIMIT 1`));
  }
  log('\nPASS local end-to-end');
})().catch(error => { console.error(redact(error.stack || error)); process.exitCode = 1; });
