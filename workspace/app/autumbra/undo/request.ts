// Browser-only counterpart to Workspace's existing 10-second corridor deadline.
// One attempt, including body read; cancelling a view also cancels its request.
export const UNDO_REQUEST = {timeoutMs: 10000};
export async function readUndoResponse(url: string, init: RequestInit = {}) {
  if (init.signal?.aborted) throw new Error("Could not reach Autumbra. Try again in a moment.");
  const controller = new AbortController();
  let timer: ReturnType<typeof setTimeout> | undefined;
  let stop: (() => void) | undefined;
  const work = (async () => {
    const response = await fetch(url, {...init, signal: controller.signal, redirect: "error"});
    const data = await response.json();
    return {response, data};
  })();
  const deadline = new Promise<never>((_, reject) => {
    stop = () => { controller.abort(); reject(new Error("Could not reach Autumbra. Try again in a moment.")); };
    timer = setTimeout(stop, UNDO_REQUEST.timeoutMs);
    init.signal?.addEventListener("abort", stop, {once: true});
    if (init.signal?.aborted) stop();
  });
  try { return await Promise.race([work, deadline]); }
  finally {
    clearTimeout(timer);
    if (stop) init.signal?.removeEventListener("abort", stop);
  }
}
