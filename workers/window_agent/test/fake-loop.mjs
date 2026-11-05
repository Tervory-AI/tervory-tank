// Acceptance fixture: use the real CLI loop; fake only its Tank transport.
import { codeSession } from '../../../cli/src/code-mode.mjs';
import { randomUUID } from 'node:crypto';
const thread = randomUUID();
const receipts = [];
const checkCommand = process.argv.includes('--check-command');
const finalRound = checkCommand ? 4 : 3;
let round = 0;
let prompted = false;
const tank = {
  async json(path, body) {
    if (path === '/v1/command/threads') return { thread_id: thread };
    if (path !== `/v1/command/threads/${thread}/code-turn` || body.model !== 'auto') throw new Error('Unexpected route');
    round++;
    if (checkCommand && round === 4) {
      const tool = JSON.parse(body.tool_results.at(-1).output).result;
      if (tool?.ran !== true || tool.code !== 0 || !tool.output.includes('sandbox-checked')) throw new Error('Command sandbox check failed');
    }
    return {
      answer: round === finalRound ? 'Updated the file.' : '',
      requests: round === 1 ? [{ name: 'read_file', arguments: { path: 'file.txt' } }] : round === 2 ? [
        { name: 'propose_edit', arguments: { path: 'file.txt', diff: '--- a/file.txt\n+++ b/file.txt\n@@ -1 +1 @@\n-old\n+new\n' } },
      ] : checkCommand && round === 3 ? [{ name: 'run_command', arguments: { command: 'printf sandbox-checked' } }] : [],
      receipt: { rows: [{ ledger_id: randomUUID(), cost_usd: 0 }] },
    };
  },
};
const io = { interactive: true, write() {}, async prompt(label) {
  if (label === '> ') { if (prompted) return null; prompted = true; return 'Update file.txt'; }
  return label === 'Apply [y/N] ' || (checkCommand && label === 'Run [y/N] ') ? 'y' : 'n';
} };
await codeSession(tank, process.argv[2], 'auto', io, receipt => { receipts.push(...receipt.rows); return []; }, value => value);
if (round !== finalRound || receipts.length !== finalRound) throw new Error('Missing receipt');
console.log(JSON.stringify({ receipts }));
