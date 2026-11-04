// Render the production components without credentials or production data.
const fs=require('node:fs'),path=require('node:path'),http=require('node:http');
const {createRequire}=require('node:module');
const root=path.resolve(__dirname,'../../..');
const deps=createRequire('/home/ammosync/.codex/dashboards-w4/workspace/package.json');
const React=deps('react'),{renderToStaticMarkup}=deps('react-dom/server'),ts=deps('typescript');
const out=path.join(root,'.tmp/live-pages');fs.mkdirSync(out,{recursive:true});
let route='/data',currentKey='data';const cache=new Map(),styles=new Set();
const identity={tenantId:'placeholder-tenant',userId:'placeholder-client',orgName:'Example'};
const tenant={currentTenant:async()=>identity,activeTenant:async()=>identity};
function load(file){file=path.resolve(file);if(cache.has(file))return cache.get(file).exports;
 const mod={exports:{}};cache.set(file,mod);
 const code=ts.transpileModule(fs.readFileSync(file,'utf8'),{compilerOptions:{jsx:ts.JsxEmit.ReactJSX,module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2022,esModuleInterop:true}}).outputText;
 function req(name){
  if(name==='react' && file.endsWith('/onboarding/wizard.tsx') && currentKey==='onboarding-run'){let index=0;return {...React,useState:(initial)=>React.useState(index++===9?'Example':initial)};}
  if(name==='@/lib/autumbra-undo-token')return{verifyUndoToken(){throw Error('No credential used');}};
  if(name==='@/lib/autumbra-undo-status')return{loadUndoStatus:async()=>({already_undone:false})};
  if(name==='@/lib/autumbra-receipts-access')return{mayReadWeeklyReceipts:async()=>true};
  if(name==='@/lib/autumbra-weekly')return{loadWeeklyReceipts:async()=>({receipts:[],note:'',timeZone:'America/Los_Angeles'})};
  if(name.endsWith('.css')){styles.add(path.resolve(path.dirname(file),name));return{};}
  if(name==='server-only')return{};
  if(name==='next/link')return{__esModule:true,default:({children,...p})=>React.createElement('a',p,children)};
  if(name==='next/navigation')return{usePathname:()=>route,useSearchParams:()=>new URLSearchParams(),useSelectedLayoutSegments:()=>route.split('/').filter(Boolean),useRouter:()=>({refresh(){},push(){}}),notFound(){throw Error('404');},redirect(){throw Error('Redirect requires identity');}};
  if(name==='@clerk/nextjs')return{useAuth:()=>({isLoaded:true,isSignedIn:false,userId:null}),OrganizationSwitcher:()=>null,UserButton:()=>null,useOrganization:()=>({isLoaded:true,organization:null}),OrganizationList:()=>null};
  if(name==='next/font/local')return{__esModule:true,default:({variable})=>({variable:variable.replaceAll('-','_')})};
  if(name==='@/lib/tenant')return tenant;
  if(name==='@/lib/admin')return{isFounder:()=>false};
  if(name==='@/lib/tank')return{commandRequest:async()=>Response.json({thread:{thread_id:'placeholder-thread',title:'',spent_usd:0,saved_usd:0},messages:[{message_id:'placeholder-answer',role:'assistant',content:'',receipt:{rows:[{step_id:'placeholder-step',ledger_id:'placeholder-row',cost_usd:0,baseline_cost_usd:0,saved_usd:0}],totals:{cost_usd:0,baseline_cost_usd:0,saved_usd:0}}}],steps:[],cards:[]}),mootPublishedMatches:async()=>({matches:currentKey==='moot-watch'?[{matchId:'b88613ae-7f0a-49e7-bdb5-28620f283041',published:true,title:'Civil appeal',fairnessReading:'',judgmentOrder:'Independent order',reveal:'Stored court holding',costUsd:null}]:[]}),marketLabRequest:async()=>({name:'Harbor throughput and notices',kind:'feed',fetched_at:'2026-10-31T18:00:00Z',offset:0,page_size:50,point_count:3,event_count:1,downloads:[],points:[0,1,2].map(index=>({index,display_title:'Harbor throughput',geo_name:'US',date_label:`${index+1} Jan 1960`,display_value:(14474+index).toLocaleString('en-US'),unit_label:'TEU'})),events:[{index:0,display_title:'Harbor notice',date_label:'1 Jan 1960',kind:'notice',body:'Saved harbor notice',display_url:'https://publisher.test/notice',link_label:'publisher.test'}]}),ledgerSummary:async()=>({days:30,calls:0,delivered:0,accepted:0,rejected:0,acceptance_rate:null,cost_usd:0,unpriced:0,cost_per_delivered_usd:null,cost_per_accepted_usd:null,by_model:[]})};
  if(name==='@/app/api/zenas/tank')return{homeRegion:()=> 'za',zenas:async()=>({ok:true,json:async()=>[]})};
  if(name.startsWith('.')||name.startsWith('@/')){let target=name.startsWith('@/')?path.join(root,'workspace',name.slice(2)):path.resolve(path.dirname(file),name);const found=[target,target+'.ts',target+'.tsx',path.join(target,'index.ts'),path.join(target,'index.tsx')].find(f=>fs.existsSync(f)&&fs.statSync(f).isFile());if(found)return load(found);}
  return deps(name);
 }
 new Function('require','module','exports',code)(req,mod,mod.exports);return mod.exports;
}
const fontCss=`@font-face{font-family:Inter;src:url(/fonts/Inter-latin.woff2);font-weight:100 900}@font-face{font-family:Jost;src:url(/fonts/Jost-300-latin.woff2);font-weight:300}@font-face{font-family:'JetBrains Mono';src:url(/fonts/JetBrainsMono-latin.woff2);font-weight:400 500}:root{--font-inter:Inter;--font-jost:Jost;--font-mono:'JetBrains Mono';--onb-body:Inter;--onb-heading:Jost;--onb-mono:'JetBrains Mono'}`;
const cases={data:['/data','data/page.tsx'],ledger:['/ledger','ledger/page.tsx'],matters:['/matters','matters/page.tsx'],autumbra:['/autumbra','autumbra/page.tsx']};
Object.assign(cases,{
 'chat-costs':['/chats/evidence/placeholder-thread','chats/evidence/[thread]/page.tsx'],
 'cost-details':['/chats/evidence/placeholder-thread/placeholder-row','chats/evidence/[thread]/[row]/page.tsx'],
 onboarding:['/onboarding','onboarding/page.tsx'],
 'onboarding-industry':['/onboarding','onboarding/page.tsx'],
 'onboarding-file':['/onboarding','onboarding/page.tsx'],
 'onboarding-run':['/onboarding','onboarding/page.tsx'],
 sources:['/market-lab/sources/b88613ae-7f0a-49e7-bdb5-28620f283041','market-lab/sources/[id]/page.tsx'],
 moot:['/moot','moot/page.tsx'],
 'moot-watch':['/moot/b88613ae-7f0a-49e7-bdb5-28620f283041','moot/[match]/page.tsx'],
 undo:['/autumbra/undo/placeholder-receipt','autumbra/undo/[id]/page.tsx'],
 weekly:['/autumbra/receipts/weekly/placeholder-tenant','autumbra/receipts/weekly/[tenant]/page.tsx']
});
async function render(key){currentKey=key;const config=cases[key];if(!config)throw Error('Unknown page');route=config[0];cache.clear();styles.clear();styles.add(path.join(root,'workspace/app/globals.css'));
 const entry=path.join(root,'workspace/app',config[1]),Page=load(entry).default;
 let page=/^[\s]*[\"']use client[\"']/.test(fs.readFileSync(entry,'utf8'))?React.createElement(Page):await Page({params:Promise.resolve({thread:'placeholder-thread',row:'placeholder-row',id:'b88613ae-7f0a-49e7-bdb5-28620f283041',match:'b88613ae-7f0a-49e7-bdb5-28620f283041',tenant:'placeholder-tenant'}),searchParams:Promise.resolve({})});
 if(key==='sources'){const {StoredSourcePage}=load(path.join(root,'workspace/app/market-lab/source-page.tsx'));page=await StoredSourcePage({tenantId:identity.tenantId,id:'b88613ae-7f0a-49e7-bdb5-28620f283041'});}
 if(key.startsWith('onboarding')){if(key!=='onboarding'){const {Wizard}=load(path.join(root,'workspace/app/onboarding/wizard.tsx'));page=React.createElement(Wizard,{orgName:'Example',orgSlot:null,engines:['ffl'],enginesError:null,onRetryEngines(){},onStart:async()=>({batch:'Example'}),progress:{summary:{total:1,done:0,failed:0,pending:1},records:[]},initialStep:key.slice(11)});}page=React.createElement(load(path.join(root,'workspace/app/onboarding/layout.tsx')).default,null,page);}
 if(key==='matters')page=React.createElement(load(path.join(root,'workspace/app/matters/layout.tsx')).default,null,page);
 const {Shell}=load(path.join(root,'workspace/app/shell.tsx'));
 const markup=renderToStaticMarkup(React.createElement(Shell,{founder:false,reviewer:false,readAccess:async()=>({founder:false,reviewer:false})},page));
 const css=fontCss+'\n'+[...styles].map(f=>fs.readFileSync(f,'utf8')).join('\n');
 return `<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>${key==='data'?'Data':key==='ledger'?'Ledger':key==='matters'?'Matters':'Autumbra'}</title><style>${css}</style><script src="https://mcp.figma.com/mcp/html-to-design/capture.js" async></script></head><body>${markup}</body></html>`;
}
const server=http.createServer(async(req,res)=>{try{const u=new URL(req.url,'http://localhost');if(u.pathname.startsWith('/brand/')||u.pathname.startsWith('/fonts/')){const base=u.pathname.startsWith('/brand/')?path.join(root,'workspace/public/brand'):path.join(root,'workspace/app/fonts');const f=path.join(base,path.basename(u.pathname));res.setHeader('Content-Type',f.endsWith('woff2')?'font/woff2':'image/png');res.end(fs.readFileSync(f));return;}
 const key=u.pathname.slice(1)||'data';let html=await render(key);if(u.searchParams.has('reference'))html=html.replace(/<script src="https:\/\/mcp\.figma\.com[^>]*><\/script>/g,'');fs.writeFileSync(path.join(out,key+'.html'),html);res.setHeader('Content-Type','text/html');res.end(html);
}catch(e){res.statusCode=500;res.end(String(e.stack));}});
server.listen(0,'127.0.0.1',()=>{fs.writeFileSync(path.join(out,'server.json'),JSON.stringify({port:server.address().port}));console.log('Local production-component renderer ready on '+server.address().port);});
