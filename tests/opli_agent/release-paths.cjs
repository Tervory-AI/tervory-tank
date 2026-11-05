const assert=require('node:assert/strict');
const fs=require('node:fs');const path=require('node:path');
const {workspace}=require('../command_acceptance_20261031/workspace_loader.cjs');
let input='';process.stdin.setEncoding('utf8');process.stdin.on('data',chunk=>{input+=chunk;});
process.stdin.on('end',async()=>{
  const files=JSON.parse(input);const root=path.resolve(__dirname,'../..');
  const read=fs.readFileSync,exists=fs.existsSync,stat=fs.statSync;
  const lookup=file=>files[path.relative(root,String(file)).replaceAll('\\','/')];
  fs.readFileSync=(file,...args)=>lookup(file)??read(file,...args);
  fs.existsSync=file=>lookup(file)!==undefined||exists(file);
  fs.statSync=file=>lookup(file)!==undefined?{isFile:()=>true}:stat(file);
  let middleware,hosts,config;
  try {
    const load=workspace({env:{},fetch:()=>assert.fail('No network'),mocks:{'next-auth/jwt':{getToken:()=>assert.fail('Release assets are public')},'next/server':{NextResponse:{rewrite:url=>({rewrite:url.pathname}),redirect:()=>assert.fail('No sign-in redirect'),next:()=>({next:true})}}}});
    hosts=load('lib/product-hosts.ts');({default:middleware,config}=load('middleware.ts'));
  }finally{fs.readFileSync=read;fs.existsSync=exists;fs.statSync=stat;}
  try {
    for(const [target,want] of [['/install.sh','/cli/opli-install.sh'],['/latest.json','/cli/latest.json'],['/releases/0.10.0/manifest.json.sig','/cli/releases/0.10.0/manifest.json.sig'],['/releases/0.10.0/SHA256SUMS','/cli/releases/0.10.0/SHA256SUMS']]) {
      const nextUrl=new URL('https://opli.tervory.com'+target);nextUrl.clone=()=>new URL(nextUrl);
      assert.equal((await middleware({headers:new Headers({host:'opli.tervory.com'}),nextUrl})).rewrite,want);
    }
    assert(config.matcher.includes('/install.sh'));assert(config.matcher.includes('/latest.json'));assert(config.matcher.includes('/releases/:path*'));
    assert.equal(hosts.opliReleasePath('app.tervory.com','/install.sh'),null);
    assert.equal(hosts.opliReleasePath('opli.tervory.com','/releases/../private'),null);
    assert.equal(hosts.opliReleasePath('opli.tervory.com','/admin'),null);
    console.log('OPLI release aliases passed');
  }catch(error){console.error(error);process.exitCode=1;}
});
