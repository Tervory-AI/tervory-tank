/* Execute generated-site handlers and visual measurements; no remote origin. */
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const { createRequire } = require('node:module');
const root = path.resolve(__dirname, '../..');
const template = path.join(root, 'agents/tisan/templates/next-site');
const ts = require(path.join(root, 'workspace/node_modules/typescript'));
function load(relative) {
 const file = path.join(template, relative);
 const code = ts.transpileModule(fs.readFileSync(file,'utf8'), {compilerOptions:{module:ts.ModuleKind.CommonJS,esModuleInterop:true,target:ts.ScriptTarget.ES2020}}).outputText;
 const out = {};
 new Function('require','exports',code)(createRequire(file),out);
 return out;
}
(async()=>{
 const row=process.argv[2];
 if(row==='T44') {
  const api=load('app/api/contact/route.ts');
  const response=await api.POST(new Request('http://127.0.0.1/api/contact',{method:'POST',body:JSON.stringify({name:'placeholder',message:'placeholder message'})}));
  assert.equal(response.status,202);assert.deepEqual(await response.json(),{ok:true});
 } else {
  const {chromium}=require(process.env.TISAN_TEST_PLAYWRIGHT || path.join(template,'node_modules/playwright'));
  const browser=await chromium.launch({headless:true,args:['--no-sandbox']});
  try {
   const page=await browser.newPage({viewport:{width:375,height:900}});
   const requests=[];await page.route('**/*',r=>{requests.push(r.request().url());return r.abort();});
   await page.setContent('<style>:root{--ink:#001840}#placeholder{position:absolute;left:16px;top:32px;width:200px;height:40px;color:var(--ink)}</style><div id="placeholder">placeholder approved text</div>');
   const frame={page:'/',frameId:'placeholder-frame',width:375,height:900,tokens:{'--ink':'#001840'},elements:[{nodeId:'placeholder-node',selector:'#placeholder',text:'placeholder approved text',box:{x:16,y:32,width:200,height:40},colours:{color:'--ink'}}]};
   const {scoreFrame}=load('visual/check.ts');
   const good=await scoreFrame(page,frame);assert.equal(good.score,1);assert.equal(good.passed,true);
   await page.locator('#placeholder').evaluate(node=>{node.textContent='placeholder changed';node.style.color='#e80008';node.style.left='50px';});
   const bad=await scoreFrame(page,frame);assert.equal(bad.passed,false);assert(bad.score<1);
   assert.deepEqual(requests,[]);
  } finally {await browser.close();}
 }
 console.log(row+' passed');
})().catch(e=>{console.error(e);process.exitCode=1;});
