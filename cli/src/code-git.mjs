import { execFile } from 'node:child_process';
import { promisify } from 'node:util';
import { LIMITS, redactSecrets } from './code-tools.mjs';
import { missingSetting } from './configuration.mjs';
import { emptyState } from './empty-state.mjs';
const execute = promisify(execFile);
const refuse = () => new Error('Code Git refused.');
export async function gitProcess(command, args, local, signal) {
  try { return (await execute(command, args, { cwd: local.gitWorkTree, shell: false, timeout: LIMITS.commandMs, maxBuffer: LIMITS.outputBytes, signal,
    env: { ...Object.fromEntries(['PATH','HOME','USERPROFILE','APPDATA','LOCALAPPDATA','SystemRoot','SSH_AUTH_SOCK','HTTPS_PROXY','HTTP_PROXY','NO_PROXY','SSL_CERT_FILE','NODE_EXTRA_CA_CERTS'].filter(k => process.env[k] !== undefined).map(k => [k, process.env[k]])), GH_PROMPT_DISABLED: '1', GIT_TERMINAL_PROMPT: '0' } })).stdout; }
  catch { throw refuse(); }
}

export async function gitSlash(name, value, local, io, mode, { process = gitProcess } = {}) {
  const clean = text => redactSecrets(String(text));
  const approve = async (label, detail) => { io.write(clean(detail) + '\n'); return io.interactive === true && (await io.prompt(label))?.trim().toLowerCase() === 'y'; };
  if (mode === 'plan') throw refuse();
  const checked = async args => { const result = await local.git(args); if (result.code || result.truncated) throw refuse(); return result.output.trim(); };
  if (name === '/commit') {
    if (value) throw refuse();
    const names = await checked(['diff', '--cached', '--name-only', '-z']);
    if (!names) { io.write('No staged changes.\n' + emptyState('staged')); return; }
    const paths = names.split('\0').filter(Boolean);
    for (const path of paths) await local.path(path, { missing: true });
    const diff = await checked(['diff', '--cached', '--no-ext-diff', '--no-textconv']);
    if (redactSecrets(diff) !== diff || /\[redacted\]|GIT binary patch|Binary files /.test(diff)) throw refuse();
    const message = `Update ${paths.join(', ')}`;
    if (Buffer.byteLength(message) > LIMITS.fileBytes) throw refuse();
    const index = await checked(['ls-files', '--stage', '-z']);
    if (!await approve('Commit [y/N] ', `${diff}\nCommit message: ${message}`)) return;
    if (await checked(['ls-files', '--stage', '-z']) !== index) throw refuse();
    // No add, push, hook, shell interpolation or model-generated Git options.
    await process('git', ['-c','core.hooksPath=/dev/null','-c','commit.gpgSign=false','commit','-m',message], local, io.signal);
    io.write('Committed.\n'); return;
  }
  if (name === '/branch') {
    if (!value) { const branches = await checked(['branch','--list','--no-color']); io.write(branches ? clean(branches) + '\n' : emptyState('branches')); return; }
    if (!/^[A-Za-z0-9][A-Za-z0-9._/-]*$/.test(value) || value.includes('..') || value.includes('@{')) throw refuse();
    await checked(['check-ref-format','--branch',value]);
    const exists = await local.git(['show-ref','--verify','--quiet',`refs/heads/${value}`]);
    if (!await approve('Switch branch [y/N] ', value)) return;
    await checked(['switch', ...(exists.code === 0 ? [] : ['-c']), value]); return;
  }
  if (name !== '/pr' || value) throw refuse();
  try { await process('gh',['auth','status'],local,io.signal); }
  catch { throw missingSetting('gh authentication', 'Install gh and run gh auth login before using /pr. Nothing was pushed.'); }
  const branch = await checked(['symbolic-ref','--short','HEAD']);
  if (['main','master'].includes(branch) || !/^[A-Za-z0-9][A-Za-z0-9._/-]*$/.test(branch)) throw refuse();
  const remote = await checked(['remote','get-url','--push','--all','origin']);
  if (!/^(?:https:\/\/github\.com\/|git@github\.com:)[A-Za-z0-9_.-]+\/[A-Za-z0-9_.-]+(?:\.git)?$/.test(remote)) throw refuse();
  if ((await checked(['status','--porcelain']))) throw refuse();
  const head = await checked(['rev-parse','HEAD']);
  if (!await approve('Push branch [y/N] ', `git push ${remote} HEAD:refs/heads/${branch}`)) return;
  if (await checked(['rev-parse','HEAD']) !== head || await checked(['symbolic-ref','--short','HEAD']) !== branch || await checked(['remote','get-url','--push','--all','origin']) !== remote) throw refuse();
  await process('git',['-c','core.hooksPath=/dev/null','-c','push.followTags=false','push','--no-force','--set-upstream',remote,`HEAD:refs/heads/${branch}`],local,io.signal);
  if (!await approve('Create pull request [y/N] ', 'gh pr create --fill')) return;
  io.write(clean(await process('gh',['pr','create','--fill'],local,io.signal)) + '\n');
}
