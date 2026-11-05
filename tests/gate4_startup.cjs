const assert = require('node:assert/strict');
const http = require('node:http');
const {spawn} = require('node:child_process');
const {once} = require('node:events');
const path = require('node:path');
const root = path.resolve(__dirname, '..');
const settings=['TANK_URL','TANK_API_KEY','TRIGGER_SIGNIN_WORKSPACE_SECRET'];
const pause = ms => new Promise(resolve=>setTimeout(resolve,ms));
function request(port, pathname, method='GET') {
  return new Promise((resolve,reject)=>{
    const req=http.request({hostname:'127.0.0.1',port,path:pathname,method,timeout:3000},res=>{
      let body='';res.setEncoding('utf8');res.on('data',chunk=>body+=chunk);res.on('end',()=>resolve({status:res.statusCode,body}));
    });req.on('error',reject);req.on('timeout',()=>req.destroy(Error('request timed out')));req.end();
  });
}
async function freePort(){const server=http.createServer();server.listen(0,'127.0.0.1');await once(server,'listening');const port=server.address().port;await new Promise(resolve=>server.close(resolve));return port;}
async function main(){
  let calls=0;
  const upstream=http.createServer((req,res)=>{calls++;res.writeHead(500);res.end();});
  upstream.listen(0,'127.0.0.1');await once(upstream,'listening');
  try {
    for(const missing of settings){
      const port=await freePort();
      const env={...process.env,TANK_URL:`http://127.0.0.1:${upstream.address().port}`,TANK_API_KEY:'offline-startup-placeholder',TRIGGER_SIGNIN_WORKSPACE_SECRET:'offline-session-placeholder',NEXT_TELEMETRY_DISABLED:'1'};
      delete env[missing];delete env.NODE_OPTIONS;
      const child=spawn(process.execPath,['node_modules/next/dist/bin/next','start','--hostname','127.0.0.1','--port',String(port)],{cwd:path.join(root,'workspace'),env,stdio:'ignore'});
      try {
        let ready;
        for(let i=0;i<100;i++){try{ready=await request(port,'/sign-in');break;}catch{if(child.exitCode!==null)throw Error('startup exited');await pause(100);}}
        assert(ready,'startup did not answer');assert.equal(ready.status,200);assert(ready.body.includes(missing));
        const home=await request(port,'/');assert.equal(home.status,200);assert(home.body.includes(missing));
        for(const [route,method] of [['/api/auth/session','GET'],['/api/tasks','GET'],['/api/tasks','POST']]){
          const result=await request(port,route,method);assert.equal(result.status,503,route);assert(result.body.includes(missing));
        }
        assert.equal(calls,0,'incomplete setup must make no upstream requests');
      } finally {
        const closed=once(child,'exit');child.kill('SIGTERM');await closed;
      }
    }
    console.log('Gate 4 startup: each missing setting renders HTTP 200 setup guidance; reads and writes return 503; zero upstream calls.');
  } finally {await new Promise(resolve=>upstream.close(resolve));}
}
main().catch(error=>{console.error(error);process.exitCode=1;});
