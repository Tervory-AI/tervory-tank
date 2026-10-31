#!/usr/bin/env node
import { createInterface } from 'node:readline/promises';
import { clearLine, cursorTo } from 'node:readline';
import { keychain, run, safe } from '../src/client.mjs';

// A token is read only from a local terminal with echo disabled. No argv,
// environment-variable, file or shell-history credential transport exists.
async function secret(label) {
  if (!process.stdin.isTTY || !process.stdin.setRawMode) throw new Error('Login requires an interactive terminal.');
  process.stdout.write(label);
  const previous = Boolean(process.stdin.isRaw);
  process.stdin.setRawMode(true); process.stdin.resume();
  return new Promise((resolve, reject) => {
    let value = '';
    function finish(error) {
      process.stdin.off('data', onData);
      process.stdin.setRawMode(previous); process.stdin.pause();
      process.stdout.write('\n');
      error ? reject(error) : resolve(value);
    }
    function onData(chunk) {
      for (const char of chunk.toString('utf8')) {
        if (char === '\u0003' || char === '\u0004') { finish(new Error('Login cancelled.')); return; }
        if (char === '\r' || char === '\n') { finish(); return; }
        if (char === '\u007f' || char === '\b') value = value.slice(0, -1);
        else if (/^[A-Za-z0-9._-]$/.test(char) && value.length < 200) value += char;
        else { finish(new Error('Personal token refused.')); return; }
      }
    }
    process.stdin.on('data', onData);
  });
}

let readline;
const controller = new AbortController();
const cancel = () => { controller.abort(); readline?.close(); };
process.on('SIGINT', cancel);
try {
  if (Number(process.versions.node.split('.')[0]) !== 22) throw new Error('Node 22 is required.');
  await run(process.argv.slice(2), {
    store: {
      get: async () => (await keychain()).get(),
      set: async token => (await keychain()).set(token),
      remove: async () => (await keychain()).remove(),
    },
    io: {
      signal: controller.signal,
      write: value => process.stdout.write(safe(value)),
      // Provisional answer stays on one stderr line. Only the validated final
      // answer enters stdout, so replace events never append stale previews.
      preview: value => {
        if (!process.stderr.isTTY) return;
        clearLine(process.stderr, 0); cursorTo(process.stderr, 0);
        const width = Math.max(1, (process.stderr.columns || 80) - 1);
        process.stderr.write(Array.from(safe(value).replace(/\s/g, ' ')).slice(-width).join(''));
      },
      secret,
      prompt: async label => {
        if (!process.stdin.isTTY) return null;
        if (!readline) {
          readline = createInterface({ input: process.stdin, output: process.stdout });
          readline.on('SIGINT', cancel);
        }
        try { return await readline.question(label); } catch { return null; }
      },
    },
  });
} catch (error) {
  // Never print native-keychain or transport errors: they can include input.
  const known = /^(?:Personal token refused\.|Tank |Login |Node 22|Unknown command|Invalid |A thread|Command |Run requires|This tool)/;
  process.stderr.write(known.test(error.message) ? `${safe(error.message)}\n` : 'Command failed. Check your OS keychain and Tank connection.\n');
  process.exitCode = 1;
} finally { readline?.close(); process.off('SIGINT', cancel); }
