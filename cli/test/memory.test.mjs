import test from 'node:test';
import assert from 'node:assert/strict';
import { run } from '../src/client.mjs';

// Transport contract only. Real Hermes acceptance lives in tests/opli_agent;
// these tests do not establish installed-client or live-service acceptance.
const token = `tv1.us-east.${'0'.repeat(32)}.${'x'.repeat(43)}`;
function client(status = 200, result = { id: 'placeholder-memory' }) {
  const calls = []; let output = '';
  return {
    calls, output: () => output,
    options: {
      store: { get: async () => token },
      io: { write: value => { output += value; } },
      transport: async (url, init) => {
        assert.equal(new URL(url).origin, 'https://app.tervory.com');
        assert.equal(init.headers.Authorization, `Bearer ${token}`);
        assert.equal(init.redirect, 'manual');
        calls.push({ path: new URL(url).pathname + new URL(url).search,
          method: init.method, body: init.body ? JSON.parse(init.body) : undefined });
        return Response.json(result, { status });
      },
    },
  };
}

for (const [args, path, method, body] of [
  [['view'], 'memory.view?task_key=memory_control&memory_control=view', 'GET', undefined],
  [['view', 'command.code'], 'memory.view?task_key=command.code&memory_control=view', 'GET', undefined],
  [['edit', 'placeholder-memory', 'Use', 'tabs'], 'memory.edit', 'POST', { memory_id: 'placeholder-memory', text: 'Use tabs', memory_control: 'edit' }],
  [['forget', 'placeholder-memory'], 'memory.forget', 'POST', { memory_id: 'placeholder-memory', memory_control: 'forget' }],
  [['off'], 'memory.control', 'POST', { control: 'off' }],
  [['control', 'view'], 'memory.control', 'POST', { control: 'view' }],
  [['control', 'edit'], 'memory.control', 'POST', { control: 'edit' }],
  [['control', 'forget'], 'memory.control', 'POST', { control: 'forget' }],
]) {
  test(`memory ${args.join(' ')} uses authenticated Tank contract`, async () => {
    const c = client();
    await run(['memory', ...args], c.options);
    assert.deepEqual(c.calls, [{ path: `/v1/command/opli/${path}`, method, body }]);
  });
}

for (const args of [[], ['control'], ['control', 'on'], ['off', 'extra'], ['forget'], ['edit', 'id'], ['view', 'a', 'b'], ['view', '--tenant', 'other']]) {
  test(`invalid memory arguments ${JSON.stringify(args)} never reach Tank`, async () => {
    const c = client();
    await assert.rejects(run(['memory', ...args], c.options));
    assert.equal(c.calls.length, 0);
    assert.equal(c.output(), '');
  });
}

for (const status of [401, 403, 503]) {
  for (const args of [['view'], ['edit', 'id', 'correction'], ['forget', 'id'], ['off']]) {
    test(`memory ${args[0]} refusal ${status} never reports success or retries`, async () => {
      const c = client(status, { detail: 'private server diagnostic' });
      await assert.rejects(run(['memory', ...args], c.options), error => error.status === status);
      assert.equal(c.output(), '');
      assert.equal(c.calls.length, 1);
    });
  }
}

test('memory view sanitizes returned terminal controls and credentials', async () => {
  const c = client(200, { text: `\u001b[31mcorrection ${token}` });
  await run(['memory', 'view'], c.options);
  assert.ok(!c.output().includes(token));
  assert.ok(!c.output().includes('\u001b'));
});
