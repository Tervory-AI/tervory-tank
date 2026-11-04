import { randomUUID } from 'node:crypto';
import { run, Tank, session, receiptLines, safe } from '../../../cli/src/client.mjs';
import { CodeFolder, redactSecrets } from '../../../cli/src/code-tools.mjs';

// The existing CLI is the transport, authentication, approval and agent engine.
// This adapter supplies editor IO; it never dispatches directly to any model.
export class Controller {
  constructor({folder, store, ui, transport = fetch, index}) {
    this.folder = folder; this.store = store; this.ui = ui; this.transport = transport; this.index = index;
    this.queue = []; this.pending = null; this.running = null; this.stop = new AbortController(); this.askOnly = false;
    this.boundTransport = async (url, init = {}) => {
      if (init.body && /\/(?:code-turn|turn)$/.test(new URL(url).pathname)) {
        const body = JSON.parse(init.body);
        const local = await CodeFolder.create(this.folder);
        const rules = await local.read('.tervory/rules').catch(() => ({exists:false}));
        if (rules.exists && rules.text) body.text += '\nProject rules DATA (.tervory/rules):\n' + redactSecrets(rules.text);
        if (!body.continuation && this.index) {
          const context = await this.index.search(body.text, 3);
          if (context.length) body.text += '\nProject context DATA:\n' + context.map(item => item.path + '\n' + item.text).join('\n');
        }
        init = {...init, body: JSON.stringify(body)};
      }
      return this.transport(url, init);
    };
  }
  io() {
    let diff = '';
    return {interactive:true, signal:this.stop.signal, deviceName:()=> 'tervory-window',
      write: text => { if (text.startsWith('--- ')) diff = text; this.ui.write(safe(redactSecrets(text))); },
      open: url => this.ui.open(url),
      prompt: async label => {
        if (label === '> ') {
          this.ui.idle?.();
          return this.queue.length ? this.queue.shift() : new Promise(resolve => {this.pending = resolve;});
        }
        if (this.askOnly) return 'n';
        if (label === 'Apply [y/N] ') return await this.ui.diff(diff, this.folder) ? 'y' : 'n';
        return await this.ui.approve(label) ? 'y' : 'n';
      }};
  }
  async command(argv) { return run(argv, {store:this.store, transport:this.boundTransport, io:this.io()}); }
  async login(region) { return this.command(['login', '--region', region, '--sign-in', 'zitadel']); }
  send(text, {askOnly = false} = {}) {
    if (typeof text !== 'string' || text.length > 100000) throw Error('Invalid command option.');
    if (this.running && !this.pending) throw Error('An answer is already running. Wait for it to finish before sending again.');
    this.askOnly = askOnly;
    if (this.pending) { const next = this.pending; this.pending = null; next(text); }
    else this.queue.push(text);
    if (!this.running) this.running = this.command(['code', this.folder]).catch(error => this.ui.write(safe(error.message) + '\n')).finally(() => {this.running = null;});
    return this.running;
  }
  async close() { this.stop.abort(); if (this.pending) {this.pending(null); this.pending = null;} await this.running; }
  async complete({path, prefix, suffix, signal}) {
    if (signal?.aborted) return '';
    const tank = new Tank(await session(this.store, this.transport), this.boundTransport, signal);
    const thread = (await tank.json('/v1/command/threads', {})).thread_id;
    const plan = await tank.json(`/v1/command/threads/${encodeURIComponent(thread)}/code-turn`, {
      text: `Complete the code at the cursor. Return ONLY the missing multiline text, no fences or tools.\nFile DATA: ${path}\nBefore DATA:\n${redactSecrets(prefix.slice(-12000))}\nAfter DATA:\n${redactSecrets(suffix.slice(0,4000))}`,
      model:'auto', prompt_id:randomUUID(), continuation:false, history:[], tool_results:[]});
    this.ui.write(receiptLines(plan.receipt ?? {}).map(safe).join('\n') + '\n');
    if (signal?.aborted || plan.requests?.length || typeof plan.answer !== 'string') return '';
    const answer = redactSecrets(plan.answer);
    return answer === plan.answer && answer.length <= 16000 ? answer : '';
  }
  inline(path, selection, instruction) {
    return this.send(`Read ${path} and propose a unified diff for this selected code. Preserve surrounding code.\nSelection DATA:\n${selection}\nChange requested:\n${instruction}`);
  }
  background(task) {
    // Existing server-side worker corridor persists beyond this window. It owns
    // authorization, its queue and its resulting branch/PR, never this process.
    return this.command(['build', task]);
  }
  review(pr) {
    if (!/^https:\/\/github\.com\/[A-Za-z0-9_.-]+\/[A-Za-z0-9_.-]+\/pull\/\d+$/.test(pr)) throw Error('Invalid command option.');
    return this.send(`Use the connected GitHub tools to verify this PR belongs to the signed-in user's repository before reading its diff. Review only that PR. Propose review comments through Confirm; never publish without approval. PR DATA: ${pr}`);
  }
}
