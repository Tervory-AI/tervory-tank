// One attempt only. Writes are never replayed automatically after an uncertain response.
export async function withDeadline<T>(work: (signal: AbortSignal) => Promise<T>, parent?: AbortSignal | null,
                                      milliseconds = 30_000): Promise<T> {
  const controller = new AbortController();
  let timer: ReturnType<typeof setTimeout> | undefined;
  let cancel: () => void = () => {};
  const stopped = new Promise<never>((_, reject) => {
    cancel = () => {
      controller.abort();
      reject(new Error("Radix could not complete that request."));
    };
    timer = setTimeout(cancel, milliseconds);
    parent?.addEventListener("abort", cancel, { once: true });
    if (parent?.aborted) cancel();
  });
  try {
    return await Promise.race([stopped, Promise.resolve().then(() => {
      if (controller.signal.aborted) throw new Error("Radix could not complete that request.");
      return work(controller.signal);
    })]);
  } finally {
    clearTimeout(timer);
    parent?.removeEventListener("abort", cancel);
    controller.abort();
  }
}

export function radixJSON(url: string, init: RequestInit = {}) {
  return withDeadline(async signal => {
    try {
      const response = await fetch(url, { ...init, signal, cache: "no-store", redirect: "error" });
      if (!response.ok) throw new Error();
      return await response.json();
    } catch { throw new Error("Radix could not complete that request."); }
  }, init.signal);
}
