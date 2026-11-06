/** Bounded JSON transport. Mutations are never replayed automatically. */
export const REQUEST_TIMEOUT_MS = 120_000;
const ERROR = "Zenas could not be reached. Check your connection and try again.";
const pending = new Map<string, string>();

export async function zenasFetch(input: string, init: RequestInit = {}): Promise<Response> {
  const method = (init.method ?? "GET").toUpperCase();
  const headers = new Headers(init.headers);
  const signature = input + "\0" + String(init.body ?? "");
  if (method === "POST" && !headers.has("idempotency-key")) {
    if (!pending.has(signature)) pending.set(signature, crypto.randomUUID());
    headers.set("idempotency-key", pending.get(signature)!);
  }
  for (let attempt = 0; attempt < (method === "GET" ? 2 : 1); attempt++) {
    const controller = new AbortController();
    const abort = () => controller.abort();
    init.signal?.addEventListener("abort", abort, { once: true });
    if (init.signal?.aborted) abort();
    const timer = setTimeout(abort, REQUEST_TIMEOUT_MS);
    try {
      const response = await fetch(input, { ...init, headers, signal: controller.signal, redirect: "error" });
      const text = await response.text(); // The deadline includes the response body.
      const value = JSON.parse(text);
      if (!value || typeof value !== "object") throw Error("invalid_response");
      if (method === "GET" && [502, 503, 504].includes(response.status) && attempt === 0) continue;
      if (method === "POST" && response.status < 500 && response.status !== 409) pending.delete(signature);
      return new Response(text, { status: response.status, headers: response.headers });
    } catch {
      if (attempt === (method === "GET" ? 1 : 0) || init.signal?.aborted) break;
    } finally {
      clearTimeout(timer);
      init.signal?.removeEventListener("abort", abort);
    }
  }
  return Response.json({ kind: "error", message: ERROR, error: ERROR, detail: ERROR }, { status: 503 });
}
