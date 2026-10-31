/* Consume the REAL offline Tank replay through the browser and CLI decoders. */
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const { pathToFileURL } = require('node:url');
const root = path.resolve(__dirname, '../..');
const ts = require(path.join(process.env.COMMAND_TEST_TOOLS || path.join(root, 'workspace/node_modules'), 'typescript'));
require.extensions['.ts'] = (module, filename) => module._compile(ts.transpileModule(
  fs.readFileSync(filename, 'utf8'), { compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 } }
).outputText, filename);
const contract = require(path.join(root, 'workspace/app/chats/contract.ts'));
const payload = JSON.parse(fs.readFileSync(0, 'utf8'));
function stream() {
  const bytes = new TextEncoder().encode(payload.sse);
  return new ReadableStream({ start(controller) {
    for (let i = 0; i < bytes.length; i += 31) controller.enqueue(bytes.slice(i, i + 31));
    controller.close();
  } });
}
(async () => {
  const browserEvents = [];
  await contract.readEvents(stream(), event => browserEvents.push(event));
  assert.equal(browserEvents.length, 504);
  let panel = [];
  for (const event of browserEvents) {
    assert.equal(event.type, 'step');
    panel = contract.upsert(panel, event.data, 'step_id');
  }
  assert.equal(panel.length, 1);
  const snapshot = contract.normalizeSnapshot(payload.snapshot);
  const durable = snapshot.steps.find(step => step.step_id === panel[0].step_id);
  for (const key of ['label', 'status', 'link', 'ci_status', 'review_status']) assert.equal(panel[0][key], durable[key]);
  assert.equal(snapshot.thread.spent_usd, null);
  assert.equal(snapshot.job_receipts.find(receipt => receipt.step_id === durable.step_id).status, 'pending');
  const cli = await import(pathToFileURL(path.join(root, 'cli/src/client.mjs')).href);
  const cliEvents = [];
  for await (const event of cli.events(new Response(stream()))) cliEvents.push(event);
  assert.deepEqual(cliEvents.map(event => event.data), browserEvents.map(event => event.data));
  assert.equal(cliEvents.at(-1).data.link, durable.link);
  const legacy = {step_id:'legacy', ledger_id:'real-row', model:'pinned', tokens_in:2, tokens_out:3,
    cost_usd:.01, baseline_cost_usd:.03, saved_usd:.02, requested_model:'pinned', auto_cost_usd:987.654,
    auto_cost_status:'priced'};
  assert.equal(contract.receiptFor([legacy]).totals.auto_cost_usd, null);
  assert(!cli.receiptLines({rows:[legacy]}).join('').includes('987.654'));
  process.stdout.write('PASS: 504 actual Tank events drained by browser and CLI; durable panel matches; pending and legacy Auto stay unproven\n');
})().catch(error => { console.error(error); process.exitCode = 1; });
