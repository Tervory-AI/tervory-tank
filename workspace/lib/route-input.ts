export class InputError extends Error {
  constructor(message: string, public status = 400) { super(message); }
}
export async function bodyBytes(request: Request, limit = 256 * 1024): Promise<Uint8Array> {
  if (Number(request.headers.get("content-length")) > limit) throw new InputError("This request is too large.", 413);
  const reader = request.body?.getReader();
  if (!reader) throw new InputError("A request body is required.");
  let size = 0;
  const chunks: Uint8Array[] = [];
  let timer: ReturnType<typeof setTimeout>;
  const timeout = new Promise<never>((_, reject) => { timer = setTimeout(() => { void reader.cancel().catch(() => {}); reject(new InputError("The upload took too long.", 408)); }, 15_000); });
  try {
    while (true) {
      const chunk = await Promise.race([reader.read(), timeout]);
      if (chunk.done) break;
      size += chunk.value.byteLength;
      if (size > limit) throw new InputError("This request is too large.", 413);
      chunks.push(chunk.value);
    }
    const bytes = new Uint8Array(size); let at = 0;
    for (const chunk of chunks) { bytes.set(chunk, at); at += chunk.length; }
    return bytes;
  } catch (error) {
    void reader.cancel().catch(() => {});
    if (error instanceof InputError) throw error;
    throw new InputError("The request could not be read. Check it and try again.");
  } finally { clearTimeout(timer!); }
}
export async function jsonInput(request: Request, limit = 256 * 1024): Promise<Record<string, unknown>> {
  if (!request.headers.get("content-type")?.includes("application/json")) throw new InputError("Send a JSON request.");
  const bytes = await bodyBytes(request, limit);
  try {
    const value: unknown = JSON.parse(new TextDecoder().decode(bytes));
    if (!value || typeof value !== "object" || Array.isArray(value)) throw Error();
    return value as Record<string, unknown>;
  } catch { throw new InputError("Send a valid JSON object."); }
}
export function routeFailure(error: unknown): Response {
  if (error instanceof InputError) return Response.json({ error: error.message, retry_safe: error.status !== 409 }, { status: error.status });
  if (error instanceof Error && /sign.in required|not signed in/i.test(error.message)) return Response.json({ error: "Please sign in to continue." }, { status: 401 });
  return Response.json({ error: "Your request could not be confirmed. Check its status before trying again." }, { status: 502 });
}
