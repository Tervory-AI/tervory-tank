import assert from 'node:assert/strict';
import { promises as fs } from 'node:fs';
import path from 'node:path';
import os from 'node:os';
import { performance } from 'node:perf_hooks';
import { ProjectIndex } from '../src/index';
import { LocalEmbedder } from '../src/embedding';
export const budgets={indexMs:600000,searchMs:35000,warmRefreshMs:30000};
async function main() {
  const base=await fs.mkdtemp(path.join(os.tmpdir(),'tervory-index-10000-'));
  const root=path.join(base,'project'),storage=path.join(base,'storage');await fs.mkdir(root);
  const cases=[
    {file:'account-recovery.ts',code:'// Restore account access for someone who forgot their password.\nexport function resetPassword(email: string) { return sendRecoveryEmail(email); }',query:'help a user regain access to their account'},
    {file:'retry-request.ts',code:'// Retry failed network requests with exponential backoff and bounded attempts.\nexport function retryRequest(attempt: number) { return Math.min(30000, 100 * 2 ** attempt); }',query:'wait longer between attempts when a network operation fails'},
    {file:'write-document.ts',code:'// Persist an edited document safely by writing a temporary file and renaming it.\nexport function saveDocument(file: string, content: string) { writeTemp(file, content); renameTemp(file); }',query:'save changes to a file without corrupting the previous version'}
  ];
  for(let start=0;start<9997;start+=100) await Promise.all(Array.from({length:Math.min(100,9997-start)},(_,j)=>{
    const n=start+j;
    return fs.writeFile(path.join(root,`item-${String(n).padStart(5,'0')}.ts`),`// Apply an arithmetic offset to a numeric value.\nexport function transformItem${n}(value: number) { return value + ${n}; }\n`);
  }));
  for(const c of cases)await fs.writeFile(path.join(root,c.file),c.code);
  const modelWorker=new LocalEmbedder(path.resolve(__dirname,'../../models'));
  let embeddedChunks=0;
  const index=new ProjectIndex(root,storage,{
    embed:async(texts:string[])=>{embeddedChunks+=texts.length;return modelWorker.embed(texts);},
    dispose:()=>modelWorker.dispose()
  });
  try {
    let start=performance.now();await index.refresh();const indexMs=performance.now()-start;
    assert.equal(index.fileCount,10000);
    const indexedChunks=embeddedChunks;assert.ok(indexedChunks>=10000);
    const searches=[];
    for(const c of cases){
      start=performance.now();await index.refresh();const results=await index.search(c.query,'meaning',5);const searchMs=performance.now()-start;
      assert.ok(results.some(r=>r.path===c.file),`${c.file} missing: ${results.map(r=>r.path)}`);
      assert.ok(searchMs<budgets.searchMs,`search budget exceeded: ${searchMs}`);
      searches.push({query:c.query,expected:c.file,returned:results.map(r=>r.path),searchMs});
    }
    start=performance.now();await index.refresh();const exact=await index.search('2 ** attempt','exact');const exactMs=performance.now()-start;
    assert.equal(exact[0].path,'retry-request.ts');assert.ok(exactMs<budgets.searchMs);
    const before=embeddedChunks;start=performance.now();await index.refresh();assert.equal(embeddedChunks,before);const warmRefreshMs=performance.now()-start;
    const model=JSON.parse(await fs.readFile(path.resolve(__dirname,'../../scripts/model-lock.json'),'utf8'));
    const record={head:process.env.GITHUB_SHA??'local',modelRevision:model.revision,os:process.platform,arch:process.arch,node:process.version,cpu:os.cpus()[0]?.model,files:10000,indexedChunks,indexMs,warmRefreshMs,exactMs,budgets,searches};
    await fs.writeFile(path.resolve('benchmark-results.json'),JSON.stringify(record,null,2)+'\n');console.log(JSON.stringify(record,null,2));
    assert.ok(indexMs<budgets.indexMs,`index budget exceeded: ${indexMs}`);assert.ok(warmRefreshMs<budgets.warmRefreshMs);
  } finally {await index.dispose();await fs.rm(base,{recursive:true,force:true});}
}
void main().catch(error=>{console.error(error);process.exitCode=1;});
