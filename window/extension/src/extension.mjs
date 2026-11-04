import { randomBytes } from 'node:crypto';
import { cli, InputQueue, hunks, selectedDiff } from './session.mjs';

export async function activate(vscode, context) {
  const client = await cli('client.mjs');
  const { CodeFolder, splitDiff, applyDiff, redactSecrets } = await cli('code-tools.mjs');
  const { codeSession } = await cli('code-mode.mjs');
  const store = { get: () => context.secrets.get('tervory.session'), set: value => context.secrets.store('tervory.session', value), remove: () => context.secrets.delete('tervory.session') };
  const documents = new Map();
  context.subscriptions.push(vscode.workspace.registerTextDocumentContentProvider('tervory-diff', { provideTextDocumentContent: uri => documents.get(uri.toString()) ?? '' }));
  let view; let session; let busy = false; let review; let terminal;
  const send = value => view?.webview.postMessage(value);
  const write = value => send({ type: 'output', text: client.safe(redactSecrets(String(value))) });
  const folder = () => {
    const roots = vscode.workspace.workspaceFolders ?? [];
    if (roots.length !== 1 || roots[0].uri.scheme !== 'file') throw Error('Open one local project folder.');
    if (!vscode.workspace.isTrusted) throw Error('Trust this project before running code tools.');
    return roots[0].uri.fsPath;
  };
  async function signIn() {
    const region = await vscode.window.showQuickPick([{ label: 'US', value: 'us-east' }, { label: 'ZA', value: 'za' }], { title: 'Sign in to Tervory' });
    if (!region) return;
    await client.run(['login', '--region', region.value], { store, io: { interactive: true, write, deviceName: () => 'Tervory desktop', open: url => vscode.env.openExternal(vscode.Uri.parse(url)) } });
  }
  async function reviewEdit(local, patch, signal) {
    const files = splitDiff(patch); const cards = []; let index = 0;
    for (const file of files) {
      const before = await local.read(file.name);
      const after = await applyDiff(before.text ?? '', file.patch, file.name, !before.exists, local.root);
      const id = randomBytes(16).toString('hex');
      const left = vscode.Uri.parse(`tervory-diff:/${id}/before/${encodeURIComponent(file.name)}`);
      const right = vscode.Uri.parse(`tervory-diff:/${id}/after/${encodeURIComponent(file.name)}`);
      documents.set(left.toString(), before.text ?? ''); documents.set(right.toString(), after);
      const items = hunks(file).map(hunk => ({ index: index++, label: hunk.label, diff: hunk.lines.join('\n') }));
      cards.push({ name: file.name, before: left.toString(), after: right.toString(), hunks: items });
    }
    try {
      send({ type: 'review', files: cards });
      return await new Promise(done => {
        const cancel = () => { review = undefined; done(''); };
        review = { cards, done: selected => { signal.removeEventListener('abort', cancel); review = undefined; done(selectedDiff(files, selected)); } };
        signal.addEventListener('abort', cancel, { once: true });
        if (signal.aborted) cancel();
      });
    } finally { for (const card of cards) { documents.delete(card.before); documents.delete(card.after); } }
  }
  async function startCode(text) {
    if (session) { session.input.push(text); return; }
    const input = new InputQueue(); const abort = new AbortController();
    session = { input, abort }; input.push(text);
    const io = {
      interactive: true, signal: abort.signal, write,
      prompt: async prompt => {
        if (prompt === '> ') { busy = false; send({ type: 'ready' }); return input.next(); }
        const value = await vscode.window.showWarningMessage(prompt.startsWith('Run') ? 'Run this command in the project?' : prompt.startsWith('Undo') ? 'Undo the last accepted edit?' : 'Confirm this action?', { modal: true }, 'Confirm');
        return abort.signal.aborted ? null : value === 'Confirm' ? 'y' : 'n';
      },
    };
    try {
      const tank = new client.Tank(await client.session(store), fetch, abort.signal);
      await codeSession(tank, folder(), 'auto', io, client.receiptLines, client.safe, {
        createFolder: async root => {
          const local = await CodeFolder.create(root); const tool = local.tool.bind(local);
          local.tool = async (request, toolIO, options) => {
            if (request.name === 'propose_edit') {
              const patch = await reviewEdit(local, request.arguments.diff, abort.signal);
              if (!patch) return { applied: false };
              return tool({ name: 'propose_edit', arguments: { diff: patch } }, { ...toolIO, prompt: async () => abort.signal.aborted ? null : 'y' }, options);
            }
            if (request.name === 'run_command') {
              const output = new vscode.EventEmitter();
              terminal?.dispose();
              terminal = vscode.window.createTerminal({ name: 'Tervory commands', pty: { onDidWrite: output.event, open() {}, close() { abort.abort(); } } });
              terminal.show(true);
              const commandIO = { ...toolIO, write: value => { toolIO.write(value); output.fire(client.safe(redactSecrets(value)).replaceAll('\n', '\r\n')); } };
              return tool(request, commandIO, options);
            }
            return tool(request, toolIO, options);
          };
          return local;
        },
      });
    } finally { input.close(); session = undefined; busy = false; send({ type: 'ready' }); }
  }
  async function ask(text) {
    const local = await CodeFolder.create(folder());
    const files = await local.files();
    const editor = vscode.window.activeTextEditor;
    let contextText = `Project files:\n${JSON.stringify(files)}`;
    if (editor?.document.uri.scheme === 'file') {
      const name = vscode.workspace.asRelativePath(editor.document.uri, false);
      const file = await local.read(name);
      if (file.exists) contextText += `\nOpen file ${name}:\n${file.text}`;
    }
    const abort = new AbortController(); session = { abort, input: new InputQueue() };
    try {
      const tank = new client.Tank(await client.session(store), fetch, abort.signal);
      const thread = (await tank.json('/v1/command/threads', {})).thread_id;
      await client.showTurn(tank, thread, redactSecrets(`${text}\n\n${contextText}`), 'auto', [], {
        interactive: true, signal: abort.signal, write,
        prompt: async () => (await vscode.window.showWarningMessage('Confirm this tool action?', { modal: true }, 'Confirm')) === 'Confirm' && !abort.signal.aborted ? 'y' : 'n',
      });
    } finally { session = undefined; busy = false; send({ type: 'ready' }); }
  }
  const provider = {
    resolveWebviewView(next) {
      view = next;
      const nonce = randomBytes(24).toString('hex');
      view.webview.options = { enableScripts: true, localResourceRoots: [] };
      view.webview.html = html(nonce);
      context.subscriptions.push(view.webview.onDidReceiveMessage(async message => {
        try {
          if (!message || typeof message.type !== 'string') return;
          if (message.type === 'cancel') { session?.abort.abort(); session?.input.close(); review?.done(new Set()); return; }
          if (message.type === 'signIn') { await signIn(); return; }
          if (message.type === 'signOut') { session?.abort.abort(); session?.input.close(); await client.run(['logout'], { store, io: { write } }); return; }
          if (message.type === 'preview' && review) {
            const card = review.cards.find(card => card.name === message.name);
            if (card) await vscode.commands.executeCommand('vscode.diff', vscode.Uri.parse(card.before), vscode.Uri.parse(card.after), card.name);
            return;
          }
          if (message.type === 'accept' && review && Array.isArray(message.hunks)) {
            const allowed = new Set(review.cards.flatMap(card => card.hunks.map(hunk => hunk.index)));
            if (message.hunks.every(id => Number.isInteger(id) && allowed.has(id))) review.done(new Set(message.hunks));
            return;
          }
          if (!['ask', 'code', 'undo'].includes(message.type) || busy) return;
          const text = message.type === 'undo' ? '/undo' : message.text;
          if (typeof text !== 'string' || !text.trim() || text.length > 200000) return;
          busy = true;
          if (message.type === 'ask') {
            if (session) throw Error('Finish or stop the code conversation first.');
            await ask(text);
          } else await startCode(text);
        } catch (error) { busy = false; write(error.message); send({ type: 'ready' }); }
      }));
      context.subscriptions.push(view.onDidDispose(() => { session?.abort.abort(); session?.input.close(); review?.done(new Set()); view = undefined; }));
    },
  };
  context.subscriptions.push(vscode.window.registerWebviewViewProvider('tervory.panel', provider));
  context.subscriptions.push(vscode.commands.registerCommand('tervory.focus', () => vscode.commands.executeCommand('tervory.panel.focus')));
  context.subscriptions.push(vscode.commands.registerCommand('tervory.signIn', signIn));
  context.subscriptions.push({ dispose() { session?.abort.abort(); session?.input.close(); terminal?.dispose(); documents.clear(); } });
  return { provider, signIn };
}

