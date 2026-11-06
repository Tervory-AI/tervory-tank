import { fork } from 'node:child_process';

// Native keyring calls are synchronous. Keep them outside the terminal process
// so a locked or unavailable OS service cannot freeze input or cancellation.
// Credentials cross private IPC only, never argv, environment, files or logs.
export function keyringEntry(service, account, { launch = fork, timeoutMs = 10_000 } = {}) {
  const operation = (method, value) => new Promise((resolve, reject) => {
    let child; let timer; let finished = false;
    const finish = (ok, result) => {
      if (finished) return;
      finished = true; clearTimeout(timer); child?.kill('SIGKILL');
      if (ok) resolve(result); else reject(new Error('OS keyring failed or timed out.'));
    };
    try {
      child = launch(new URL('./keyring-process.mjs', import.meta.url), [], {
        execArgv: [], stdio: ['ignore', 'ignore', 'ignore', 'ipc'], windowsHide: true,
        env: Object.fromEntries(['PATH','HOME','USER','LOGNAME','USERPROFILE','APPDATA','LOCALAPPDATA','SystemRoot','DBUS_SESSION_BUS_ADDRESS','XDG_RUNTIME_DIR','DISPLAY','WAYLAND_DISPLAY'].filter(key => process.env[key] !== undefined).map(key => [key, process.env[key]])),
      });
      timer = setTimeout(() => finish(false), timeoutMs);
      child.once('error', () => finish(false));
      child.once('exit', () => finish(false));
      child.once('message', message => finish(message?.ok === true, message?.value));
      child.send({ service, account, method, value }, error => { if (error) finish(false); });
    } catch { finish(false); }
  });
  return { getPassword: () => operation('getPassword'), setPassword: value => operation('setPassword', value), deletePassword: () => operation('deletePassword') };
}
