const vscode = require('vscode');
const {randomUUID} = require('node:crypto');
const path = require('node:path');
const {Controller} = require('./controller.mjs');
const {CodeFolder, splitDiff, applyDiff, redactSecrets} = require('../../../cli/src/code-tools.mjs');
const controllers = new Map();
let panel; let context; const documents = new Map();

function terminal() {
  const writes = new vscode.EventEmitter();
  const term = vscode.window.createTerminal({name:'Tervory', pty:{onDidWrite:writes.event, open(){}, close(){}}});
  return {write:text=>{writes.fire(text.replace(/\n/g, '\r\n')); panel?.webview.postMessage({type:'output', text});}, show:()=>term.show(true), dispose:()=>{term.dispose();writes.dispose();}};
}
async function preview(patch, folder) {
  const local = await CodeFolder.create(folder);
  const files = splitDiff(patch); const keys = [];
  try {
    for (const file of files) {
      const before = await local.read(file.name); const value = before.exists ? before.text : '';
      const after = await applyDiff(value, file.patch, file.name, !before.exists, folder);
      const id = randomUUID(); const left = `tervory-preview:/${id}/before/${file.name}`; const right = `tervory-preview:/${id}/after/${file.name}`;
      documents.set(left, value); documents.set(right, after); keys.push(left,right);
      await vscode.commands.executeCommand('vscode.diff', vscode.Uri.parse(left), vscode.Uri.parse(right), file.name, {preview:true});
    }
    return await vscode.window.showWarningMessage('Apply [y/N]', {modal:true}, 'Accept', 'Reject') === 'Accept';
  } finally { for (const key of keys) documents.delete(key); }
}
async function controller(folder) {
  if (!vscode.workspace.isTrusted) throw Error('Code tool refused.');
  folder ??= vscode.workspace.workspaceFolders?.length === 1 ? vscode.workspace.workspaceFolders[0] : await vscode.window.showWorkspaceFolderPick();
  if (!folder || folder.uri.scheme !== 'file') throw Error('Code mode requires a git repository.');
  const root = folder.uri.fsPath;
  if (!controllers.has(root)) {
    const tty = terminal();
    const store = {get:()=>context.secrets.get('tervory-session'),set:value=>context.secrets.store('tervory-session',value),remove:()=>context.secrets.delete('tervory-session')};
    const item = new Controller({folder:root,store,ui:{write:tty.write,open:url=>vscode.env.openExternal(vscode.Uri.parse(url)),diff:preview,
      approve:async label=>{tty.show();return await vscode.window.showWarningMessage(label,{modal:true},'y','N')==='y';}}});
    item.tty = tty; controllers.set(root,item);
  }
  return controllers.get(root);
}
async function input(mode) {
  const c = await controller();
  const text = await vscode.window.showInputBox({prompt:'> ',ignoreFocusOut:true});
  if (text) c.send(text,{askOnly:mode==='ask'});
}
exports.activate = function activate(extensionContext) {
  context=extensionContext;
  context.subscriptions.push(vscode.workspace.registerTextDocumentContentProvider('tervory-preview',{provideTextDocumentContent:uri=>documents.get(uri.toString()) ?? ''}));
  const commands = {
    'tervory.ask':()=>input('ask'), 'tervory.agent':()=>input('agent'),
    'tervory.undo':async()=>{(await controller()).send('/undo');},
    'tervory.loginUS':async()=>{await (await controller()).login('us-east');},
    'tervory.loginZA':async()=>{await (await controller()).login('za');},
    'tervory.plugins':async()=>{await (await controller()).command(['run','plugins','list']);},
    'tervory.inlineEdit':async()=>{const editor=vscode.window.activeTextEditor;if(!editor)return;
      const instruction=await vscode.window.showInputBox({prompt:'> '}); if(!instruction)return;
      const c=await controller(vscode.workspace.getWorkspaceFolder(editor.document.uri));
      c.inline(path.relative(c.folder,editor.document.uri.fsPath),editor.document.getText(editor.selection),instruction);},
    'tervory.background':async()=>{const task=await vscode.window.showInputBox({prompt:'> '});if(task)await(await controller()).background(task);},
    'tervory.review':async()=>{const pr=await vscode.window.showInputBox({prompt:'https://github.com/owner/repo/pull/number'});if(pr)(await controller()).review(pr);},
  };
  for(const [name,action] of Object.entries(commands))context.subscriptions.push(vscode.commands.registerCommand(name,async()=>{try{return await action();}catch(error){vscode.window.showErrorMessage(error.message);}}));
  context.subscriptions.push(vscode.window.registerWebviewViewProvider('tervory.chat',{resolveWebviewView(view){
    panel=view; const nonce=randomUUID().replaceAll('-','');view.webview.options={enableScripts:true,localResourceRoots:[vscode.Uri.joinPath(context.extensionUri,'media')]};
    const logo=view.webview.asWebviewUri(vscode.Uri.joinPath(context.extensionUri,'media/tervory-logo.png'));
    view.webview.html=`<!doctype html><html><head><meta http-equiv="Content-Security-Policy" content="default-src 'none'; img-src ${view.webview.cspSource}; style-src 'nonce-${nonce}'; script-src 'nonce-${nonce}';"><style nonce="${nonce}">body{color:var(--vscode-foreground);background:var(--vscode-sideBar-background)}img{width:180px}textarea{width:95%}pre{white-space:pre-wrap;overflow-wrap:anywhere}</style></head><body><img src="${logo}" alt="Tervory"><pre id="output"></pre><textarea id="input" aria-label="> "></textarea><button id="ask">Ask</button><button id="agent">Agent</button><button id="undo">/undo</button><button id="us">US</button><button id="za">ZA</button><script nonce="${nonce}">const api=acquireVsCodeApi();const text=document.getElementById('input');for(const id of ['ask','agent','undo','us','za'])document.getElementById(id).onclick=()=>{api.postMessage({type:id,text:text.value});text.value='';};window.addEventListener('message',event=>{if(event.data.type==='output'){const out=document.getElementById('output');out.textContent=(out.textContent+event.data.text).slice(-100000);}});</script></body></html>`;
    context.subscriptions.push(view.webview.onDidReceiveMessage(async message=>{try{
      if(!message || !['ask','agent','undo','us','za'].includes(message.type))return;
      const c=await controller();
      if(message.type==='us'||message.type==='za')await c.login(message.type==='us'?'us-east':'za');
      else if(message.type==='undo')c.send('/undo');
      else if(typeof message.text==='string' && message.text.trim())c.send(message.text,{askOnly:message.type==='ask'});
    }catch(error){vscode.window.showErrorMessage(error.message);}}));
  }}));
  // No route to a direct provider: autocomplete uses the same token-chosen Tank.
  context.subscriptions.push(vscode.languages.registerInlineCompletionItemProvider({scheme:'file'},{async provideInlineCompletionItems(doc,pos,_context,token){
    if(token.isCancellationRequested || !vscode.workspace.isTrusted)return [];
    const folder=vscode.workspace.getWorkspaceFolder(doc.uri);if(!folder)return [];
    const c=await controller(folder); const local=await CodeFolder.create(c.folder);
    const name=path.relative(c.folder,doc.uri.fsPath).split(path.sep).join('/');
    await local.read(name); // Same ignore, secret, size and symlink boundary.
    const stop=new AbortController();const subscription=token.onCancellationRequested(()=>stop.abort());
    try{
      await new Promise(resolve=>{const timer=setTimeout(resolve,300);stop.signal.addEventListener('abort',()=>{clearTimeout(timer);resolve();},{once:true});});
      if(stop.signal.aborted)return [];
      const offset=doc.offsetAt(pos);const text=doc.getText();const answer=await c.complete({path:name,prefix:text.slice(0,offset),suffix:text.slice(offset),signal:stop.signal});
      return answer && !stop.signal.aborted ? [new vscode.InlineCompletionItem(answer,new vscode.Range(pos,pos))] : [];
    }catch(error){if(!stop.signal.aborted)c.ui.write(error.message+'\n');return [];}finally{subscription.dispose();}
  }}));
  return {controller,preview};
};
exports.deactivate = async()=>{for(const c of controllers.values()){await c.close();c.tty.dispose();}controllers.clear();};
