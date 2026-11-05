import { basename, extname } from 'node:path';
import { LIMITS, redactSecrets } from './code-tools.mjs';
const fail = () => new Error('Code attachment refused.');
const IMAGE_BYTES = 5 * 1024 * 1024; // Existing Tank binary attachment bound.
export async function attachmentsFrom(text, local, tank, thread, io) {
  const matches = [...text.matchAll(/(?:^|\s)@(?:"([^"\n]+)"|'([^'\n]+)'|([^\s]+))/g)];
  if (matches.length > 10) throw fail(); // Existing Command attachments per turn.
  const prepared = [];
  for (const match of matches) {
    const path = match[1] ?? match[2] ?? match[3];
    const visible = await local.git(['ls-files', '-z', '--cached', '--others', '--exclude-standard', '--', path]);
    const ignored = await local.git(['ls-files', '-z', '--cached', '--ignored', '--exclude-standard', '--', path]);
    if (visible.code || ignored.code || visible.truncated || ignored.truncated || !visible.output || ignored.output) throw fail();
    if (/^\.(png|jpe?g|gif|webp)$/i.test(extname(path))) {
      const value = await local.raw(path, { binary: true, maxBytes: IMAGE_BYTES });
      if (!value) throw fail();
      const bytes = value.bytes;
      const valid = bytes.subarray(0,8).equals(Buffer.from([137,80,78,71,13,10,26,10]))
        || (bytes[0] === 255 && bytes[1] === 216 && bytes[2] === 255)
        || ['GIF87a','GIF89a'].includes(bytes.subarray(0,6).toString())
        || (bytes.subarray(0,4).toString() === 'RIFF' && bytes.subarray(8,12).toString() === 'WEBP');
      if (!valid || redactSecrets(bytes.toString('latin1')) !== bytes.toString('latin1')) throw fail();
      prepared.push({ name: basename(path), bytes });
    } else {
      const file = await local.read(path);
      if (!file.exists || file.size > LIMITS.fileBytes) throw fail();
      prepared.push({ name: basename(path), text: file.text });
    }
  }
  const attachments = [];
  // Validate every local attachment before uploading anything.
  for (const file of prepared) {
    if (file.bytes) {
      const result = await tank.json('/v1/command/code-attachments', { thread_id: thread, name: file.name, base64: file.bytes.toString('base64') });
      if (typeof result.attachment_id !== 'string' || result.model_readable !== false) throw fail();
      attachments.push({ attachment_id: result.attachment_id });
      io.write(`Image attached (stored only): ${file.name}\n`);
    } else attachments.push(file);
  }
  return attachments;
}
