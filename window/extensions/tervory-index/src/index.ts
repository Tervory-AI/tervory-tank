import { create, insertMultiple, removeMultiple, search, save, load } from '@orama/orama';
import { promises as fs } from 'node:fs';
import path from 'node:path';
import { createHash } from 'node:crypto';
import { chunks, type Chunk } from './chunks';
import { sources } from './files';
import type { Embedder } from './embedding';
const schema = {id:'string',path:'string',startLine:'number',endLine:'number',text:'string',vector:'vector[384]'} as const;
const fresh = () => create({schema});
export type Hit = Chunk & {score:number};
export class ProjectIndex {
  private db = fresh();
  private files = new Map<string,{hash:string;ids:string[]}>();
  private tail: Promise<unknown> = Promise.resolve();
  private closed = false;
  constructor(readonly root:string, private storage:string, private embedder:Embedder) {}
  async restore():Promise<void> {
    try {
      const state = JSON.parse(await fs.readFile(path.join(this.storage,'index.json'),'utf8'));
      if (state.version !== 1 || state.root !== this.root) return;
      load(this.db,state.db); this.files = new Map(state.files);
    } catch { /* missing/incompatible cache: rebuild */ }
  }
  refresh():Promise<void> {
    const next = this.tail.then(() => this.sync());
    this.tail = next.catch(() => {}); return next;
  }
  private async sync():Promise<void> {
    if (this.closed) return;
    const seen = new Set<string>();
    for await (const file of sources(this.root)) {
      if (this.closed) return;
      seen.add(file.path);
      const hash = createHash('sha256').update(file.text).digest('hex');
      if (this.files.get(file.path)?.hash === hash) continue;
      const parts = chunks(file.path,file.text);
      const records = [];
      for (let i=0;i<parts.length;i+=32) {
        const batch = parts.slice(i,i+32);
        const vectors = await this.embedder.embed(batch.map(c=>`${c.path}\n${c.text}`));
        records.push(...batch.map((c,j)=>({...c,id:`${file.path}:${c.startLine}`,vector:vectors[j]})));
      }
      const old = this.files.get(file.path);
      if (old) await removeMultiple(this.db,old.ids);
      if (records.length) await insertMultiple(this.db,records);
      this.files.set(file.path,{hash,ids:records.map(r=>r.id)});
    }
    for (const [file,record] of this.files) if (!seen.has(file)) {
      await removeMultiple(this.db,record.ids); this.files.delete(file);
    }
    await fs.mkdir(this.storage,{recursive:true,mode:0o700});
    const temp = path.join(this.storage,'index.next');
    await fs.writeFile(temp,JSON.stringify({version:1,root:this.root,files:[...this.files],db:save(this.db)}),{mode:0o600});
    await fs.rename(temp,path.join(this.storage,'index.json'));
  }
  async search(query:string, mode:'meaning'|'exact'='meaning',limit=10):Promise<Hit[]> {
    await this.tail;
    if (!query.trim() || query.length > 4000) return [];
    limit = Math.max(1,Math.min(50,Math.floor(limit)||10));
    if (mode === 'exact') {
      // Literal substring search, including punctuation and case, without tokenization.
      const all = await search(this.db,{term:'',limit:Math.max(1,[...this.files.values()].reduce((n,f)=>n+f.ids.length,0))});
      return all.hits.filter(h=>h.document.text.includes(query)).slice(0,limit).map(h=>({...h.document,score:1}));
    }
    const [vector] = await this.embedder.embed([query]);
    const results = await search(this.db,{mode:'vector',vector:{value:vector,property:'vector'},similarity:0,limit});
    return results.hits.map(h=>({...h.document,score:h.score}));
  }
  get fileCount():number { return this.files.size; }
  async dispose():Promise<void> { this.closed=true; await this.tail; await this.embedder.dispose(); }
}