export function html(nonce) {
  return `<!doctype html><html><head><meta charset="utf-8"><meta http-equiv="Content-Security-Policy" content="default-src 'none'; style-src 'nonce-${nonce}'; script-src 'nonce-${nonce}';"><style nonce="${nonce}">
body{background:#fff;color:#001840;font:14px system-ui;margin:16px}button{background:#001840;color:white;border:0;border-radius:4px;padding:9px;margin:4px;cursor:pointer}textarea{box-sizing:border-box;width:100%;min-height:90px;background:#F4F6FB;color:#001840;border:1px solid #B8BFD0;padding:10px}pre{white-space:pre-wrap;overflow-wrap:anywhere;font:12px monospace}fieldset{border:1px solid #B8BFD0;margin:8px 0}label{display:block;padding:6px}input{margin-right:8px}</style></head><body>
<h2>Tervory</h2><button id="signIn">Sign in</button><button id="signOut">Sign out</button><pre id="output" role="log" aria-live="polite"></pre><div id="review"></div><label for="text">Ask about this project or describe a change</label><textarea id="text"></textarea><button id="ask">Ask</button><button id="code">Edit</button><button id="undo">Undo</button><button id="cancel">Stop</button>
<script nonce="${nonce}">
const api=acquireVsCodeApi(),byId=id=>document.getElementById(id);let waiting=false;
for(const type of ['signIn','signOut','ask','code','undo','cancel'])byId(type).onclick=()=>{if(waiting&&['ask','code','undo'].includes(type))return;if(['ask','code','undo'].includes(type))waiting=true;api.postMessage({type,text:byId('text').value});};
window.addEventListener('message',({data})=>{if(data.type==='ready'){waiting=false;return;}if(data.type==='output'){byId('output').textContent+=data.text;return;}if(data.type!=='review')return;
const area=byId('review');area.replaceChildren();for(const file of data.files){const box=document.createElement('fieldset'),title=document.createElement('legend');title.textContent=file.name;box.append(title);const preview=document.createElement('button');preview.textContent='Open diff';preview.onclick=()=>api.postMessage({type:'preview',name:file.name});box.append(preview);const all=document.createElement('button');all.textContent='Accept file';const none=document.createElement('button');none.textContent='Reject file';box.append(all,none);all.onclick=()=>box.querySelectorAll('input').forEach(x=>x.checked=true);none.onclick=()=>box.querySelectorAll('input').forEach(x=>x.checked=false);
for(const hunk of file.hunks){const label=document.createElement('label'),input=document.createElement('input'),code=document.createElement('pre');input.type='checkbox';input.dataset.index=hunk.index;input.checked=false;label.append(input,document.createTextNode('Accept hunk '+hunk.label));code.textContent=hunk.diff;box.append(label,code);}area.append(box);}
const apply=document.createElement('button');apply.textContent='Apply selected';apply.onclick=()=>{api.postMessage({type:'accept',hunks:[...area.querySelectorAll('input:checked')].map(x=>Number(x.dataset.index))});area.replaceChildren();};const reject=document.createElement('button');reject.textContent='Reject all';reject.onclick=()=>{api.postMessage({type:'accept',hunks:[]});area.replaceChildren();};area.append(apply,reject);});
</script></body></html>`;
}
