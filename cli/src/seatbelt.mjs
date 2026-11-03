// Adapted from openai/codex, Apache-2.0, commit
// 6b2a2757de696c2506ee460c49c66a8e2bed65e0:
// codex-rs/sandboxing/src/seatbelt_base_policy.sbpl (unchanged alongside this file).
// Changes: add only folder/system-runtime reads, folder writes, explicit secret
// and network denies. Do not include upstream broad read-only platform defaults.
import { readFile } from 'node:fs/promises';

const quote = value => JSON.stringify(value);
const fold = value => value.replace(/[a-z]/g, c => `[${c}${c.toUpperCase()}]`);
const secrets = fold('(^|/)([.]git|[.]env[^/]*|id_[^/]*|[^/]*[.](pem|key)|[.]ssh|[.]config|keychains|keyrings)(/|$)');

export async function seatbeltProfile(root, mounts = []) {
  const base = await readFile(new URL('./seatbelt-base.sbpl', import.meta.url), 'utf8');
  const runtime = [];
  for (let i = 0; i < mounts.length;) {
    const operation = mounts[i++];
    if (operation === '--ro-bind') {
      const source = mounts[i++], target = mounts[i++];
      // Darwin uses canonical host paths instead of a synthetic mount tree.
      // /dev/null masks are replaced by the deny rule below.
      if (source !== '/dev/null') runtime.push(source, target);
    } else if (operation === '--symlink') { i += 2; }
    else if (operation === '--tmpfs') { i++; }
    else throw new Error('Code tool refused.');
  }
  const roots = [...new Set([root, '/bin', '/usr/bin', '/usr/lib', '/usr/share', '/System/Library', ...runtime])];
  const paths = roots.map(path => `(subpath ${quote(path)})`).join('\n');
  return base + `
; Tervory additions: minimum system/runtime reads, selected-folder writes only.
(allow file-read* file-map-executable ${paths})
(allow file-read-metadata (path-ancestors ${quote(root)}))
(allow file-read-metadata (literal "/") (literal "/dev") (literal "/private") (literal "/private/var"))
(allow file-read* (literal "/dev/null") (literal "/dev/zero") (literal "/dev/random") (literal "/dev/urandom"))
(allow file-read* file-write-data (subpath "/dev/fd"))
(allow file-write* (subpath ${quote(root)}))
(deny file-read* file-write* file-map-executable (regex #${quote(secrets)}))
(deny network*)
`;
}
