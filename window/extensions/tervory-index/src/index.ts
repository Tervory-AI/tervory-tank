import { create, insertMultiple, removeMultiple, search, save, load } from '@orama/orama';
import { promises as fs } from 'node:fs';
import path from 'node:path';
import { createHash, randomUUID } from 'node:crypto';
import { chunks, type Chunk, type Span } from './chunks';
import { sources } from './files';
import type { Embedder } from './embedding';
const schema = {id:'string',path:'string',startLine:'number',endLine:'number',text:'string',vector:'vector[384]'} as const;
// Bump when model identity, chunk boundaries or persisted schema changes.
const cacheVersion=2;
const fresh = () => create({schema});
export type Hit = Chunk & {score:number};
export class ProjectIndex {
  private db = fresh();
  private files = new Map<string,{hash:string;ids:string[]}>();
  private tail: Promise<unknown> = Promise.resolve();
  private closed = false;
  constructor(readonly root:string, private storage:string, private embedder:Embedder, private structure?:(file:string)=>Promise<Span[]>) {}
  async restore():Promise<void> {
    try {
      const state = JSON.parse(await fs.readFile(path.join(this.storage,'index.json'),'utf8'));
      if (state.version !== cacheVersion || state.root !== this.root) return;
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
    let pending:{path:string;hash:string;parts:Chunk[]}[]=[];
    let pendingSize=0;
    const flush=async()=>{
      const parts=pending.flatMap(f=>f.parts);
      const vectors:number[][]=[];
      for(let i=0;i<parts.length;i+=32) vectors.push(...await this.embedder.embed(parts.slice(i,i+32).map(c=>`${c.path}\n${c.text}`)));
      let offset=0;
      for(const file of pending) {
        const records=file.parts.map(c=>({...c,id:`${c.path}:${c.startLine}`,vector:vectors[offset++]}));
        const old=this.files.get(file.path);
        if(old) await removeMultiple(this.db,old.ids);
        if(records.length) await insertMultiple(this.db,records);
        this.files.set(file.path,{hash:file.hash,ids:records.map(r=>r.id)});
      }
      pending=[];pendingSize=0;
    };
    for await (const file of sources(this.root)) {
      if (this.closed) return;
      seen.add(file.path);
      const hash = createHash('sha256').update(file.text).digest('hex');
      if (this.files.get(file.path)?.hash === hash) continue;
      const parts=chunks(file.path,file.text,await this.structure?.(file.path));
      pending.push({path:file.path,hash,parts});pendingSize+=parts.length;
      if(pendingSize>=32 || pending.length>=32) await flush();
    }
    if(pending.length) await flush();
    for (const [file,record] of this.files) if (!seen.has(file)) {
      await removeMultiple(this.db,record.ids); this.files.delete(file);
    }
    await fs.mkdir(this.storage,{recursive:true,mode:0o700});
    const temp = path.join(this.storage,`index.${randomUUID()}.next`);
    try {
      await fs.writeFile(temp,JSON.stringify({version:cacheVersion,root:this.root,files:[...this.files],db:save(this.db)}),{mode:0o600});
      await fs.rename(temp,path.join(this.storage,'index.json'));
    } finally {await fs.rm(temp,{force:true});}
  }
  async search(query:string, mode:'meaning'|'exact'='meaning',limit=10):Promise<Hit[]> {
    await this.tail;
    if (!query.trim() || query.length > 4000) return [];
    limit = Math.max(1,Math.min(50,Math.floor(limit)||10));
    if (mode === 'exact') {
      const matches:Hit[]=[];
      for await (const file of sources(this.root)) {
        const at=file.text.indexOf(query);
        if (at<0) continue;
        const startLine=file.text.slice(0,at).split('\n').length;
        const endLine=startLine+query.split('\n').length-1;
        const text=file.text.split('\n').slice(startLine-1,Math.min(endLine+2,startLine+40)).join('\n');
        matches.push({path:file.path,startLine,endLine,text,score:1});
        if (matches.length>=limit) break;
      }
      return matches;
    }
    const [vector] = await this.embedder.embed([query]);
    const results = await search(this.db,{mode:'vector',vector:{value:vector,property:'vector'},similarity:0,limit});
    return results.hits.map(({document:d,score})=>({path:d.path,startLine:d.startLine,endLine:d.endLine,text:d.text,score}));
  }
  get fileCount():number { return this.files.size; }
  async dispose():Promise<void> { this.closed=true; await this.tail; await this.embedder.dispose(); }
}
