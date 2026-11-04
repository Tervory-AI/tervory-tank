import { Worker } from 'node:worker_threads';
import path from 'node:path';
export interface Embedder { embed(texts: string[]): Promise<number[][]>; dispose(): Promise<void> }
export class LocalEmbedder implements Embedder {
  private worker: Worker;
  private next = 0;
  private pending = new Map<number,{resolve:(v:number[][])=>void; reject:(e:Error)=>void}>();
  constructor(modelRoot: string) {
    this.worker = new Worker(path.join(__dirname,'embedding-worker.js'),{workerData:{modelRoot}});
    this.worker.on('message', (m: {id:number; vectors:number[][]; error?:string}) => {
      const p = this.pending.get(m.id); this.pending.delete(m.id);
      if (m.error) p?.reject(new Error(m.error)); else p?.resolve(m.vectors);
    });
    this.worker.on('error', e => { for (const p of this.pending.values()) p.reject(e); this.pending.clear(); });
    this.worker.on('exit', () => { for (const p of this.pending.values()) p.reject(new Error('Embedding worker stopped')); this.pending.clear(); });
  }
  embed(texts:string[]):Promise<number[][]> {
    return new Promise((resolve,reject) => { const id = this.next++; this.pending.set(id,{resolve,reject}); this.worker.postMessage({id,texts}); });
  }
  async dispose():Promise<void> { await this.worker.terminate(); }
}
