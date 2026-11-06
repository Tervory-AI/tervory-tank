import { open, lstat } from 'node:fs/promises';
import { constants } from 'node:fs';
import { homedir } from 'node:os';
import { join, basename } from 'node:path';
import { LIMITS, redactSecrets } from './code-tools.mjs';
import { ConfigurationError, missingSetting } from './configuration.mjs';

const refused = () => new Error('Code MCP refused.');
const identifier = /^[A-Za-z0-9_.-]+$/;
export async function mcpKeyring(server, name) {
  if (!identifier.test(server) || !identifier.test(name)) throw refused();
  try {
    const { Entry } = await import('@napi-rs/keyring');
    return new Entry('@tervory/cli/mcp', `${server}/${name}`, { linux: { store: 'secret-service' } });
  } catch {
    throw new ConfigurationError(`Code MCP keyring entry @tervory/cli/mcp/${server}/${name} is unavailable. Enable the OS keyring before connecting.`, [`@tervory/cli/mcp/${server}/${name}`]);
  }
}

export function serverIdentity(config) {
  return config.transport === 'http' ? `http:${new URL(config.url).origin}` : `stdio:${basename(config.command)}`;
}

export async function loadMCP(path = join(homedir(), '.tervory', 'mcp.json')) {
  let handle;
  try {
    const before = await lstat(path);
    if (!before.isFile() || before.isSymbolicLink()) throw refused();
    handle = await open(path, constants.O_RDONLY | (constants.O_NOFOLLOW ?? 0) | (constants.O_NONBLOCK ?? 0));
    const stat = await handle.stat();
    const after = await lstat(path);
    if (after.isSymbolicLink() || before.dev !== stat.dev || before.ino !== stat.ino || after.dev !== stat.dev || after.ino !== stat.ino) throw refused();
    if (!stat.isFile() || stat.nlink !== 1 || stat.size > LIMITS.fileBytes) throw refused();
    const buffer = Buffer.alloc(LIMITS.fileBytes + 1); const { bytesRead } = await handle.read(buffer, 0, buffer.length, 0);
    if (bytesRead > LIMITS.fileBytes) throw refused();
    const raw = new TextDecoder('utf8', { fatal: true }).decode(buffer.subarray(0, bytesRead));
    if (redactSecrets(raw) !== raw) throw refused();
    const value = JSON.parse(raw);
    if (value && typeof value === 'object' && !Array.isArray(value) && value.servers == null) throw missingSetting('~/.tervory/mcp.json: servers', 'Add your MCP server configuration before connecting.');
    if (!value || Object.keys(value).some(k => k !== 'servers') || !value.servers || Array.isArray(value.servers)) throw refused();
    for (const [name, config] of Object.entries(value.servers)) {
      if (!identifier.test(name) || !config || Object.keys(config).some(k => !['transport', 'command', 'args', 'url', 'env', 'headers'].includes(k))) throw refused();
      const required = field => {
        if (config[field] === undefined || config[field] === null || config[field] === '') throw missingSetting(`~/.tervory/mcp.json: servers.${name}.${field}`, 'Complete this server configuration before connecting.');
      };
      required('transport');
      if (config.transport === 'stdio') {
        required('command');
        if (typeof config.command !== 'string' || !config.command || /[\0\r\n]/.test(config.command) || config.url || config.headers) throw refused();
        if (config.args !== undefined && (!Array.isArray(config.args) || config.args.some(arg => typeof arg !== 'string' || /[\0\r\n]/.test(arg) || /(?:token|secret|password|api[-_]key)(?:=|$)/i.test(arg)))) throw refused();
      } else if (config.transport === 'http') {
        required('url');
        const url = new URL(config.url);
        if (url.protocol !== 'https:' || url.username || url.password || url.search || url.hash || config.command || config.args || config.env) throw refused();
      } else throw refused();
      for (const [key, ref] of Object.entries(config.env ?? config.headers ?? {})) {
        if (!identifier.test(key) || !ref || typeof ref !== 'object' || Object.keys(ref).join() !== 'keyring' || typeof ref.keyring !== 'string' || !identifier.test(ref.keyring)) throw refused();
      }
    }
    return value.servers;
  } catch (error) { if (error instanceof ConfigurationError) throw error; if (error.code === 'ENOENT' && !handle) return {}; throw refused(); }
  finally { await handle?.close(); }
}

