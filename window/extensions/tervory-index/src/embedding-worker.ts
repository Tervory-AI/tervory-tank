import { parentPort, workerData } from 'node:worker_threads';
// Model and tokenizer are packaged assets. No fallback to a Hub or inference API.
const ready = (async () => {
  const {env,pipeline} = await import('@huggingface/transformers');
  globalThis.fetch = async () => { throw new Error('Network disabled in local embedding worker'); };
  env.allowRemoteModels = false;
  env.allowLocalModels = true;
  env.localModelPath = workerData.modelRoot;
  env.useBrowserCache = false;
  return pipeline('feature-extraction','Xenova/all-MiniLM-L6-v2',{dtype:'q8',local_files_only:true,device:'cpu',session_options:{intraOpNumThreads:2,interOpNumThreads:1}});
})();
let queue = Promise.resolve();
parentPort!.on('message', (m: {id:number;texts:string[]}) => {
  queue = queue.then(async () => {
    try {
      const model = await ready;
      const output = await model(m.texts,{pooling:'mean',normalize:true});
      parentPort!.postMessage({id:m.id,vectors:output.tolist()});
    } catch (error) { parentPort!.postMessage({id:m.id,error:String(error)}); }
  });
});
// Attach a rejection handler before the first request arrives.
void ready.catch(() => {});
