import { readFile } from 'node:fs/promises';

const ORIGINS = Object.freeze({ 'us-east': 'https://app.tervory.com', za: 'https://za.tervory.com' });
const ENVELOPE = /^tv1\.(us-east|za)\.[0-9a-f]{32}\.[A-Za-z0-9_-]{43}$/;

export function originFor(token) {
  if (typeof token !== 'string' || !ENVELOPE.test(token)) throw new Error('Personal token refused.');
  return ORIGINS[token.split('.')[1]];
}

// Terminal output is untrusted server data: strip terminal controls and bearer
// strings even if an upstream error or model response accidentally contains one.
export function safe(value) {
  return String(value).replace(/tv1\.(?:us-east|za)\.[0-9a-f]{32}\.[A-Za-z0-9_-]+/g, '[redacted]')
    .replace(/\x1b\][^\x07]*(?:\x07|$)/g, '')
    .replace(/\x1b\[[0-?]*[ -/]*[@-~]/g, '')
    .replace(/[\x00-\x08\x0b-\x1f\x7f]/g, '');
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
  constructor(token, transport = fetch) {
    this.origin = originFor(token);
    this.#token = token;
    this.transport = transport;
  }
  async request(path, body, method = body === undefined ? 'GET' : 'POST') {
    if (!/^\/v1\/command\/[A-Za-z0-9/?=&._%-]+$/.test(path)) throw new Error('Command path refused.');
    let response;
    try {
      response = await this.transport(this.origin + path, {
        method, redirect: 'error', headers: { Authorization: `Bearer ${this.#token}`, 'Content-Type': 'application/json' },
        ...(body === undefined ? {} : { body: JSON.stringify(body) }),
      });
    } catch { throw new Error('Tank connection failed.'); }
    if (!response.ok) {
      // Do not print error bodies, request objects or transport exceptions.
      throw new Error(response.status === 401 ? 'Personal token refused.' : `Tank refused the command (${response.status}).`);
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
  const cards = []; let complete = false;
  for await (const event of events(response)) {
    switch (event.kind) {
      case 'token': io.write(safe(event.data.text)); break;
      case 'step': io.write(`\n[${safe(event.data.status)}] ${safe(event.data.actor)}: ${safe(event.data.label)}\n`); break;
      case 'receipt': io.write(`\n${receiptLines(event.data).map(safe).join('\n')}\n`); break;
      case 'card': if (!event.data.status || event.data.status === 'pending') cards.push(event.data); break;
      case 'error': throw new Error('Tank could not complete the turn.');
      case 'done': complete = true; break;
    }
  }
  if (!complete) throw new Error('Tank stream interrupted; the turn was not retried.');
  for (const card of cards) await confirmCard(tank, card, io);
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
  const tank = new Tank(token, transport);
  if (name === 'models') { io.write(safe(JSON.stringify(await tank.json('/v1/command/models'), null, 2)) + '\n'); return; }
  if (name === 'threads') {
    for (const thread of await tank.json('/v1/command/threads')) io.write(`${safe(thread.thread_id)} ${safe(thread.title)} | spent ${amount(thread.spent_usd)} | saved ${amount(thread.saved_usd)}\n`);
    return;
  }
  if (name === 'receipts') {
    if (!rest[0]) throw new Error('A thread or task identifier is required.');
    const result = await tank.json(`/v1/command/threads/${encodeURIComponent(rest[0])}`);
    io.write(receiptLines({ rows: result.receipts ?? result.thread?.receipts ?? [] }).map(safe).join('\n') + '\n'); return;
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
    await confirmCard(tank, card, io); return;
  }
  if (name === 'run') {
    if (rest.length !== 2) throw new Error('Run requires an agent and task.');
    let arguments_ = {};
    try { arguments_ = flags.args ? JSON.parse(flags.args) : {}; } catch { throw new Error('Invalid task arguments.'); }
    if (flags.file) arguments_.file = await readFile(flags.file, 'utf8');
    const tool = `${rest[0]}.${rest[1]}`;
    const allowed = await tank.json('/v1/command/tools');
    if (!allowed.includes(tool)) throw new Error('This tool is not available to this user.');
    const card = await tank.json(`/v1/command/threads/${encodeURIComponent(thread)}/actions`, { tool, arguments: arguments_ });
    await confirmCard(tank, card, io); return;
  }
  const attachments = flags.file ? [{ name: flags.file.split(/[\\/]/).pop(), text: await readFile(flags.file, 'utf8') }] : [];
  if (name === 'ask') { await showTurn(tank, thread, rest.join(' '), flags.model ?? 'auto', attachments, io); return; }
  while (true) {
    const text = await io.prompt('> ');
    if (text === null || text.trim() === '/exit') break;
    if (!text.trim()) continue;
    await showTurn(tank, thread, text, flags.model ?? 'auto', attachments, io);
  }
}
