import { runTests } from '@vscode/test-electron';
import { promises as fs } from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { createHash } from 'node:crypto';
import { execFileSync } from 'node:child_process';
const root=fileURLToPath(new URL('../',import.meta.url));
const lock=JSON.parse(await fs.readFile(new URL('./editor-lock.json',import.meta.url),'utf8'));
const asset=lock.assets[`${process.platform}-${process.arch}`];
if (!asset) throw new Error('Unsupported editor test platform');
const cache=process.env.TERVORY_EDITOR_CACHE??path.join(root,'.vscode-test');
const directory=path.join(cache,`${process.platform}-${process.arch}`);
const executable=process.platform==='darwin'?path.join(directory,'VSCodium.app/Contents/MacOS/Electron'):path.join(directory,process.platform==='win32'?'VSCodium.exe':'codium');
try {await fs.access(executable);} catch {
  await fs.mkdir(directory,{recursive:true});
  const response=await fetch(`https://github.com/VSCodium/vscodium/releases/download/${lock.version}/${asset.file}`);
  if (!response.ok) throw new Error(`Editor download failed: ${response.status}`);
  const data=Buffer.from(await response.arrayBuffer());
  if (createHash('sha256').update(data).digest('hex')!==asset.sha256) throw new Error('Editor checksum mismatch');
  const archive=path.join(directory,asset.file); await fs.writeFile(archive,data);
  if (process.platform==='win32') execFileSync('tar',['-xf',archive,'-C',directory]);
  else if (process.platform==='darwin') execFileSync('unzip',['-q',archive,'-d',directory]);
  else execFileSync('tar',['-xzf',archive,'-C',directory]);
  await fs.unlink(archive);
}
const project=path.join(cache,'fixture');
await fs.rm(project,{recursive:true,force:true});
await fs.mkdir(project,{recursive:true});
await fs.writeFile(path.join(project,'account.ts'),'// Recover access when a user forgets their password.\nexport function resetPassword(email: string) { return email; }\n');
await fs.writeFile(path.join(project,'landscape.ts'),'// Paint trees, mountains and a river on a canvas.\nexport function drawLandscape() { return "green"; }\n');
await runTests({vscodeExecutablePath:executable,extensionDevelopmentPath:root,extensionTestsPath:path.join(root,'dist/test/electron.test.js'),
  launchArgs:[project,'--no-sandbox','--disable-gpu','--disable-workspace-trust','--skip-welcome','--skip-release-notes','--disable-telemetry','--user-data-dir',path.join(directory,'test-profile'),'--extensions-dir',path.join(directory,'extensions')]});
