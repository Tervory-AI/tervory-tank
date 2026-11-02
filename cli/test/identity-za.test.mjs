import test from 'node:test';
import assert from 'node:assert/strict';
import { identityApprovalUrl, run, safe, StreamSanitizer } from '../src/client.mjs';

const start = {
  identity_provider: 'zitadel', device_code: 'tzd1.synthetic-offline', user_code: '1234-5678',
  verification_uri: 'https://auth.za.tervory.com/ui/v2/login/device',
  verification_uri_complete: 'https://auth.za.tervory.com/ui/v2/login/device?user_code=1234-5678',
  interval: 1, expires_in: 600,
};

test('ZA accepts only the fixed Zitadel origin for both verification URLs', () => {
  assert.equal(identityApprovalUrl(start, 'za'), start.verification_uri_complete);
  for (const field of ['verification_uri', 'verification_uri_complete']) {
    for (const url of ['https://evil.example/device', 'http://auth.za.tervory.com/device',
      'https://auth.za.tervory.com.evil.example/device', 'https://user@auth.za.tervory.com/device',
      'https://auth.za.tervory.com:444/device', 'https://auth.za.tervory.com/device#fragment']) {
      assert.throws(() => identityApprovalUrl({ ...start, [field]: url }, 'za'), /Login refused by Tank/);
    }
  }
  assert.throws(() => identityApprovalUrl(start, 'us-east'), /Login refused by Tank/);
  assert.equal(identityApprovalUrl({ user_code: 'BCDF-GHJK' }, 'us-east'),
    'https://app.tervory.com/cli/device?code=BCDF-GHJK&region=us-east');
  assert.equal(identityApprovalUrl({ user_code: 'BCDF-GHJK' }, 'za'),
    'https://app.tervory.com/cli/device?code=BCDF-GHJK&region=za');
});

test('ZA login opens Zitadel and stores only the unchanged Tank credential pair', async () => {
  const opened = []; const calls = []; let saved;
  const grant = {
    access_token: `tv1.za.${'0'.repeat(32)}.${'x'.repeat(43)}`,
    refresh_token: `tvr1.za.${'0'.repeat(32)}.${'r'.repeat(43)}`,
    expires_at: new Date(Date.now() + 3600_000).toISOString(),
    refresh_expires_at: new Date(Date.now() + 30 * 86400_000).toISOString(),
  };
  await run(['login', '--region', 'za'], {
    store: { set: async value => { saved = value; } },
    io: { write() {}, sleep: async () => {}, open: value => opened.push(value) },
    transport: async (url, init) => {
      calls.push(url);
      assert.equal(new URL(url).origin, 'https://za.tervory.com');
      assert.equal(init.headers.Authorization, undefined);
      assert.equal(init.redirect, 'manual');
      return Response.json(url.endsWith('/code') ? start : grant);
    },
  });
  assert.deepEqual(opened, [start.verification_uri_complete]);
  assert.equal(calls.length, 2);
  assert.equal(JSON.parse(saved).access_token, grant.access_token);
  assert.equal(JSON.parse(saved).refresh_token, grant.refresh_token);
  assert(!saved.includes(start.device_code));
});


test('wrapped identity device codes are redacted across every chunk boundary', () => {
  const code = 'tzd1.synthetic-offline-device-code';
  assert.equal(safe(code), '[redacted]');
  for (let split = 0; split <= code.length; split++) {
    const sanitizer = new StreamSanitizer();
    assert.equal(sanitizer.write(code.slice(0, split)) + sanitizer.write(code.slice(split)) + sanitizer.end(), '[redacted]');
  }
});
