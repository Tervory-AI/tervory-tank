// Offline worker proof for the real terminal entrypoint. No network, real
// credentials, keychain reads or model calls. Not founder acceptance.
// node --import ./tests/cli_code_mode/worker-proof.mjs cli/bin/tervory.mjs code .
import { registerHooks } from 'node:module';
import assert from 'node:assert/strict';
import { resolve } from 'node:path';

if (!process.stdin.isTTY || !process.stdout.isTTY) throw Error('Worker proof requires a real terminal');
const runner = process.env.CODE_PROOF_PYTHON;
if (!runner || !runner.startsWith('/') || runner.includes("'")) throw Error('CODE_PROOF_PYTHON must name the existing test interpreter');
const token = 'tv1.us-east.' + '1'.repeat(32) + '.' + 'x'.repeat(43);
registerHooks({
  resolve(specifier, context, next) {
    if (specifier !== '@napi-rs/keyring') return next(specifier, context);
    return { shortCircuit: true, url: 'data:text/javascript,' + encodeURIComponent(
      `export class Entry { getPassword() { return ${JSON.stringify(token)}; } setPassword() { throw Error('No writes'); } deletePassword() { throw Error('No writes'); } }`) };
  },
});
let round = 0;
globalThis.fetch = async (url, init) => {
  assert.equal(new URL(url).origin, 'https://app.tervory.com');
  assert.equal(init.headers.Authorization, 'Bearer ' + token);
  if (url.endsWith('/threads')) return Response.json({ thread_id: 'offline-worker-proof' });
  assert(url.endsWith('/code-turn'));
  const body = JSON.parse(init.body);
  if (++round === 1) return Response.json({ answer: '', requests: [{ name: 'run_command', arguments: {
    command: `'${runner}' -m pytest -q tests/test_schema.py`,
  } }] });
  const result = JSON.parse(body.tool_results.at(-1).output).result;
  assert.equal(result.code, 0, result.output);
  assert.match(result.output, /2 passed/);
  assert.equal(body.continuation, true);
  return Response.json({ answer: 'Offline worker proof: the existing schema test file passed inside the sandbox.', requests: [] });
};
assert.equal(resolve(process.argv.at(-1)), process.cwd());
