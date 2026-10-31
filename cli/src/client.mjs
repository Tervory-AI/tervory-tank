import { readFile } from 'node:fs/promises';
import { basename, extname } from 'node:path';
import { parse } from 'csv-parse/sync';

const ORIGINS = Object.freeze({ 'us-east': 'https://app.tervory.com', za: 'https://za.tervory.com' });
const ENVELOPE = /^tv1\.(us-east|za)\.[0-9a-f]{32}\.[A-Za-z0-9_-]{43}$/;

export function originFor(token) {
  if (typeof token !== 'string' || !ENVELOPE.test(token)) throw new Error('Personal token refused.');
  return ORIGINS[token.split('.')[1]];
}

// Terminal output is untrusted server data: strip terminal controls and bearer
// strings even if an upstream error or model response accidentally contains one.
export function safe(value) {
  const sanitizer = new StreamSanitizer();
  return sanitizer.write(value) + sanitizer.end();
}
const redact = value => value.replace(/tv1\.(?:us-east|za)\.[0-9a-f]{32}\.[A-Za-z0-9_-]+/g, '[redacted]');

/** Keep terminal-control and credential state across arbitrary SSE chunks. */
export class StreamSanitizer {
  #escape = '';
  #candidate = '';
  #dropping = false;
  write(value) {
    let out = '';
    const printable = char => {
      if (this.#dropping) {
        if (/^[A-Za-z0-9_.-]$/.test(char)) return;
        this.#dropping = false;
      }
      if (this.#candidate.startsWith('tv1.')) {
        if (/^[A-Za-z0-9_.-]$/.test(char)) {
          this.#candidate += char;
          if (this.#candidate.length > 256) {
            out += '[redacted]'; this.#candidate = ''; this.#dropping = true;
          }
          return;
        }
        out += redact(this.#candidate); this.#candidate = '';
      }
      this.#candidate += char;
      while (this.#candidate && !'tv1.'.startsWith(this.#candidate)) {
        out += this.#candidate[0]; this.#candidate = this.#candidate.slice(1);
      }
    };
    for (const char of String(value)) {
      if (this.#escape === 'esc') {
        this.#escape = char === '[' ? 'csi' : [']', 'P', '^', '_'].includes(char) ? 'string' : '';
        continue;
      }
      if (this.#escape === 'csi') {
        if (/^[\x40-\x7e]$/.test(char)) this.#escape = '';
        continue;
      }
      if (this.#escape === 'string') {
        if (char === '\x07' || char === '\x9c') this.#escape = '';
        else if (char === '\x1b') this.#escape = 'string-esc';
        continue;
      }
      if (this.#escape === 'string-esc') {
        this.#escape = char === '\\' ? '' : char === '\x1b' ? 'string-esc' : 'string';
        continue;
      }
      if (char === '\x1b') { this.#escape = 'esc'; continue; }
      if (char === '\x9b') { this.#escape = 'csi'; continue; }
      if (['\x90', '\x9d', '\x9e', '\x9f'].includes(char)) { this.#escape = 'string'; continue; }
      if (/[\x00-\x08\x0b-\x1f\x7f-\x9f]/.test(char)) continue;
      printable(char);
    }
    return out;
  }
  end() {
    const out = redact(this.#candidate);
    this.#candidate = ''; this.#escape = ''; this.#dropping = false;
    return out;
  }
}

export async function keychain() {
  const { Entry } = await import('@napi-rs/keyring');
  const entry = new Entry('@tervory/cli', 'personal-token', { linux: { store: 'secret-service' } });
  return {
    get: () => entry.getPassword(),
    set: value => entry.setPassword(value),
    remove: () => entry.deletePassword(),
  };
}

export class Tank {
  #token;
  constructor(token, transport = fetch, signal) {
    this.origin = originFor(token);
    this.#token = token;
    this.transport = transport;
    this.signal = signal;
  }
  async request(path, body, method = body === undefined ? 'GET' : 'POST') {
    if (!/^\/v1\/command\/[A-Za-z0-9/?=&._%-]+$/.test(path)) throw new Error('Command path refused.');
    let response;
    try {
      response = await this.transport(this.origin + path, {
        method, redirect: 'error', signal: this.signal, headers: { Authorization: `Bearer ${this.#token}`, 'Content-Type': 'application/json' },
        ...(body === undefined ? {} : { body: JSON.stringify(body) }),
      });
    } catch { throw new Error(this.signal?.aborted ? 'Command cancelled; no action was retried.' : 'Tank connection failed.'); }
    if (!response.ok) {
      // Do not print error bodies, request objects or transport exceptions.
      const error = new Error(response.status === 401 ? 'Personal token refused.' : `Tank refused the command (${response.status}).`);
      error.status = response.status;
      throw error;
    }
    return response;
  }
  async json(path, body, method) { return (await this.request(path, body, method)).json(); }
}

export async function* events(response) {
  if (!response.body) throw new Error('Tank stream missing.');
  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = '';
  try {
    while (true) {
      const { value, done } = await reader.read();
      buffer += decoder.decode(value, { stream: !done });
      buffer = buffer.replace(/\r\n/g, '\n');
      if (buffer.length > 2_000_000) throw new Error('Tank event exceeds the limit.');
      let boundary;
      while ((boundary = buffer.indexOf('\n\n')) >= 0) {
        const frame = buffer.slice(0, boundary); buffer = buffer.slice(boundary + 2);
        let kind = 'message'; const data = [];
        for (const line of frame.split('\n')) {
          if (line.startsWith('event:')) kind = line.slice(6).trim();
          if (line.startsWith('data:')) data.push(line.slice(5).trimStart());
        }
        if (data.length) {
          let parsed;
          try { parsed = JSON.parse(data.join('\n')); } catch { throw new Error('Tank sent an invalid event.'); }
          yield { kind, data: parsed };
        }
      }
      if (done) {
        if (buffer.trim()) throw new Error('Tank stream interrupted.');
        break;
      }
    }
  } finally { reader.releaseLock(); }
}

const amount = value => value === null || value === undefined ? 'pending' : String(value);
export function receiptLines(receipt) {
  const rows = receipt.rows ?? [];
  if (!rows.length) return ['Receipt pending'];
  return rows.map(row => {
    const auto = row.auto_cost_status === 'recorded' && row.auto_ledger_id
      ? `${amount(row.auto_cost_usd)} [ledger ${row.auto_ledger_id}]` : 'unavailable (no historical ledger evidence)';
    return `${row.model === 'code' ? 'code (no model)' : row.model} | tokens ${row.tokens_in}/${row.tokens_out}`
      + ` | cost ${amount(row.cost_usd)} | baseline ${amount(row.baseline_cost_usd)}`
      + ` | saved ${amount(row.saved_usd)} | ledger ${row.ledger_id}`
      + (row.requested_model && row.requested_model !== 'auto' ? ` | Auto ${auto}` : '');
  });
}

export async function confirmCard(tank, card, io) {
  io.write(`${safe(card.summary)}\n`);
  // Any response except an explicit yes cancels, including EOF.
  const answer = await io.prompt('Confirm [y/N] ');
  const action = /^(y|yes)$/i.test(answer?.trim() ?? '') ? 'confirm' : 'cancel';
  return tank.json(`/v1/command/cards/${encodeURIComponent(card.card_id)}`, { action });
}

export async function showTurn(tank, thread, text, model, attachments, io) {
  const response = await tank.request(`/v1/command/threads/${encodeURIComponent(thread)}/turn`, { text, model, attachments });
  const cards = new Map(); const receipts = []; let complete = false; let lastSeq = 0;
  let sanitizer = new StreamSanitizer(); let answer = '';
  for await (const event of events(response)) {
    if (Number.isSafeInteger(event.data.seq)) {
      if (event.data.seq <= lastSeq) continue;
      lastSeq = event.data.seq;
    }
    switch (event.kind) {
      case 'token':
        if (event.data.replace) { sanitizer = new StreamSanitizer(); answer = ''; }
        answer += sanitizer.write(event.data.text);
        if (answer.length > 2_000_000) throw new Error('Tank answer exceeds the limit.');
        io.preview?.(answer); break;
      case 'step':
        io.preview?.('');
        io.write(`\n[${safe(event.data.status)}] ${safe(event.data.actor)}: ${safe(event.data.label)}\n`);
        io.preview?.(answer); break;
      case 'receipt': receipts.push(event.data); break;
      case 'card': if (!event.data.status || event.data.status === 'pending') cards.set(event.data.card_id, event.data); break;
      case 'error': io.preview?.(''); throw new Error('Tank could not complete the turn.');
      case 'done': complete = true; break;
    }
  }
  io.preview?.('');
  if (!complete) throw new Error('Tank stream interrupted; the turn was not retried.');
  io.write(answer + sanitizer.end());
  for (const receipt of receipts) io.write(`\n${receiptLines(receipt).map(safe).join('\n')}\n`);
  for (const card of cards.values()) {
    const result = await confirmCard(tank, card, io);
    if (result.status !== 'cancelled') await followThread(tank, thread, result, io);
  }
}

export async function followThread(tank, thread, card, io, { limit = 240, interval = 500 } = {}) {
  const seen = new Map();
  for (let poll = 0; poll < limit; poll++) {
    if (io.signal?.aborted) throw new Error('Command cancelled; no action was retried.');
    const snapshot = await tank.json(`/v1/command/threads/${encodeURIComponent(thread)}`);
    const tracked = new Set([card.card_id, card.build_id].filter(Boolean));
    const steps = (snapshot.steps ?? []).filter(step => tracked.has(step.step_id));
    for (const step of steps) {
      const value = JSON.stringify(step);
      if (seen.get(step.step_id) === value) continue;
      seen.set(step.step_id, value);
      io.write(`[${safe(step.status)}] ${safe(step.actor)}: ${safe(step.label)}${step.link ? ` ${safe(step.link)}` : ''}\n`);
    }
    for (const row of snapshot.receipts ?? []) {
      if (!tracked.has(row.step_id)) continue;
      const key = `receipt:${row.ledger_id}`; const value = JSON.stringify(row);
      if (seen.get(key) === value) continue;
      seen.set(key, value); io.write(receiptLines({ rows: [row] }).map(safe).join('\n') + '\n');
    }
    const stored = (snapshot.cards ?? []).find(item => item.card_id === card.card_id);
    if (['failed', 'unknown', 'cancelled'].includes(stored?.status)) return;
    if (steps.length && steps.every(step => ['done', 'failed'].includes(step.status))
        && !steps.some(step => step.receipt_status === 'pending')) return;
    if (poll + 1 < limit) {
      if (io.wait) await io.wait(interval);
      else await new Promise((resolve, reject) => {
        const cancel = () => { clearTimeout(timer); reject(new Error('Command cancelled; no action was retried.')); };
        const timer = setTimeout(() => { io.signal?.removeEventListener('abort', cancel); resolve(); }, interval);
        io.signal?.addEventListener('abort', cancel, { once: true });
      });
    }
  }
  io.write(`Work is still pending. Reopen thread ${safe(thread)} to continue watching.\n`);
}

export function options(argv) {
  const args = []; const flags = {};
  for (let i = 0; i < argv.length; i++) {
    if (!argv[i].startsWith('--')) { args.push(argv[i]); continue; }
    const flag = argv[i].slice(2);
    if (!['model', 'thread', 'file', 'args'].includes(flag) || flags[flag] !== undefined || !argv[i + 1] || argv[i + 1].startsWith('--')) {
      throw new Error('Invalid command option.');
    }
    flags[flag] = argv[++i];
  }
  return { args, flags };
}

export async function run(argv, { store, transport, io }) {
  const { args, flags } = options(argv); const [name, ...rest] = args;
  if (!name || name === 'help') {
    io.write('tervory login | logout | chat [thread] | ask "question" | threads | run <agent> <task> [--file path] [--args JSON] | build "change" | receipts <thread|task> | models\n');
    return;
  }
  if (name === 'login') {
    if (rest.length || Object.keys(flags).length) throw new Error('Login accepts no arguments.');
    const token = await io.secret('Personal token: ');
    const tank = new Tank(token, transport);
    await tank.json('/v1/command/tools'); // Validate revocation before persistence.
    await store.set(token);
    io.write('Personal token saved in the OS keychain.\n'); return;
  }
  if (name === 'logout') { await store.remove(); io.write('Personal token removed from the OS keychain.\n'); return; }
  const token = await store.get();
  const tank = new Tank(token, transport, io.signal);
  if (name === 'models') { io.write(safe(JSON.stringify(await tank.json('/v1/command/models'), null, 2)) + '\n'); return; }
  if (name === 'threads') {
    for (const thread of await tank.json('/v1/command/threads')) io.write(`${safe(thread.thread_id)} ${safe(thread.title)} | spent ${amount(thread.spent_usd)} | saved ${amount(thread.saved_usd)}\n`);
    return;
  }
  if (name === 'receipts') {
    if (!rest[0]) throw new Error('A thread or task identifier is required.');
    let result;
    try {
      result = await tank.json(`/v1/command/threads/${encodeURIComponent(rest[0])}`);
    } catch (error) {
      if (error.status !== 404) throw error;
      result = await tank.json(`/v1/command/tasks/${encodeURIComponent(rest[0])}/receipts`);
    }
    io.write(receiptLines({ rows: result.rows ?? result.receipts ?? [] }).map(safe).join('\n') + '\n'); return;
  }
  if (!['ask', 'chat', 'run', 'build'].includes(name)) throw new Error('Unknown command.');
  if (name !== 'chat' && !rest.length) throw new Error('Command text is required.');
  const thread = flags.thread ?? (name === 'chat' ? rest[0] : undefined)
    ?? (await tank.json('/v1/command/threads', {})).thread_id;
  io.write(`Thread ${safe(thread)}\n`);
  if (name === 'build') {
    const brief = rest.join(' ');
    io.write(safe(brief) + '\n');
    const card = await tank.json('/v1/command/build', { thread_id: thread, brief_markdown: brief });
    const result = await confirmCard(tank, card, io);
    if (result.status !== 'cancelled') await followThread(tank, thread, result, io);
    return;
  }
  if (name === 'run') {
    if (rest.length !== 2) throw new Error('Run requires an agent and task.');
    let arguments_ = {};
    try { arguments_ = flags.args ? JSON.parse(flags.args) : {}; } catch { throw new Error('Invalid task arguments.'); }
    const tool = `${rest[0]}.${rest[1]}`;
    if (flags.file) {
      if (tool !== 'base.batch') throw new Error('Invalid file option for this tool; use --args with its Tank schema.');
      const text = await readFile(flags.file, 'utf8');
      if (Buffer.byteLength(text) > 2_000_000) throw new Error('Invalid file size.');
      try {
        arguments_.records = parse(text, { columns: true, bom: true, skip_empty_lines: true, max_record_size: 200_000 });
      } catch { throw new Error('Invalid CSV file.'); }
      arguments_.batch ??= basename(flags.file, extname(flags.file));
    }
    const allowed = await tank.json('/v1/command/tools');
    if (!allowed.includes(tool)) throw new Error('This tool is not available to this user.');
    const card = await tank.json(`/v1/command/threads/${encodeURIComponent(thread)}/actions`, { tool, arguments: arguments_ });
    const result = await confirmCard(tank, card, io);
    if (result.status !== 'cancelled') await followThread(tank, thread, result, io);
    return;
  }
  const attachments = flags.file ? [{ name: flags.file.split(/[\\/]/).pop(), text: await readFile(flags.file, 'utf8') }] : [];
  if (name === 'ask') { await showTurn(tank, thread, rest.join(' '), flags.model ?? 'auto', attachments, io); return; }
  if (rest[0] || flags.thread) {
    const snapshot = await tank.json(`/v1/command/threads/${encodeURIComponent(thread)}`);
    for (const message of snapshot.messages ?? []) io.write(`${safe(message.role)}: ${safe(message.content)}\n`);
    for (const step of snapshot.steps ?? []) io.write(`[${safe(step.status)}] ${safe(step.actor)}: ${safe(step.label)}\n`);
    for (const card of snapshot.cards ?? []) {
      if (['confirmed', 'executing'].includes(card.status)) await followThread(tank, thread, card, io);
    }
  }
  while (true) {
    const text = await io.prompt('> ');
    if (text === null || text.trim() === '/exit') break;
    if (!text.trim()) continue;
    await showTurn(tank, thread, text, flags.model ?? 'auto', attachments, io);
  }
}
