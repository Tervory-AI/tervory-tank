import { cp, mkdir, readFile, readdir, access, rm } from 'node:fs/promises';
import { resolve, basename } from 'node:path';
import { execFileSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';

// Install every extension directory; a malformed sibling fails the build rather
// than silently shipping an OS with a feature missing.
export async function installExtensions(root, resources) {
  const folders = [];
  const panel = resolve(root, 'window/extension');
  try { await access(panel); folders.push(panel); } catch { /* gate 3 not present yet */ }
  const siblings = resolve(root, 'window/extensions');
  let entries = [];
  try { entries = await readdir(siblings, { withFileTypes: true }); } catch (error) { if (error.code !== 'ENOENT') throw error; }
  for (const entry of entries.sort((a, b) => a.name.localeCompare(b.name))) {
    if (entry.isSymbolicLink()) throw Error('Built-in extension must be a real directory.');
    if (entry.isDirectory()) folders.push(resolve(siblings, entry.name));
  }
  const ids = new Set();
  for (const folder of folders) {
    const pkg = JSON.parse(await readFile(resolve(folder, 'package.json')));
    const id = `${pkg.publisher}.${pkg.name}`;
    if (!pkg.publisher || !pkg.name || ids.has(id)) throw Error('Invalid or duplicate built-in extension.');
    ids.add(id);
    if (pkg.scripts?.build) {
      execFileSync(process.execPath, [process.env.npm_execpath, 'ci', '--ignore-scripts', '--no-audit', '--no-fund'], { cwd: folder, stdio: 'inherit' });
      execFileSync(process.execPath, [process.env.npm_execpath, 'run', 'build'], { cwd: folder, stdio: 'inherit' });
    }
    const destination = resolve(resources, 'extensions', basename(folder));
    await rm(destination, { recursive: true, force: true });
    await mkdir(destination, { recursive: true });
    await cp(folder, destination, { recursive: true, filter: path => !['.git', 'node_modules', 'test', 'tests'].includes(basename(path)) });
    // Reuse the CLI's real modules and their pure JS transport dependency.
    // Native keyring is intentionally not loaded: the panel uses SecretStorage.
    if (folder === panel) {
      await cp(resolve(root, 'cli/src'), resolve(destination, 'cli/src'), { recursive: true });
      await cp(resolve(root, 'cli/package.json'), resolve(destination, 'cli/package.json'));
      await cp(resolve(root, 'cli/node_modules/csv-parse'), resolve(destination, 'cli/node_modules/csv-parse'), { recursive: true });
    }
    // Dependencies that extensions need at runtime belong in their locked build
    // output or node_modules, never downloaded by the desktop after installation.
    try { await cp(resolve(folder, 'node_modules'), resolve(destination, 'node_modules'), { recursive: true }); }
    catch (error) { if (error.code !== 'ENOENT') throw error; }
  }
  return [...ids];
}
if (process.argv[1] === fileURLToPath(import.meta.url)) {
  const root = resolve(import.meta.dirname, '../..');
  console.log(await installExtensions(root, resolve(process.argv[2])));
}
