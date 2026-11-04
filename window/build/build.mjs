import { execFileSync } from 'node:child_process';
import { cp, mkdir, readFile, writeFile, rm, readdir } from 'node:fs/promises';
import { resolve } from 'node:path';
import { createHash } from 'node:crypto';
import { prepare, root, pin, source } from './prepare.mjs';
import { installExtensions } from './extensions.mjs';
const platform = process.platform; const arch = process.arch;
if (!['win32', 'darwin', 'linux'].includes(platform) || !['x64', 'arm64'].includes(arch)) throw Error('Unsupported build host');
if (process.versions.node.split('.')[0] !== pin.node.split('.')[0]) throw Error(`Use Node ${pin.node}`);
await prepare();
const npm = (args, cwd = source) => execFileSync(process.execPath, [process.env.npm_execpath, ...args], { cwd, stdio: 'inherit', env: { ...process.env, VSCODE_QUALITY: 'stable', VSCODE_ARCH: arch, BUILD_SOURCEVERSION: pin.commit } });
// Code-OSS postinstall builds its platform-native modules. Do not disable scripts.
npm(['ci']);
npm(['ci', '--ignore-scripts', '--no-audit', '--no-fund'], resolve(root, 'cli'));
npm(['run', 'gulp', '--', `vscode-${platform}-${arch}-min`]);
const built = resolve(source, `../VSCode-${platform}-${arch}`);
// Copilot is excluded from the distribution. Tervory's extension is copied from
// our own build below, with the unmodified CLI source, rather than a second agent.
const resources = platform === 'darwin' ? resolve(built, 'Tervory.app/Contents/Resources/app') : resolve(built, 'resources/app');
await rm(resolve(resources, 'extensions/copilot'), { recursive: true, force: true });
await installExtensions(root, resources);
const out = resolve(root, 'window/dist'); await mkdir(out, { recursive: true });
// Use the upstream platform installers. Signing stays off until configured.
if (platform === 'win32') {
  npm(['run', 'gulp', '--', `vscode-win32-${arch}-user-setup`]);
  await cp(resolve(source, `.build/win32-${arch}/user-setup/VSCodeSetup.exe`), resolve(out, `tervory-window-win32-${arch}-setup.exe`));
} else if (platform === 'linux') {
  npm(['run', 'gulp', '--', `vscode-linux-${arch}-prepare-deb`, `vscode-linux-${arch}-build-deb`]);
  const debs = resolve(source, `.build/linux/deb/${arch === 'x64' ? 'amd64' : 'arm64'}/deb`);
  for (const deb of await readdir(debs)) if (deb.endsWith('.deb')) await cp(resolve(debs, deb), resolve(out, deb));
} else {
  execFileSync('hdiutil', ['create', '-volname', 'Tervory', '-srcfolder', built, '-ov', '-format', 'UDZO', resolve(out, `tervory-window-darwin-${arch}.dmg`)], { stdio: 'inherit' });
}
const file = `tervory-window-${platform}-${arch}.tar.gz`;
execFileSync('tar', ['-czf', resolve(out, file), '-C', built, '.'], { stdio: 'inherit' });
let sums = '';
for (const name of await readdir(out)) {
  if (!/\.(deb|exe|dmg|gz)$/.test(name)) continue;
  sums += `${createHash('sha256').update(await readFile(resolve(out, name))).digest('hex')}  ${name}\n`;
}
await writeFile(resolve(out, 'SHA256SUMS'), sums);
await writeFile(resolve(out, 'build.json'), JSON.stringify({ upstream: pin, platform, arch, signed: false, files: await readdir(out) }, null, 2));
console.log(resolve(out, file));
