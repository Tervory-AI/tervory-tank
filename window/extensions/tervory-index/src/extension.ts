import * as vscode from 'vscode';
import path from 'node:path';
import { createHash } from 'node:crypto';
import { ProjectIndex } from './index';
import { LocalEmbedder } from './embedding';
import type { Span } from './chunks';
import { budget, type IndexApi, type CodeMatch } from './api';
let deactivateCurrent:()=>Promise<void>=async()=>{};
export function deactivate():Promise<void> {return deactivateCurrent();}
export async function activate(context:vscode.ExtensionContext) {
  const indexes = new Map<string,ProjectIndex>();
  const output = vscode.window.createOutputChannel('[Project index]');
  context.subscriptions.push(output);
  let timer:ReturnType<typeof setTimeout>|undefined;
  let running = Promise.resolve();
  let disposed=false;
  let closing:Promise<void>|undefined;
  const close=()=>closing??=(async()=>{
    disposed=true;clearTimeout(timer);await running.catch(()=>{});
    await Promise.all([...indexes.values()].map(index=>index.dispose()));indexes.clear();
  })();
  deactivateCurrent=close;
  const refresh = ():Promise<void> => {
    if(disposed)return Promise.resolve();
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
            new LocalEmbedder(context.asAbsolutePath('models')),async file=>{
              if (/\.[cm]?[jt]sx?$|\.py$/.test(file)) return [];
              const uri=vscode.Uri.joinPath(folder.uri,...file.split('/'));
              // Reuse installed language providers; never run repository executables.
              const symbols=await Promise.race([
                vscode.commands.executeCommand<(vscode.DocumentSymbol|vscode.SymbolInformation)[]>('vscode.executeDocumentSymbolProvider',uri).then(value=>value,()=>undefined),
                new Promise<undefined>(resolve=>setTimeout(resolve,1000))
              ]);
              const spans:Span[]=[];
              const collect=(items:(vscode.DocumentSymbol|vscode.SymbolInformation)[])=>{
                for(const item of items) {
                  const range='range' in item?item.range:item.location.range;
                  spans.push({startLine:range.start.line,endLine:range.end.line});
                  if('children' in item)collect(item.children);
                }
              };
              collect(symbols??[]);return spans;
            });
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
    {dispose:()=>{void close();}});
  // Return promptly so the panel can activate us while a large project is indexing.
  void refresh().catch(e=>output.appendLine(String(e)));
  const api:IndexApi = {
    version:1,ready:()=>running,refresh,fileCount:()=>[...indexes.values()].reduce((n,i)=>n+i.fileCount,0),
    async search(query,options={}) {
      if (!vscode.workspace.isTrusted) return [];
      await refresh();
      const results:CodeMatch[]=[];
      for (const [root,index] of indexes) {
        const rootUri=vscode.Uri.file(root);
        if (options.workspaceUri && options.workspaceUri!==rootUri.toString()) continue;
        for (const hit of await index.search(query,options.mode,options.limit)) {
          results.push({...hit,uri:vscode.Uri.joinPath(rootUri,...hit.path.split('/')).toString()});
        }
      }
      return results.sort((a,b)=>b.score-a.score).slice(0,Math.max(1,Math.min(50,options.limit??10)));
    },
    async getRelevantCode(query,options={}) {
      return budget(await api.search(query,{limit:options.limit??20,workspaceUri:options.workspaceUri}),options.maxCharacters);
    }
  };
  context.subscriptions.push(vscode.commands.registerCommand('tervory.index.search',async()=>{
    const mode=await vscode.window.showQuickPick([{label:'[Meaning]',mode:'meaning' as const},{label:'[Exact match]',mode:'exact' as const}],{placeHolder:'[Search mode]'});
    if (!mode) return;
    const query=await vscode.window.showInputBox({prompt:'[Search project]'});
    if (!query?.trim()) return;
    try {
      const matches=await api.search(query,{mode:mode.mode});
      if (!matches.length) {void vscode.window.showInformationMessage('[No matches]');return;}
      const selected=await vscode.window.showQuickPick(matches.map(hit=>({label:hit.path,description:`${hit.startLine}:${hit.endLine}`,detail:hit.text.slice(0,160),hit})),{placeHolder:'[Search results]'});
      if (selected) {
        const editor=await vscode.window.showTextDocument(vscode.Uri.parse(selected.hit.uri));
        const range=new vscode.Range(selected.hit.startLine-1,0,selected.hit.endLine-1,0);
        editor.selection=new vscode.Selection(range.start,range.end); editor.revealRange(range);
      }
    } catch {void vscode.window.showErrorMessage('[Search unavailable]');}
  }));
  return api;
}
