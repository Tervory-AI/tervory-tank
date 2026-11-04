// Acceptance fixture: use the real CLI loop; fake only its Tank transport.
import { codeSession } from '../../../cli/src/code-mode.mjs';
import { randomUUID } from 'node:crypto';
const thread = randomUUID();
const receipts = [];
let round = 0;
let prompted = false;
const tank = {
  async json(path, body) {
    if (path === '/v1/command/threads') return { thread_id: thread };
    if (path !== `/v1/command/threads/${thread}/code-turn` || body.model !== 'auto') throw new Error('Unexpected route');
    round++;
    return {
      answer: round === 3 ? 'Updated the file.' : '',
      requests: round === 1 ? [{ name: 'read_file', arguments: { path: 'file.txt' } }] : round === 2 ? [
        { name: 'propose_edit', arguments: { path: 'file.txt', diff: '--- a/file.txt\n+++ b/file.txt\n@@ -1 +1 @@\n-old\n+new\n' } },
      ] : [],
      receipt: { rows: [{ ledger_id: randomUUID(), cost_usd: 0 }] },
    };
  },
};
const io = { interactive: true, write() {}, async prompt(label) {
  if (label === '> ') { if (prompted) return null; prompted = true; return 'Update file.txt'; }
  return label === 'Apply [y/N] ' ? 'y' : 'n';
} };
await codeSession(tank, process.argv[2], 'auto', io, receipt => { receipts.push(...receipt.rows); return []; }, value => value);
if (round !== 3 || receipts.length !== 3) throw new Error('Missing receipt');
console.log(JSON.stringify({ receipts }));