export class MCPClients {
  constructor(tank, io, { load = loadMCP, keyring = mcpKeyring, transport = fetch } = {}) {
    Object.assign(this, { tank, io, load, keyring, transport }); this.clients = new Map(); this.values = new Set(); this.catalogue = [];
  }
  clean(value) {
    let text = String(value);
    for (const secret of this.values) if (secret) text = text.split(secret).join('[redacted]');
    return redactSecrets(text);
  }
  cleanObject(value) {
    if (typeof value === 'string') return this.clean(value);
    if (Array.isArray(value)) return value.map(item=>this.cleanObject(item));
    if (value && typeof value === 'object') return Object.fromEntries(Object.entries(value).map(([key,item])=>[this.clean(key),this.cleanObject(item)]));
    return value;
  }
  async allowed(config) {
    const policy = await this.tank.json('/v1/command/code-mcp-policy');
    if (!Array.isArray(policy.blocked)) throw refused();
    return !policy.blocked.includes('*') && !policy.blocked.includes(serverIdentity(config));
  }
  async tools(mode, headless) {
    if (headless || mode === 'plan') return [];
    const configs = await this.load(); const catalogue = [];
    for (const [name, config] of Object.entries(configs)) {
      if (!await this.allowed(config)) { await this.clients.get(name)?.client.close(); this.clients.delete(name); continue; }
      const fingerprint = JSON.stringify(config);
      if (this.clients.has(name) && this.clients.get(name).fingerprint !== fingerprint) { await this.clients.get(name).client.close(); this.clients.delete(name); }
      if (!this.clients.has(name)) {
        this.io.write(`MCP ${name}: ${config.transport === 'stdio' ? JSON.stringify([config.command, ...(config.args ?? [])]) : config.url}\n`);
        if (this.io.interactive !== true || (await this.io.prompt(`Connect MCP ${name} [y/N] `))?.trim().toLowerCase() !== 'y') continue;
        if (!await this.allowed(config)) throw refused();
        const secretEntries = {};
        for (const [key, ref] of Object.entries(config.env ?? config.headers ?? {})) {
          let secret;
          const missing = () => missingSetting(`@tervory/cli/mcp/${name}/${ref.keyring}`, `Run tervory mcp secret ${name} ${ref.keyring} before connecting.`);
          try { secret = await (await this.keyring(name, ref.keyring)).getPassword(); }
          catch { throw missing(); }
          if (typeof secret !== 'string' || !secret) throw missing();
          this.values.add(secret); secretEntries[key] = secret;
        }
        const { Client } = await import('@modelcontextprotocol/sdk/client/index.js');
        let channel;
        if (config.transport === 'stdio') {
          const { StdioClientTransport } = await import('@modelcontextprotocol/sdk/client/stdio.js');
          channel = new StdioClientTransport({ command: config.command, args: config.args ?? [], env: secretEntries, stderr: 'ignore', maxBufferSize: LIMITS.fileBytes });
        } else {
          const { StreamableHTTPClientTransport } = await import('@modelcontextprotocol/sdk/client/streamableHttp.js');
          const guarded = async (url, init) => {
            if (String(url) !== new URL(config.url).href) throw refused();
            const response = await this.transport(url, { ...init, redirect: 'error', signal: AbortSignal.any([AbortSignal.timeout(LIMITS.commandMs), ...(init?.signal ? [init.signal] : []), ...(this.io.signal ? [this.io.signal] : [])]) });
            if (response.status >= 300 && response.status < 400) { await response.body?.cancel(); throw refused(); }
            let size = 0;
            return new Response(response.body?.pipeThrough(new TransformStream({ transform(chunk, controller) { size += chunk.byteLength; if (size > LIMITS.fileBytes) throw refused(); controller.enqueue(chunk); } })), { status: response.status, headers: response.headers });
          };
          channel = new StreamableHTTPClientTransport(new URL(config.url), { fetch: guarded, requestInit: { headers: secretEntries, redirect: 'error' }, reconnectionOptions: { maxRetries: 0, initialReconnectionDelay: 1000, maxReconnectionDelay: 1000, reconnectionDelayGrowFactor: 1 } });
        }
        const client = new Client({ name: 'tervory', version: '0.11.0' }, { capabilities: {} });
        try { await client.connect(channel, { timeout: LIMITS.commandMs, signal: this.io.signal }); }
        catch { await client.close().catch(() => {}); throw refused(); }
        this.clients.set(name, { client, config, fingerprint });
      }
      const { client } = this.clients.get(name); let cursor; const seen = new Set();
      do {
        const page = await client.listTools(cursor ? { cursor } : {}, { timeout: LIMITS.commandMs, signal: this.io.signal });
        for (const tool of page.tools) {
          if (!identifier.test(tool.name) || this.clean(tool.name) !== tool.name) throw refused();
          catalogue.push({ server: name, name: tool.name, description: this.clean(tool.description ?? ''), inputSchema: this.cleanObject(tool.inputSchema) });
        }
        if (Buffer.byteLength(JSON.stringify(catalogue)) > LIMITS.fileBytes) throw refused();
        cursor = page.nextCursor;
        if (cursor && seen.has(cursor)) throw refused(); seen.add(cursor);
      } while (cursor);
    }
    this.catalogue = catalogue; return catalogue;
  }
  async call(args, mode, headless) {
    const server = this.clients.get(args.server);
    if (headless || mode === 'plan' || ['search','fetch','web_search','web_fetch'].includes(args.tool) || !server || !this.catalogue.some(t => t.server === args.server && t.name === args.tool) || !await this.allowed(server.config)) throw refused();
    this.io.write(this.clean(JSON.stringify({ server: args.server, tool: args.tool, arguments: args.arguments ?? {} })) + '\n');
    if (this.io.interactive !== true || (await this.io.prompt('Run MCP tool [y/N] '))?.trim().toLowerCase() !== 'y') return { status: 'cancelled' };
    if (!await this.allowed(server.config)) throw refused();
    try {
      const result = await server.client.callTool({ name: args.tool, arguments: args.arguments ?? {} }, undefined, { timeout: LIMITS.commandMs, signal: this.io.signal });
      const clean = this.cleanObject(result); if (Buffer.byteLength(JSON.stringify(clean)) > LIMITS.fileBytes) throw refused();
      return clean;
    } catch { throw refused(); }
  }
  async close() { await Promise.allSettled([...this.clients.values()].map(({ client }) => client.close())); this.clients.clear(); this.values.clear(); }
}
