const fs = require('node:fs');
const path = require('node:path');
const assert = require('node:assert/strict');
const root = path.resolve(__dirname, '..');
const sources = new Map();
// All deferred sources are now integrated; keep the patch paths as a manifest.
for (const name of ['gate4.patch', 'gate5.patch']) {
 const patch = fs.readFileSync(path.join(root, 'tank-patches/base', name), 'utf8');
 for (const match of patch.matchAll(/^\+\+\+ b\/(.+)$/gm)) sources.set(match[1], fs.readFileSync(path.join(root, match[1]), 'utf8'));
}
module.exports = {root, sources, read: file => sources.get(file) ?? fs.readFileSync(path.join(root,file),'utf8')};
