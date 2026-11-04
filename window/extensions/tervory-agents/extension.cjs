const vscode = require('vscode');
const { randomUUID } = require('node:crypto');
const ORIGINS = { 'us-east': 'https://app.tervory.com', za: 'https://za.tervory.com' };

function activate(context) {
  async function call(path, body, method) {
    const token = await context.secrets.get('tervory.personal');
    const match = /^tv1\.(us-east|za)\.[0-9a-f]{32}\.[A-Za-z0-9_-]{43}$/.exec(token || '');
    if (!match) throw new Error('Connect Tervory first.');
    const response = await fetch(ORIGINS[match[1]] + '/v1/window-agents/' + path, {
      method: method || (body ? 'POST' : 'GET'),
      headers: { Authorization: `Bearer ${token}`, 'content-type': 'application/json' },
      body: body ? JSON.stringify(body) : undefined,
      signal: AbortSignal.timeout(30000), redirect: 'error',
    });
    if (!response.ok) throw new Error(`Request stopped (${response.status}).`);
    return response.status === 204 ? null : response.json();
  }
  const changes = new vscode.EventEmitter();
  const provider = {
    onDidChangeTreeData: changes.event,
    getTreeItem: item => item,
    async getChildren() { return []; },
  };
  context.subscriptions.push(vscode.window.registerTreeDataProvider('tervory.agents', provider), changes);
  const register = (name, action) => context.subscriptions.push(vscode.commands.registerCommand(name, async (...args) => {
    try { await action(...args); changes.fire(); }
    catch (error) { vscode.window.showErrorMessage(error.message); }
  }));
  register('tervory.agents.connect', async () => {
    const value = await vscode.window.showInputBox({ prompt: 'Tervory personal token', password: true, ignoreFocusOut: true });
    if (value) {
      if (!/^tv1\.(us-east|za)\.[0-9a-f]{32}\.[A-Za-z0-9_-]{43}$/.test(value)) throw new Error('Personal token refused.');
      await context.secrets.store('tervory.personal', value);
    }
  });
  register('tervory.agents.vault', async () => {
    const name = await vscode.window.showInputBox({ prompt: 'Credential name' });
    if (!name) return;
    const value = await vscode.window.showInputBox({ prompt: 'GitHub token — saved in your vault', password: true, ignoreFocusOut: true });
    if (value) await call('vault/github', { name, value }, 'PUT');
  });
  register('tervory.agents.start', async () => {
    const names = await call('vault/github');
    const credential_name = await vscode.window.showQuickPick(names, { placeHolder: 'GitHub credential name' });
    if (!credential_name) return;
    const repo = await vscode.window.showInputBox({ prompt: 'GitHub owner/repository' });
    if (!repo) return;
    const prompt = await vscode.window.showInputBox({ prompt: 'Task' });
    if (!prompt) return;
    await call('jobs', { repo, credential_name, prompt, request_id: randomUUID() });
  });
  register('tervory.agents.cancel', async item => {
    if (item?.jobId) await call(`jobs/${encodeURIComponent(item.jobId)}/cancel`, {});
  });
}
module.exports = { activate };
