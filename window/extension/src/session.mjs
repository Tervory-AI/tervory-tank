import { resolve } from 'node:path';
import { existsSync } from 'node:fs';
import { pathToFileURL } from 'node:url';
const packaged = resolve(import.meta.dirname, '../cli/src');
const development = resolve(import.meta.dirname, '../../../cli/src');
export const cli = name => import(pathToFileURL(resolve(existsSync(packaged) ? packaged : development, name)).href);

// A prompt has one consumer. Disposal/cancellation resolves it as a refusal.
export class InputQueue {
  values = []; pending;
  push(value) {
    if (this.pending) { const done = this.pending; this.pending = undefined; done(value); }
    else this.values.push(value);
  }
  next() {
    if (this.values.length) return Promise.resolve(this.values.shift());
    return new Promise(done => { this.pending = done; });
  }
  close() { this.values = []; this.pending?.(null); this.pending = undefined; }
}

export function hunks(file) {
  const lines = file.patch.split('\n'); const result = [];
  for (let i = 2; i < lines.length - 1;) {
    const match = /^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@/.exec(lines[i]);
    if (!match) throw Error('Invalid diff');
    let end = i + 1;
    while (end < lines.length - 1 && !lines[end].startsWith('@@')) end++;
    result.push({ label: `${file.name}:${match[1]}`, start: Number(match[1]), oldCount: Number(match[2] ?? 1), newCount: Number(match[4] ?? 1), lines: lines.slice(i + 1, end) });
    i = end;
  }
  return result;
}
export function selectedDiff(files, selected) {
  let index = 0; let result = '';
  for (const file of files) {
    let body = ''; let offset = 0;
    for (const hunk of hunks(file)) {
      if (selected.has(index++)) {
        const newStart = hunk.start + offset + (hunk.oldCount === 0 ? 1 : 0) - (hunk.newCount === 0 ? 1 : 0);
        body += `@@ -${hunk.start},${hunk.oldCount} +${Math.max(0, newStart)},${hunk.newCount} @@\n${hunk.lines.join('\n')}\n`;
        offset += hunk.newCount - hunk.oldCount;
      }
    }
    if (body) result += file.patch.split('\n').slice(0, 2).join('\n') + '\n' + body;
  }
  return result;
}
