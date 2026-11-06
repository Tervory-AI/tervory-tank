import test from 'node:test';
import assert from 'node:assert/strict';
import { buildRelease } from '../scripts/build-release.mjs';
import { signRelease } from '../scripts/sign-release.mjs';
import { verifyRelease } from '../scripts/verify-release.mjs';
import { generateKeyPairSync } from 'node:crypto';
import { createServer } from 'node:http';
import { mkdtemp, mkdir, readFile, writeFile, rm, readlink, access } from 'node:fs/promises';
import { execFile } from 'node:child_process';
import { promisify } from 'node:util';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { pathToFileURL } from 'node:url';
const execute=promisify(execFile);

test('ship signed installers and updates work on both release hosts and refuse tampering', async t => {
  const root=await mkdtemp(join(tmpdir(),'opli-ship-'));t.after(()=>rm(root,{recursive:true,force:true}));
  const site=join(root,'site');const platform=`${process.platform==='darwin'?'darwin':'linux'}-${process.arch}${process.platform==='darwin'?'':'-gnu'}`;
  const versions=['0.10.1','0.10.2'];const pair=generateKeyPairSync('ed25519',{privateKeyEncoding:{type:'pkcs8',format:'pem'},publicKeyEncoding:{type:'spki',format:'pem'}});
  for(const version of versions){buildRelease({out:site,platforms:[platform],version});signRelease(join(site,'releases',version),pair.privateKey,pair.publicKey);}
  for(const version of versions)assert.equal(verifyRelease(join(site,'releases',version),pair.publicKey,platform,version),1);
  const requests=[];
  const server=createServer(async(req,res)=>{try{let path=new URL(req.url,'http://localhost').pathname;requests.push(path);path=path==='/install.sh'?'/opli-install.sh':path.replace(/^\/cli\//,'/');if(path.includes('..'))throw Error();res.end(await readFile(join(site,path)));}catch{res.writeHead(404).end();}});
  await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));t.after(()=>new Promise(resolve=>server.close(resolve)));
  const origin=`http://127.0.0.1:${server.address().port}`;const bin=join(root,'bin');await mkdir(bin);
  const downloader = '#!/bin/sh\nexec "$NODE_EXECUTABLE" "$TERVORY_TEST_DOWNLOADER" "$@"\n';
  await writeFile(join(bin,'curl'),downloader,{mode:0o755});
  for(const base of ['https://opli.tervory.com','https://app.tervory.com/cli']) {
    const name=base.includes('opli.')?'opli':'app';const home=join(root,name);const installer=join(root,name+'.sh');
    const served=await fetch(origin+(name==='opli'?'/install.sh':'/cli/install.sh'));await writeFile(installer,await served.text());
    const env={...process.env,NODE_EXECUTABLE:process.execPath,TERVORY_TEST_DOWNLOADER:new URL('./fixtures/download-release.cjs',import.meta.url).pathname,TERVORY_TEST_RELEASE_BASE:base,TERVORY_TEST_RELEASE_ORIGIN:origin,PATH:bin+':'+process.env.PATH,TERVORY_HOME:home,TERVORY_BIN_DIR:join(home,'bin'),TERVORY_CLI_VERSION:versions[0],TERVORY_NO_UPDATE_CHECK:'1'};
    delete env.TERVORY_CLI_BASE;delete env.TERVORY_CLI_PUBLIC_KEY_FILE;
    if (process.platform === 'win32') {
      await assert.rejects(execute('sh',[installer],{env}), error => /Unsupported system/.test(error.stderr));
      continue;
    }
    const installed=await execute('sh',[installer],{env});assert(installed.stdout.includes('Release signatures verified.'));
    const launcher=join(home,'bin/tervory');
    assert((await execute(launcher,['version'],{env})).stdout.includes(versions[0]));
    const old=join(home,'cli',versions[0]);const record=JSON.parse(await readFile(join(old,'RELEASE.json'),'utf8'));assert.equal(record.release_base,base);assert.equal(record.signed,true);
    const trusted=await readFile(join(old,'TRUSTED-RELEASE.pem'),'utf8');assert.equal(trusted,pair.publicKey);
    const {update}=await import(pathToFileURL(join(old,'src/update.mjs')));const urls=[];
    const transport=(url,init)=>{assert(String(url).startsWith(base+'/'));urls.push(String(url));return fetch(origin+new URL(url).pathname,init);};
    const sig=join(site,'releases',versions[1],'manifest.json.sig');const signature=await readFile(sig);await writeFile(sig,Buffer.alloc(64).toString('base64'));
    await assert.rejects(update({root:old,transport,io:{write(){}}}),/signature invalid/);assert.equal(await readlink(join(home,'cli/current')),versions[0]);await writeFile(sig,signature);
    const bridge = new URL('./fixtures/release-fetch.mjs', import.meta.url);
    requests.length=0;
    const updated=await execute(launcher,['update'],{env:{...env,TERVORY_CLI_VERSION:'',NODE_OPTIONS:(env.NODE_OPTIONS??'')+' --import='+bridge.href}});
    assert(updated.stdout.includes(`Updated Tervory CLI ${versions[0]} -> ${versions[1]}.`));assert.equal(await readlink(join(home,'cli/current')),versions[1]);
    assert((await execute(launcher,['version'],{env})).stdout.includes(versions[1]));
    assert.equal(await readFile(join(home,'cli',versions[1],'TRUSTED-RELEASE.pem'),'utf8'),trusted);assert(requests.some(url=>url.endsWith('.tar.gz.sig')));
    const current=join(home,'cli',versions[1]);await rm(join(current,'TRUSTED-RELEASE.pem'));await assert.rejects(update({root:current,transport,io:{write(){}}}),/trust key missing/);
    const archiveSig=join(site,'releases',versions[0],`tervory-cli-${versions[0]}-${platform}.tar.gz.sig`);const before=await readFile(archiveSig);await writeFile(archiveSig,Buffer.alloc(64).toString('base64'));
    const fresh=join(root,name+'-bad');await assert.rejects(execute('sh',[installer],{env:{...env,TERVORY_HOME:fresh,TERVORY_BIN_DIR:join(fresh,'bin')}}));await assert.rejects(access(join(fresh,'cli/current')));await writeFile(archiveSig,before);
  }
});
