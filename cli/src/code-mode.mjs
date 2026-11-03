import { CodeFolder, redactSecrets } from './code-tools.mjs';

export async function codeSession(tank, folder, model, io, formatReceipt, sanitize) {
  if (io.interactive !== true) throw new Error('Code mode requires an interactive terminal.');
  const local = await CodeFolder.create(folder);
  const thread = (await tank.json('/v1/command/threads', {})).thread_id;
  io.write(`Thread ${sanitize(thread)}\n`);
  while (true) {
    if (io.signal?.aborted) throw new Error('Command cancelled; no action was retried.');
    const input = await io.prompt('> ');
    if (input === null || input.trim() === '/exit') return;
    if (!input.trim()) continue;
    const text = redactSecrets(input);
    let results = [];
    for (let round = 0; ; round++) {
      if (io.signal?.aborted) throw new Error('Command cancelled; no action was retried.');
      if (round === 32) throw new Error('Code tool limit reached; nothing was retried.');
      // Existing token-chosen origin and the existing bounded JSON transport.
      // No request is retried, including an interrupted/charged code turn.
      const plan = await tank.json(`/v1/command/threads/${encodeURIComponent(thread)}/code-turn`, {
        text, model, tool_results: results,
      });
      if (typeof plan.answer !== 'string' || !Array.isArray(plan.requests) || plan.requests.length > 6) throw new Error('Tank sent an invalid answer.');
      if (plan.answer) io.write(sanitize(redactSecrets(plan.answer)) + '\n');
      io.write(formatReceipt(plan.receipt ?? {}).map(sanitize).join('\n') + '\n');
      if (!plan.requests.length) break;
      for (const request of plan.requests) {
        if (io.signal?.aborted) throw new Error('Command cancelled; no action was retried.');
        let result;
        try { result = await local.tool(request, io); }
        catch { result = { error: 'Code tool refused.' }; }
        // The tool's output has already been redacted line-by-line. Redact the
        // envelope too, so model-supplied argument strings cannot smuggle secrets.
        const output = redactSecrets(JSON.stringify({ arguments: request.arguments, result }));
        while (results.length && (results.length >= 6 || results.reduce((n, item) => n + Buffer.byteLength(item.output), 0) + Buffer.byteLength(output) > 1_500_000)) results.shift();
        if (Buffer.byteLength(output) > 400000) {
          results.push({ name: request.name, output: JSON.stringify({ error: 'Code tool result exceeds the limit.' }) });
        } else results.push({ name: request.name, output });
      }
    }
  }
}
