// Run the actual Next route with a verified-identity fixture and a stub Tank.
import assert from 'node:assert/strict';
import path from 'node:path';
import {createRequire} from 'node:module';
import {fileURLToPath} from 'node:url';
const root=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'..');
const require=createRequire(path.join(root,'workspace/package.json'));
const {build}=require(process.env.TRAIN1_ESBUILD_PATH || 'esbuild');
const bundled=await build({entryPoints:[path.join(root,'workspace/app/api/skala/gold/route.ts')],bundle:true,write:false,platform:'node',format:'cjs',packages:'external',plugins:[{
  name:'verified-fixtures', setup(build) {
    build.onResolve({filter:/^@\//},args=>({path:args.path,namespace:'fixture'}));
    build.onLoad({filter:/.*/,namespace:'fixture'},args=>({contents:args.path.endsWith('/access') ?
      `export async function goldIdentity(scope) { return {userId:'verified',tenantId:scope==='platform'?'platform':'verified-tenant',role:'founder'} }` :
      `export async function checkGold(identity,id,body) { globalThis.trainCalls.push({identity,id,body});return {ok:true} }; export const confirmTrainingRead=checkGold,finalGoldCheck=checkGold,goldNext=checkGold,goldSummary=checkGold;`,loader:'js'}));
  }
}]});
const module={exports:{}};
new Function('require','module','exports',bundled.outputFiles[0].text)(require,module,module.exports);
const {POST}=module.exports;
globalThis.trainCalls=[];
const request=(origin,body={id:'00000000-0000-0000-0000-000000000011',action:'right',tenantId:'untrusted',userId:'untrusted'})=>new Request('http://internal:3000/api/skala/gold?scope=tenant',{method:'POST',headers:{host:'app.example.invalid',origin,'content-type':'application/json'},body:JSON.stringify(body)});
assert.equal((await POST(request('https://app.example.invalid'))).status,200);
assert.equal(globalThis.trainCalls[0].identity.tenantId,'verified-tenant');
assert.equal(globalThis.trainCalls[0].identity.userId,'verified');
assert.equal((await POST(request('https://other.example.invalid'))).status,403);
assert.equal((await POST(request('null'))).status,403);
assert.equal((await POST(request('https://app.example.invalid',{id:'invalid',action:'right'}))).status,400);
assert.equal(globalThis.trainCalls.length,1);
console.log('TRAIN-1 API checks passed: trusted identity, tenant scope, proxy origin, forged origin, malformed input.');
