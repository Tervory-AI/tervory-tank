const fs = require('node:fs');
const path = require('node:path');
const assert = require('node:assert/strict');
const root = path.resolve(__dirname, '..');
const sources = new Map();
// Apply the deferred Tank patches in memory, accepting offset hunks just as git
// does. Every removed/context line must match; pinned vendor files stay intact.
for (const name of ['gate4.patch', 'gate5.patch']) {
  const lines = fs.readFileSync(path.join(root, 'tank-patches', name), 'utf8').split('\n');
  let file, before, cursor, output;
  const finish = () => { if (file) { output.push(...before.slice(cursor)); sources.set(file, output.join('\n')); } };
  for (let i = 0; i < lines.length; i++) {
    if (lines[i].startsWith('--- a/')) {
      finish(); file = lines[i].slice(6);
      assert.equal(lines[++i], '+++ b/' + file);
      before = (sources.get(file) ?? fs.readFileSync(path.join(root,file),'utf8')).split('\n');
      cursor = 0; output = []; continue;
    }
    if (!/^@@ /.test(lines[i])) continue;
    const removed = [], added = [];
    while (++i < lines.length && /^[ +\-]/.test(lines[i]) && !lines[i].startsWith('--- a/')) {
      if (lines[i][0] !== '+') removed.push(lines[i].slice(1));
      if (lines[i][0] !== '-') added.push(lines[i].slice(1));
    }
    i--;
    let start = cursor;
    while (start < before.length && !removed.every((line,j) => before[start+j] === line)) start++;
    assert(start < before.length, `Patch hunk does not match ${name}: ${file}`);
    output.push(...before.slice(cursor,start), ...added); cursor = start + removed.length;
  }
  finish();
}
module.exports = {root, sources, read: file => sources.get(file) ?? fs.readFileSync(path.join(root,file),'utf8')};
