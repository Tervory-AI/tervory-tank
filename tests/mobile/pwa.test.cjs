const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const vm=require('node:vm');
const path=require('node:path');
const root=path.resolve(__dirname,'../..');
function worker(options={}) {
 const hooks={},stored=new Map(),fetched=[],deleted=[];
 const cache={addAll:async urls=>{for(const u of urls) stored.set(u,'public');},match:async r=>stored.get(r.url),put:async(r,v)=>stored.set(r.url,v)};
 const box={URL,self:{location:{origin:'https://app.tervory.com'},clients:{claim:async()=>{}},addEventListener:(n,f)=>hooks[n]=f},
 caches:{open:async()=>cache,keys:async()=>options.keys||[],delete:async key=>{deleted.push(key);return true;}},fetch:async r=>{fetched.push(r.url);return {ok:options.ok!==false,type:options.type||'basic',redirected:!!options.redirected,headers:{get:()=>options.private?'private, no-store':null},clone:()=>({public:true})};}};
 vm.runInNewContext(fs.readFileSync(path.join(root,'workspace/public/sw.js'),'utf8'),box);
 return {hooks,stored,fetched,deleted};
}
test('manifest installs the existing app and exact logo pixels on navy',()=>{
 const m=JSON.parse(fs.readFileSync(path.join(root,'workspace/public/manifest.webmanifest')));
 assert.equal(m.start_url,'/chats');assert.equal(m.display,'standalone');assert.equal(m.scope,'/');
 for(const icon of m.icons){const bytes=fs.readFileSync(path.join(root,'workspace/public',icon.src));const size=Number(icon.sizes.split('x')[0]);assert.equal(bytes.readUInt32BE(16),size);assert.equal(bytes.readUInt32BE(20),size);assert.equal(icon.purpose,'any maskable');}
 assert(fs.readFileSync(path.join(root,'workspace/app/layout.tsx'),'utf8').includes('appleWebApp: { capable: true'));
});
test('navigation, data, credentials, cross-origin and arbitrary assets never enter cache',()=>{
 const {hooks,stored,fetched}=worker();
 for(const [url,method,mode] of [
  ['/chats','GET','navigate'],['/api/command/threads','GET','cors'],['/sign-in','GET','navigate'],['/oauth/token','POST','cors'],
  ['/_next/static/client.json','GET','cors'],['/_next/static/app.js?tenant=placeholder','GET','cors'],['https://placeholder.invalid/_next/static/a.js','GET','cors'],['/files/placeholder.pdf','GET','cors']]){
  hooks.fetch({request:{url:new URL(url,'https://app.tervory.com').href,method,mode},respondWith:()=>assert.fail('private fetch intercepted')});
 }
 assert.equal(stored.size,0);assert.equal(fetched.length,0);
});
test('public assets cache, private response headers still refuse caching',async()=>{
 for(const privateValue of [false,true]){
  const {hooks,stored,fetched}=worker({private:privateValue});let result;
  const request={url:'https://app.tervory.com/_next/static/chunks/placeholder.js',method:'GET',mode:'cors'};
  hooks.fetch({request,respondWith:v=>result=v});await result;
  assert.equal(fetched.length,1);assert.equal(stored.size,privateValue?0:1);
 }
});
test('install precaches only manifest and public icons',async()=>{
 const {hooks,stored}=worker();let result;hooks.install({waitUntil:v=>result=v});await result;
 assert.equal(stored.size,4);assert([...stored.keys()].every(p=>p.startsWith('/icons/')||p==='/manifest.webmanifest'));
});
test('redirected, opaque and failed responses never enter cache',async()=>{
 for(const options of [{redirected:true},{type:'opaque'},{ok:false}]){
  const {hooks,stored}=worker(options);let result;
  hooks.fetch({request:{url:'https://app.tervory.com/_next/static/chunks/placeholder.js',method:'GET',mode:'cors'},respondWith:v=>result=v});
  await result;assert.equal(stored.size,0);
 }
});
test('activation removes previous shell versions and preserves unrelated caches',async()=>{
 const {hooks,deleted}=worker({keys:['tervory-shell-v0','tervory-shell-v1','unrelated']});let result;
 hooks.activate({waitUntil:v=>result=v});await result;
 assert.deepEqual(deleted,['tervory-shell-v0']);
});
