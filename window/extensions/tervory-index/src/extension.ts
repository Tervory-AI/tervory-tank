import * as vscode from 'vscode';
import path from 'node:path';
import { createHash } from 'node:crypto';
import { ProjectIndex } from './index';
import { LocalEmbedder } from './embedding';
export async function activate(context:vscode.ExtensionContext) {
  const indexes = new Map<string,ProjectIndex>();
  const output = vscode.window.createOutputChannel('[Project index]');
  context.subscriptions.push(output);
  let timer:ReturnType<typeof setTimeout>|undefined;
  let running = Promise.resolve();
  const refresh = ():Promise<void> => {
    running = running.catch(e=>output.appendLine(String(e))).then(async () => {
      if (!vscode.workspace.isTrusted || !context.storageUri) return;
      const roots = (vscode.workspace.workspaceFolders??[]).filter(f=>f.uri.scheme==='file');
      for (const [root,index] of indexes) if (!roots.some(f=>f.uri.fsPath===root)) {
        indexes.delete(root); await index.dispose();
      }
      for (const folder of roots) {
        let index = indexes.get(folder.uri.fsPath);
        if (!index) {
          const key = createHash('sha256').update(folder.uri.toString()).digest('hex');
          index = new ProjectIndex(folder.uri.fsPath,path.join(context.storageUri.fsPath,key),
            new LocalEmbedder(context.asAbsolutePath('models')));
          await index.restore(); indexes.set(folder.uri.fsPath,index);
        }
        await index.refresh();
      }
    });
    return running;
  };
  const schedule = () => { clearTimeout(timer); timer=setTimeout(()=>{void refresh().catch(e=>output.appendLine(String(e)));},300); };
  const watcher = vscode.workspace.createFileSystemWatcher('**/*');
  context.subscriptions.push(watcher,watcher.onDidCreate(schedule),watcher.onDidChange(schedule),watcher.onDidDelete(schedule),
    vscode.workspace.onDidChangeWorkspaceFolders(schedule),vscode.workspace.onDidGrantWorkspaceTrust(schedule),
    vscode.commands.registerCommand('tervory.index.rebuild',refresh),
    {dispose:()=>{clearTimeout(timer);void running.catch(()=>{}).then(()=>Promise.all([...indexes.values()].map(i=>i.dispose())));}});
  // Return promptly so the panel can activate us while a large project is indexing.
  void refresh().catch(e=>output.appendLine(String(e)));
  return {version:1,ready:()=>running,refresh,fileCount:()=>[...indexes.values()].reduce((n,i)=>n+i.fileCount,0)};
}
