import { safe } from './client.mjs';
import { redactSecrets } from './code-tools.mjs';
import { emptyState } from './empty-state.mjs';

const segments = new Intl.Segmenter(undefined, { granularity: 'grapheme' });
const width = value => /[\p{Extended_Pictographic}\u1100-\u115f\u2e80-\ua4cf\uac00-\ud7a3\uf900-\ufaff\uff01-\uff60]/u.test(value) ? 2 : 1;
const clean = value => safe(redactSecrets(String(value)));
export function wrapTerminal(text, columns) {
  const limit = Math.max(1, columns || 80); const lines = [];
  for (const line of String(text).split('\n')) {
    let out = ''; let used = 0;
    for (const { segment } of segments.segment(line.replaceAll('\t','  '))) {
      const size = width(segment);
      if (used && used + size > limit) { lines.push(out); out = ''; used = 0; }
      if (size > limit) continue;
      out += segment; used += size;
    }
    lines.push(out);
  }
  return lines.join('\n');
}

// Only complete words can enter a preview. Incomplete credentials stay buffered;
// assignment lines and private-key blocks use the same final redactor as files.
export function previewText(value) {
  const raw = String(value); const tail = raw.slice(raw.lastIndexOf('\n')+1);
  const held = /(?:aws_secret_access_key|api[_-]?key|secret[_-]?key|client[_-]?secret|password|passwd|access[_-]?token|auth[_-]?token)\b/i.test(tail);
  const prefix = held ? raw.slice(0,raw.lastIndexOf('\n')+1) : raw.slice(0,Math.max(raw.lastIndexOf(' '),raw.lastIndexOf('\n'),raw.lastIndexOf('\t'))+1);
  return clean(prefix);
}

export class TerminalUI {
  constructor({ write, live = write, columns = () => 80, tty = false, env = {}, plain = false }) {
    Object.assign(this,{output:write,live,columns}); this.plain = plain || !tty || Object.hasOwn(env,'NO_COLOR');
    this.active = false; this.steps = []; this.state = null;
  }
  clearPreview() { if (this.active) this.live('\r\x1b[2K'); this.active = false; }
  write(value) {
    this.clearPreview(); const text = clean(value);
    if (this.plain) { this.output(text); return; }
    const lines = text.split('\n');
    this.output(lines.map(line => {
      const colour = line.startsWith('+') ? 32 : line.startsWith('-') ? 31 : line.startsWith('@@') ? 36 : null;
      return wrapTerminal(line,this.columns()).split('\n').map(part => colour ? `\x1b[${colour}m${part}\x1b[0m` : part).join('\n');
    }).join('\n'));
  }
  preview(value) {
    if (this.plain) return; // Screen readers get a single validated answer.
    const text = previewText(value).replace(/\s/g,' ');
    if (!text) return;
    this.clearPreview(); const lines = wrapTerminal(text,Math.max(1,this.columns()-1)).split('\n');
    this.live(lines.at(-1)); this.active = true;
  }
  status(state) {
    this.state = state;
    const money = value => typeof value === 'number' && Number.isFinite(value) ? '$'+Number(value.toFixed(6)) : 'pending';
    this.write(`Model ${state.model} | mode ${state.mode} | cost ${money(state.cost_usd)} | saved vs Auto ${money(state.savings_usd)}\n`);
  }
  tool(step) {
    if (step.phase === 'start') {
      this.steps.push({...step, expanded:this.plain});
      this.write(`Tool ${this.steps.length}: ${step.name}\n`);
      if (this.plain) this.write(JSON.stringify(step.arguments ?? {})+'\n');
    } else {
      const entry = this.steps.at(-1); if (!entry) return;
      Object.assign(entry,step); this.write(`Tool ${this.steps.length}: ${step.failed ? 'needs input' : 'done'}\n`);
      if (!step.failed && entry.name === 'list_files' && Array.isArray(step.result?.files) && !step.result.files.length) this.write(emptyState('files'));
      if (!step.failed && entry.name === 'search' && Array.isArray(step.result?.matches) && !step.result.matches.length) this.write(emptyState('matches'));
      if (this.plain) this.write(JSON.stringify(step.result ?? {})+'\n');
    }
  }
  toggle(value) {
    if (!value && !this.steps.length) { this.write(emptyState('tools')); return; }
    if (!value) { for (const [i,step] of this.steps.entries()) this.write(`Tool ${i+1}: ${step.name} [${step.expanded?'expanded':'collapsed'}]\n`); return; }
    const index = Number(value)-1; const step = this.steps[index];
    if (!Number.isInteger(index) || !step) { this.write('Tool step not available.\n'); return; }
    step.expanded = !step.expanded;
    this.write(`Tool ${index+1}: ${step.expanded?'expanded':'collapsed'}\n`);
    if (step.expanded) this.write(JSON.stringify({arguments:step.arguments,result:step.result})+'\n');
  }
}

export function terminalIO(io, settings) {
  const ui = new TerminalUI({...settings,write:io.write});
  return {...io, write:value=>ui.write(value), preview:value=>ui.preview(value), status:state=>ui.status(state), tool:step=>ui.tool(step), steps:value=>ui.toggle(value),
    reset:()=>{ui.clearPreview();ui.steps=[];ui.state=null;},
    prompt:async label=>{ui.clearPreview();return io.prompt(label);}};
}
