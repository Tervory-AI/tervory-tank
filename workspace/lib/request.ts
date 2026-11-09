/** One attempt only. Reads can be retried explicitly; writes may already have succeeded. */
export const requestBudget = { milliseconds: 30_000, streamMilliseconds: 15 * 60_000 };

export async function fetchWithDeadline(input: RequestInfo | URL, init: RequestInit = {}): Promise<Response> {
  const controller = new AbortController();
  const caller = init.signal ?? (input instanceof Request ? input.signal : undefined);
  const signal = caller ? AbortSignal.any([caller, controller.signal]) : controller.signal;
  let timer: ReturnType<typeof setTimeout>;
  let totalTimer: ReturnType<typeof setTimeout>;
  let rejectTimeout: (reason: Error) => void = () => {};
  const expired = new Promise<never>((_, reject) => { rejectTimeout = reject; });
  const timeout = () => {
    clearTimeout(totalTimer);
    rejectTimeout(new Error("The request took too long. Check its status before trying again."));
    controller.abort();
  };
  const arm = () => { clearTimeout(timer); timer = setTimeout(timeout, requestBudget.milliseconds); (timer as unknown as { unref?: () => void }).unref?.(); };
  arm();
  totalTimer = setTimeout(timeout, requestBudget.streamMilliseconds);
  (totalTimer as unknown as { unref?: () => void }).unref?.();
  const finish = () => { clearTimeout(timer); clearTimeout(totalTimer); };
  try {
    const response = await Promise.race([globalThis.fetch(input, { ...init, signal }), expired]);
    if (!response.body) { finish(); return response; }
    const reader = response.body.getReader();
    const streaming = response.headers.get("content-type")?.includes("text/event-stream");
    const body = new ReadableStream<Uint8Array>({
      async pull(out) {
        try {
          const chunk = await Promise.race([reader.read(), expired]);
          if (chunk.done) { finish(); out.close(); reader.releaseLock(); }
          else { if (streaming) arm(); out.enqueue(chunk.value); }
        } catch {
          finish();
          void reader.cancel().catch(() => {});
          out.error(new Error("The response was interrupted. Check its status before trying again."));
        }
      },
      cancel(reason) {
        finish();
        const cancelled = reader.cancel(reason);
        controller.abort();
        return cancelled;
      },
    });
    const result = new Response(body, { status: response.status, statusText: response.statusText, headers: response.headers });
    Object.defineProperties(result, { url: { value: response.url }, redirected: { value: response.redirected }, type: { value: response.type } });
    return result;
  } catch {
    finish();
    controller.abort();
    throw new Error("The request could not be confirmed. Check its status before trying again.");
  }
}
