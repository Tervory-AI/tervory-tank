#!/usr/bin/env node
import { createInterface } from 'node:readline/promises';
import { clearLine, cursorTo } from 'node:readline';
import { spawn } from 'node:child_process';
import { hostname } from 'node:os';
import { keychain, run, safe } from '../src/client.mjs';

// Sign-in is a browser device approval: no credential is typed, pasted, passed
// in argv or the environment, or written anywhere except the OS keychain.
function openBrowser(url) {
  if (!/^https:\/\/app\.tervory\.com\/cli\/device\?/.test(url)) return;
  const [command, args] = process.platform === 'darwin' ? ['open', [url]]
    : process.platform === 'win32' ? ['rundll32', ['url.dll,FileProtocolHandler', url]] : ['xdg-open', [url]];
  try {
    const child = spawn(command, args, { stdio: 'ignore', detached: true });
    child.on('error', () => {}); child.unref();
  } catch { /* The printed link still works. */ }
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
      open: openBrowser,
      deviceName: () => hostname(),
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
  const known = /^(?:Personal token refused\.|Tank |Login |Signed |Node 22|Unknown command|Invalid |A thread|Command |Run requires|This tool)/;
  process.stderr.write(known.test(error.message) ? `${safe(error.message)}\n` : 'Command failed. Check your OS keychain and Tank connection.\n');
  process.exitCode = 1;
} finally { readline?.close(); process.off('SIGINT', cancel); }
