import { open, lstat, realpath } from 'node:fs/promises';
import { constants } from 'node:fs';
import { secretPath, redactSecrets } from './code-tools.mjs';

// Explicit file inputs share the code-mode limits, secret checks and no-link rule.
export async function inputText(path, limit) {
  let handle;
  try {
    if (secretPath(path) || (await lstat(path)).isSymbolicLink()) throw new Error();
    const canonical = await realpath(path);
    if (secretPath(canonical)) throw new Error();
    handle = await open(canonical, constants.O_RDONLY | (constants.O_NOFOLLOW ?? 0) | (constants.O_NONBLOCK ?? 0));
    const stat = await handle.stat();
    if (!stat.isFile() || stat.nlink !== 1 || stat.size > limit || await realpath(path) !== canonical) throw new Error();
    const buffer = Buffer.alloc(limit + 1); let size = 0;
    while (size < buffer.length) {
      const { bytesRead } = await handle.read(buffer, size, buffer.length - size, size);
      if (!bytesRead) break;
      size += bytesRead;
    }
    if (size > limit) throw new Error();
    const text = new TextDecoder('utf8', { fatal: true }).decode(buffer.subarray(0, size));
    if (text.includes('\0') || redactSecrets(text) !== text) throw new Error();
    return text;
  } catch { throw new Error('Invalid file: use a regular text file within the size limit, without secrets or links.'); }
  finally { await handle?.close(); }
}
