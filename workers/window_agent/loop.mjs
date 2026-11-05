// The CLI owns the agent loop. This adapter supplies the approved background IO.
import { readFile } from 'node:fs/promises';
import { codeSession } from '/opt/tervory/cli/src/code-mode.mjs';
const job = JSON.parse(await readFile('/run/secrets/job.json', 'utf8'));
let supplied = false;
const controller = new AbortController();
process.on('SIGTERM', () => controller.abort());
const io = {
  interactive: true, signal: controller.signal, write() {},
  async prompt(label) {
    if (label === '> ') {
      if (supplied) return null;
      supplied = true;
      return job.prompt + '\nComplete the repository changes. Do not commit, push, merge, or call product tools; the worker publishes the result.';
    }
    // The user authorised edits and bounded code tools by starting this task.
    if (label === 'Apply [y/N] ' || label === 'Run [y/N] ') return 'y';
    return 'n';
  },
};
const tank = {
  async json(path, body) {
    if (path === '/v1/command/threads') return { thread_id: job.thread_id };
    if (path !== `/v1/command/threads/${job.thread_id}/code-turn`) throw new Error('Background action refused');
    const response = await fetch(`${job.tank_url}/v1/window-agents/worker/${job.tenant_id}/${job.job_id}/code-turn`, {
      method: 'POST', headers: { 'content-type': 'application/json' },
      body: JSON.stringify({ lease: job.lease, turn: body }), signal: AbortSignal.timeout(180000),
    });
    if (!response.ok) throw new Error('Code turn stopped');
    return response.json();
  },
};
await codeSession(tank, '/work/repo', 'auto', io, () => [], value => value);
