const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const { workspace } = require('../command_acceptance_20261031/workspace_loader.cjs');
let input = '';
process.stdin.setEncoding('utf8');
process.stdin.on('data', chunk => { input += chunk; });
process.stdin.on('end', async () => {
  try {
    const original = fs.readFileSync;
    const target = path.resolve(__dirname, '../../workspace/lib/tank.ts');
    const calls = [];
    fs.readFileSync = (name, ...options) => path.resolve(String(name)) === target ? input : original(name, ...options);
    let proxy;
    try { proxy = workspace({ env: { TANK_URL: 'http://placeholder-tank', TANK_API_KEY: 'placeholder-key' }, fetch: async (url, init) => { calls.push({ url, init }); return Response.json([]); } })('lib/tank.ts').personalCommandRequest; }
    finally { fs.readFileSync = original; }
    const token = 'tv1.us-east.' + '1'.repeat(32) + '.' + 'placeholder'.padEnd(43, 'x');
    for (const route of ['code-models', 'code-mcp-policy', 'code-sessions', 'code-sessions/00000000-0000-0000-0000-000000000011']) {
      const result = await proxy(new Request('https://app.tervory.com/v1/command/' + route, { headers: { authorization: 'Bearer ' + token, host: 'app.tervory.com', 'x-tervory-user': 'forged', 'x-tank-key': 'forged' } }), route.split('/'));
      assert.equal(result.status, 200);
      assert.deepEqual(Object.keys(calls.at(-1).init.headers).sort(), ['Authorization', 'Content-Type']);
    }
    for (const [route, method, body] of [['code-mcp-policy','PUT',{server_id:'stdio:placeholder',blocked:true}],['code-attachments','POST',{thread_id:'00000000-0000-0000-0000-000000000011',name:'image.png',base64:'placeholder'}],['threads/00000000-0000-0000-0000-000000000011/code-stream','POST',{text:'inspect'}]]) {
      const result = await proxy(new Request('https://app.tervory.com/v1/command/'+route,{method,body:JSON.stringify(body),headers:{authorization:'Bearer '+token,'content-type':'application/json','x-tervory-role':'org:admin'}}),route.split('/'));
      assert.equal(result.status,200);
      assert.deepEqual(Object.keys(calls.at(-1).init.headers).sort(),['Authorization','Content-Type']);
    }
    const before = calls.length;
    for (const route of ['models', 'code-sessions/not-an-id']) {
      assert.equal((await proxy(new Request('https://app.tervory.com/v1/command/' + route, { headers: { authorization: 'Bearer ' + token, host:'app.tervory.com' } }), route.split('/'))).status, 404);
    }
    assert.equal(calls.length, before);
    console.log('OPLI corridor checks passed');
  } catch (error) { console.error(error); process.exitCode = 1; }
});
