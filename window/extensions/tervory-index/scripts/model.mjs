// Build-time only. Runtime explicitly disables all model network access.
import { mkdir, writeFile, readFile } from 'node:fs/promises';
import { createHash } from 'node:crypto';
import { fileURLToPath } from 'node:url';
const root = fileURLToPath(new URL('../models/Xenova/all-MiniLM-L6-v2/',import.meta.url));
const manifest = JSON.parse(await readFile(new URL('./model-lock.json',import.meta.url),'utf8'));
for (const [file,hash] of Object.entries(manifest.files)) {
  const response = await fetch(`https://huggingface.co/Xenova/all-MiniLM-L6-v2/resolve/${manifest.revision}/${file}`);
  if (!response.ok) throw new Error(`Model download failed: ${response.status}`);
  const data = Buffer.from(await response.arrayBuffer());
  if (createHash('sha256').update(data).digest('hex') !== Buffer.from(hash).toString('hex')) throw new Error(`Model checksum failed: ${file}`);
  await mkdir(new URL('.',`file://${root}${file}`).pathname,{recursive:true});
  await writeFile(`${root}${file}`,data);
}
console.log('Pinned local model assets verified.');
