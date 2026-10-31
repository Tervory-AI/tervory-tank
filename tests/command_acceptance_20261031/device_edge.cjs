/* Actual CLI device login -> (us-east: actual Workspace adapter | za: Tank directly)
 * -> disposable loopback Tank. The browser approval step is automated by calling
 * the actual Workspace approval module with a signed-in identity. Synthetic only. */
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const { pathToFileURL } = require('node:url');
const { workspace } = require('./workspace_loader.cjs');
const root = path.resolve(__dirname, '../..');
const input = JSON.parse(fs.readFileSync(0, 'utf8'));
const origin = input.origin; const region = input.region;
assert.equal(new URL(origin).hostname, '127.0.0.1');
assert(['us-east', 'za'].includes(region));
const PUBLIC = { 'us-east': 'https://app.tervory.com', za: 'https://za.tervory.com' };
const ZA_TANK = 'https://za-tank.fixture';
// Production shape: Boston's TANK_API_KEY_ZA is the ZA Tank's narrow TANK_HOMES_KEY,
// which cannot approve; approvals use the dedicated TANK_DEVICE_APPROVAL_KEY_ZA.
const ZA_HOMES_KEY = 'dummy-za-homes-key';
const ZA_KEY = input.za_key ?? 'dummy-workspace-key';

let adapterCalls = 0; let directCalls = 0; let approvalCalls = 0;
// Workspace process: us-east home. ZA approvals use approvalTank('za') (https only).
const load = workspace({
  env: { TANK_URL: region === 'us-east' ? origin : 'http://us-east-tank.invalid', TANK_API_KEY: 'dummy-workspace-key',
         TANK_URL_ZA: ZA_TANK, TANK_API_KEY_ZA: ZA_HOMES_KEY, TANK_DEVICE_APPROVAL_KEY_ZA: ZA_KEY },
  fetch: async (url, init) => {
    const target = new URL(url);
    if (target.pathname.startsWith('/v1/command/device/approval/')) {
      approvalCalls++;
      assert.equal(target.origin, region === 'za' ? ZA_TANK : origin);
      assert.equal(init.headers['x-tank-key'], region === 'za' ? ZA_KEY : 'dummy-workspace-key');
    } else {
      // The public adapter only ever forwards to its own box.
      assert.equal(region, 'us-east'); assert.equal(target.origin, origin);
      adapterCalls++;
    }
    return fetch(origin + target.pathname + target.search, init);
  },
});
const adapter = load('lib/tank.ts').personalCommandRequest;
const approval = load('lib/device-login.ts');

const transport = async (url, init) => {
  const target = new URL(url);
  assert.equal(target.origin, PUBLIC[region], 'CLI must call only its region public origin');
  if (region === 'za') {
    // B: za.tervory.com is Tank only. The CLI talks straight to the ZA Tank.
    directCalls++;
    return fetch(origin + target.pathname + target.search, init);
  }
  const request = new Request(url, init);
  return adapter(request, target.pathname.slice('/v1/command/'.length).split('/'));
};

(async () => {
  const cli = await import(pathToFileURL(path.join(root, 'cli/src/client.mjs')).href);
  let saved = null; let output = ''; const opened = [];
  const store = { get: async () => saved, set: async value => { saved = value; }, remove: async () => { saved = null; } };
  const identity = { tenantId: input.tenant, userId: 'offline-client', tenantAdmin: false };
  let approved = false;
  const io = {
    write: value => { output += value; }, prompt: async () => 'N', deviceName: () => `acceptance-${region}`,
    open: url => { opened.push(url); },
    // Automated browser step: the signed-in user opens the page and clicks Approve.
    sleep: async () => {
      if (approved) return;
      approved = true;
      const page = new URL(opened.at(-1));
      assert.equal(page.origin + page.pathname, 'https://app.tervory.com/cli/device');
      assert.equal(page.searchParams.get('region'), region);
      const code = page.searchParams.get('code');
      const shown = await approval.deviceApproval(identity, region, code);
      assert(shown.ok, JSON.stringify(shown));
      assert.equal(shown.device.device_name, `acceptance-${region}`);
      assert.equal(shown.device.region, region);
      const decided = await approval.deviceApproval(identity, region, code, 'approve');
      assert(decided.ok && decided.device.status === 'approved');
    },
  };
  await cli.run(region === 'za' ? ['login', '--region', 'za'] : ['login'], { store, transport, io });
  assert(approved && opened.length === 1);
  const first = JSON.parse(saved);
  assert.equal(first.region, region);
  assert(first.access_token.startsWith(`tv1.${region}.${input.tenant.replaceAll('-', '')}.`));

  // Review of #506 B2: offline-client is a customer, so a pin is refused by Tank (403)
  // before any write and the CLI names no model. The real turn then uses Auto.
  await assert.rejects(() => cli.run(['ask', '--model', input.pin, 'Pinned from the CLI'], { store, transport, io }),
    error => error.message === 'Only Auto is available on this account. Nothing was sent.');
  assert(!output.includes(input.pin), output);
  output = '';
  await cli.run(['ask', 'Hello from the CLI'], { store, transport, io });
  assert.match(output, /Hello world\./, output);
  // Customer receipt: dollar figures only, no model, baseline-model or Auto-model
  // names and no ledger ids (review item 3); an Auto turn has no Auto comparison line.
  assert.match(output, /Step 1 \| cost [0-9.]+ \| would have cost /, output);
  assert.doesNotMatch(output, /What Auto would have cost/, output);
  for (const name of ['luna', input.pin, 'ledger ', 'tokens ']) assert(!output.includes(name), `customer receipt leaked ${name}: ${output}`);
  const thread = /Thread ([0-9a-f-]{36})/.exec(output)[1];

  // Refresh: the access token is near expiry, so the next command rotates both tokens.
  saved = JSON.stringify({ ...first, expires_at: new Date(Date.now() - 1000).toISOString() });
  await cli.run(['threads'], { store, transport, io });
  const second = JSON.parse(saved);
  assert.notEqual(second.access_token, first.access_token);
  assert.notEqual(second.refresh_token, first.refresh_token);
  assert.match(output, new RegExp(thread));
  await assert.rejects(() => new cli.Tank(first.access_token, transport).json('/v1/command/tools'), /Personal token refused/);

  // Revoke: logout ends the server credential, then the keychain copy is gone.
  await cli.run(['logout'], { store, transport, io });
  assert.equal(saved, null);
  await assert.rejects(() => new cli.Tank(second.access_token, transport).json('/v1/command/tools'), /Personal token refused/);
  await assert.rejects(() => cli.run(['threads'], { store, transport, io }), /Login required/);
  for (const secret of [first.access_token, first.refresh_token, second.access_token, second.refresh_token]) {
    assert(!output.includes(secret));
  }
  assert.equal(approvalCalls, 2);
  if (region === 'za') assert(adapterCalls === 0 && directCalls >= 8);
  else assert(adapterCalls >= 8 && directCalls === 0);
  process.stdout.write(`PASS: CLI device login ${region} ${region === 'za' ? 'direct to Tank' : 'via Workspace adapter'}; `
    + `turn, Auto comparison, refresh rotation, revoke\n${JSON.stringify({ thread })}\n`);
})().catch(error => { console.error(error); process.exitCode = 1; });
