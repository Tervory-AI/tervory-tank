/** Scripted OFFLINE fake-Tank recording of the production CLI run/stream path.
 * No native keychain, real token, provider, browser, worker or production call.
 */
import { writeFile } from 'node:fs/promises';
import { run } from '../../cli/src/client.mjs';

const recording = [];
const started = performance.now();
const write = text => {
  recording.push([(performance.now() - started) / 1000, 'o', text.replaceAll('\n', '\r\n')]);
  process.stdout.write(text);
};
const answers = ['Show the fake receipt', 'N', '/exit'];
const token = `tv1.us-east.${'0'.repeat(32)}.${'x'.repeat(43)}`;
const encode = (kind, data) => `event: ${kind}\ndata: ${JSON.stringify(data)}\n\n`;
write('OFFLINE FAKE-TANK EVIDENCE — scripted input, synthetic ledger rows.\n');
write('Not a founder-browser test, native keychain test or measured model run.\n');
write('$ node tests/cli_1_20261031/record.mjs\n');
await run(['chat', 'fake-thread', '--model', 'fake-pinned-model'], {
  store: { get: async () => token },
  transport: async (url, init) => {
    if (url.endsWith('/cards/fake-card')) {
      if (JSON.parse(init.body).action !== 'cancel') throw new Error('Recording must cancel');
      return Response.json({ status: 'cancelled' });
    }
    if (!url.endsWith('/turn')) throw new Error('Unexpected recording route');
    const messages = [
      ['step', { status: 'running', actor: 'Fake Tank', label: 'Synthetic task' }],
      ['token', { text: 'This is a ' }], ['token', { text: 'fake-Tank answer.' }],
      ['step', { status: 'done', actor: 'Fake Tank', label: 'Synthetic task' }],
      ['receipt', { rows: [{ step_id: 'fake-step', model: 'fake-pinned-model', requested_model: 'fake-pinned-model',
        tokens_in: 20, tokens_out: 8, cost_usd: '0.000028', baseline_cost_usd: '0.000056', saved_usd: '0.000028',
        ledger_id: 'fake-ledger-1', auto_cost_status: 'unavailable', auto_cost_usd: null }] }],
      ['card', { card_id: 'fake-card', status: 'pending', summary: 'Synthetic paid action — cancel in this recording' }],
      ['done', { message_id: 'fake-message' }],
    ];
    const encoder = new TextEncoder();
    return new Response(new ReadableStream({ async start(controller) {
      for (const [kind, data] of messages) {
        await new Promise(resolve => setTimeout(resolve, 100));
        controller.enqueue(encoder.encode(encode(kind, data)));
      }
      controller.close();
    } }), { headers: { 'Content-Type': 'text/event-stream' } });
  },
  io: { write, prompt: async label => {
    const answer = answers.shift() ?? null;
    write(label + (answer ?? '') + '\n'); return answer;
  } },
});
write('Fake action cancelled; no provider or worker was called.\n');
const header = { version: 2, width: 120, height: 28, timestamp: Math.floor(Date.now() / 1000),
  title: 'CLI-1 OFFLINE fake-Tank scripted chat and receipt', env: { TERM: 'xterm-256color', SHELL: '/bin/bash' } };
await writeFile(new URL('./fake-tank-chat.cast', import.meta.url), [header, ...recording].map(JSON.stringify).join('\n') + '\n');
