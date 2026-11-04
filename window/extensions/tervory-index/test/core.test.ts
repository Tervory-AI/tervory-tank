import { test } from 'node:test';
import assert from 'node:assert/strict';
import { promises as fs } from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { chunks } from '../src/chunks';
import { ProjectIndex } from '../src/index';
import { sources } from '../src/files';
const embedder = {embed:async (texts:string[])=>texts.map(()=>Array.from({length:384},(_,i)=>i===0?1:0)),dispose:async()=>{}};
test('symbols and bounded long functions preserve line references',()=>{
  const text = 'export function first() {\n  return 1;\n}\nexport function second() {\n  return 2;\n}';
  const result = chunks('code.ts',text);
  assert.equal(result[0].startLine,1); assert.equal(result[1].startLine,4);
  assert.equal(result.map(c=>c.text).join('\n'),text);
  assert.ok(chunks('large.py','def large():\n'+'  pass\n'.repeat(300)).every(c=>c.endLine-c.startLine<40));
});
test('nested ignore rules, secrets, binary and symlinks never enter storage; changes and deletions refresh',async()=>{
  const base = await fs.mkdtemp(path.join(os.tmpdir(),'tervory-index-'));
  const root = path.join(base,'project'), store=path.join(base,'store');
  await fs.mkdir(path.join(root,'sub'),{recursive:true});
  try {
    await fs.writeFile(path.join(root,'.gitignore'),'ignored.ts\n');
    await fs.writeFile(path.join(root,'sub','.gitignore'),'hidden.ts\n');
    for (const name of ['ignored.ts','.env','private.key','sub/hidden.ts']) await fs.writeFile(path.join(root,name),'do not index');
    await fs.writeFile(path.join(root,'binary.ts'),Buffer.from([65,0,66]));
    await fs.writeFile(path.join(root,'leaked.ts'),'const password = "'+'example'.repeat(3)+'"');
    await fs.writeFile(path.join(root,'safe.ts'),'export const first = 1;');
    const files=[]; for await (const f of sources(root)) files.push(f.path);
    assert.deepEqual(files,['safe.ts']);
    const index = new ProjectIndex(root,store,embedder);
    await index.refresh(); assert.equal(index.fileCount,1);
    await fs.writeFile(path.join(root,'safe.ts'),'export const changed = 2;');
    await index.refresh(); assert.equal((await index.search('changed','exact'))[0].text,'export const changed = 2;');
    assert.equal((await index.search('first','exact')).length,0);
    const restored = new ProjectIndex(root,store,embedder); await restored.restore(); assert.equal(restored.fileCount,1);
    await fs.writeFile(path.join(root,'.gitignore'),'safe.ts\nignored.ts\n');
    await index.refresh(); assert.equal(index.fileCount,0);
    await fs.unlink(path.join(root,'safe.ts')); await restored.refresh(); assert.equal(restored.fileCount,0);
    await index.dispose(); await restored.dispose();
  } finally { await fs.rm(base,{recursive:true,force:true}); }
});
test('real packaged MiniLM model embeds with network disabled in worker',async()=>{
  const {LocalEmbedder}=await import('../src/embedding.js');
  const model=new LocalEmbedder(path.resolve(__dirname,'../../models'));
  try {
    const [a,b,c]=await model.embed(['reset forgotten password','recover account credentials','paint a mountain landscape']);
    assert.equal(a.length,384);
    const dot=(v:number[],w:number[])=>v.reduce((s,x,i)=>s+x*w[i],0);
    assert.ok(dot(a,b)>dot(a,c));
  } finally {await model.dispose();}
});
