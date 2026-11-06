import { open } from 'node:fs/promises';
import { constants } from 'node:fs';
import { basename, extname } from 'node:path';
import { parse } from 'csv-parse/sync';
import { redactSecrets, secretPath } from './code-tools.mjs';

const INPUT_BYTES = 2_000_000; // Existing run --file limit.
const identifier = /^[a-z][a-z0-9_.-]*$/i;

async function csvFile(path) {
  if (secretPath(path)) throw new Error('Invalid file: secret paths are refused.');
  let handle;
  try {
    handle = await open(path, constants.O_RDONLY | (constants.O_NOFOLLOW ?? 0) | (constants.O_NONBLOCK ?? 0));
    const stat = await handle.stat();
    if (!stat.isFile() || stat.nlink !== 1 || stat.size > INPUT_BYTES) throw new Error();
    const buffer = Buffer.alloc(INPUT_BYTES + 1);
    let size = 0;
    while (size < buffer.length) {
      const { bytesRead } = await handle.read(buffer, size, buffer.length - size, size);
      if (!bytesRead) break;
      size += bytesRead;
    }
    if (size > INPUT_BYTES) throw new Error();
    const text = new TextDecoder('utf8', { fatal: true }).decode(buffer.subarray(0, size));
    if (text.includes('\0') || redactSecrets(text) !== text) throw new Error();
    return parse(text, { columns: true, bom: true, skip_empty_lines: true, max_record_size: 200_000 });
  } catch { throw new Error('Invalid CSV file: check its path, size and contents.'); }
  finally { await handle?.close(); }
}

// Both live and dry runs use exactly this input preparation. Dry runs stop here:
// only Tank can decide permission, task-schema validity and remote readiness.
export async function prepareRun(parts, flags) {
  if (parts.length !== 2 || !parts.every(part => identifier.test(part))) throw new Error('Run requires an agent and task.');
  if (Object.keys(flags).some(key => !['thread', 'file', 'args', 'dry-run', 'output'].includes(key))) throw new Error('Invalid command option.');
  let args;
  try { args = flags.args === undefined ? {} : JSON.parse(flags.args); }
  catch { throw new Error('Invalid task arguments.'); }
  if (!args || typeof args !== 'object' || Array.isArray(args)) throw new Error('Invalid task arguments.');
  const tool = parts.join('.');
  if (flags.file) {
    if (tool !== 'base.batch') throw new Error('Invalid file option for this tool; use --args with its Tank schema.');
    args.records = await csvFile(flags.file);
    args.batch ??= basename(flags.file, extname(flags.file));
  }
  const text = JSON.stringify(args);
  if (redactSecrets(text) !== text) throw new Error('Invalid task arguments: secrets must stay in the OS keyring.');
  return { tool, arguments: args };
}

export function dryRunResult(request) {
  return {
    status: 'dry_run', tool: request.tool,
    records: Array.isArray(request.arguments.records) ? request.arguments.records.length : null,
    argument_names: Object.keys(request.arguments).sort(),
    authorization: 'not_checked', task_schema: 'not_checked',
    network_calls: 0, tool_calls: 0, cost_usd: 0,
  };
}

export function dryRunText(result) {
  return `Dry run: local input valid.\nTool ${result.tool} | records ${result.records ?? '—'} | cost 0\n`
    + 'Tank authorization and task schema: not checked.\n'
    + 'No request was sent; no job was started.\n'
    + 'First action: remove --dry-run to request Tank approval.\n';
}
