import * as vscode from 'vscode';
import assert from 'node:assert/strict';
import { promises as fs } from 'node:fs';
import path from 'node:path';
import type { IndexApi } from '../src/api';
export async function run():Promise<void> {
  const extension=vscode.extensions.getExtension<IndexApi>('tervory.tervory-index');
  assert.ok(extension,'stock editor discovers extension');
  const api=await extension.activate(); await api.ready();
  assert.equal(api.version,1); assert.equal(api.fileCount(),2);
  const semantic=await api.search('help someone regain access to their account');
  assert.equal(semantic[0].path,'account.ts');
  const exact=await api.search('resetPassword(email:',{mode:'exact'});
  assert.equal(exact[0].path,'account.ts'); assert.equal(exact[0].startLine,2);
  assert.equal((await api.search('RESETPASSWORD',{mode:'exact'})).length,0);
  const attached=await api.getRelevantCode('forgot password',{maxCharacters:200});
  assert.ok(attached.length>0);assert.ok(attached.reduce((n,m)=>n+m.text.length,0)<=200);
  assert.ok(attached.every(m=>m.uri.startsWith('file:')));
  const root=vscode.workspace.workspaceFolders![0].uri.fsPath;
  const changed=path.join(root,'created.ts');
  await fs.writeFile(changed,'export const watcherCreated = 1;');
  // Observe the watcher itself; calling refresh here would hide broken subscriptions.
  const waitFor=async(check:()=>boolean)=>{
    const deadline=Date.now()+30000;
    while(!check()) {if(Date.now()>deadline)assert.fail('watcher refresh timed out');await new Promise(r=>setTimeout(r,200));}
  };
  await waitFor(()=>api.fileCount()===3);
  await fs.writeFile(changed,'export const watcherChanged = 2;');
  await new Promise(r=>setTimeout(r,1000));await api.ready();
  assert.equal((await api.search('watcherChanged',{mode:'exact'})).length,1);
  await fs.unlink(changed);await waitFor(()=>api.fileCount()===2);
  await fs.writeFile(path.join(root,'.tervoryignore'),'account.ts\n');
  await waitFor(()=>api.fileCount()===1);
  assert.equal((await api.search('resetPassword',{mode:'exact'})).length,0);
  await fs.unlink(path.join(root,'.tervoryignore'));await waitFor(()=>api.fileCount()===2);
  assert.ok((await vscode.commands.getCommands()).includes('tervory.index.search'));
  console.log('Stock VSCodium: activation, real semantic and literal retrieval, attachment budget and file watchers passed.');
}
