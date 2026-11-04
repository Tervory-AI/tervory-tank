import { promises as fs } from 'node:fs';
import path from 'node:path';
import ignore, { Ignore } from 'ignore';
const blocked = /(^|\/)(?:\.git|node_modules|\.tmp|\.venv|dist|build|coverage|\.tervory-index|\.ssh|\.aws|\.azure|\.kube)(\/|$)|(^|\/)(?:\.env(?:\..*)?|.*\.(?:pem|key|p12|pfx|keystore)|id_(?:rsa|ed25519)(?:\.pub)?|credentials(?:\..*)?|secrets?(?:\..*)?|.*\.secret)(\/|$)/i;
const supported = /\.(?:[cm]?[jt]sx?|py|rs|go|java|kt|swift|c|h|cpp|hpp|cs|rb|php|sh|sql|md|txt|json|ya?ml|toml|html|css|vue|svelte)$/i;
export const slash = (p: string): string => p.split(path.sep).join('/');
export function secretText(text: string): boolean {
  return /-----BEGIN [A-Z ]*PRIVATE KEY-----|\b(?:AKIA|ASIA)[A-Z0-9]{16}\b|\bgh[pousr]_[A-Za-z0-9]{20,}|\bsk-(?:proj-)?[A-Za-z0-9_-]{20,}|(?:password|secret|api[_-]?key|access[_-]?token)\s*[:=]\s*["'][^"'\s]{8,}["']/i.test(text);
}
export interface Source { path: string; text: string }
// Never traverse symlinks, including symlinked files. Nested ignores use their own bases.
export async function* sources(root: string): AsyncGenerator<Source> {
  async function* walk(dir: string, rules: {base:string; matcher:Ignore}[]): AsyncGenerator<Source> {
    let entries;
    try { entries = await fs.readdir(dir, {withFileTypes:true}); } catch { return; }
    for (const name of ['.gitignore', '.tervoryignore']) {
      try {
        const filename = path.join(dir,name);
        if ((await fs.lstat(filename)).isSymbolicLink()) continue;
        rules = [...rules, {base:dir, matcher:ignore().add(await fs.readFile(filename,'utf8'))}];
      } catch { /* absent ignore file */ }
    }
    for (const entry of entries) {
      const absolute = path.join(dir,entry.name), relative = slash(path.relative(root,absolute));
      if (entry.isSymbolicLink() || blocked.test(relative)) continue;
      if (rules.some(r => r.matcher.ignores(slash(path.relative(r.base,absolute)) + (entry.isDirectory()?'/':'')))) continue;
      if (entry.isDirectory()) { yield* walk(absolute,rules); continue; }
      if (!entry.isFile() || !supported.test(relative)) continue;
      try {
        // Open without following symlinks where supported; check real path on all OSes.
        const real = await fs.realpath(absolute);
        if (real !== absolute || (await fs.lstat(absolute)).isSymbolicLink()) continue;
        if ((await fs.stat(absolute)).size > 256_000) continue;
        const buffer = await fs.readFile(absolute);
        if (buffer.includes(0)) continue;
        const text = buffer.toString('utf8');
        if (!secretText(text)) yield {path:relative,text};
      } catch { /* file removed during traversal */ }
    }
  }
  yield* walk(await fs.realpath(root),[]);
}
