// Same deadline pattern as lib/tank's boundedFetch, without server credentials.
// One attempt only: an uncertain write is resolved through its existing receipt.
export async function within<T>(work: () => Promise<T>, timeout = 35000, abort?: () => void): Promise<T> {
  let timer: ReturnType<typeof setTimeout> | undefined;
  const deadline = new Promise<never>((_, reject) => {
    timer = setTimeout(() => { abort?.(); reject(new Error("Rig did not answer. Try again.")); }, timeout);
  });
  try { return await Promise.race([work(), deadline]); }
  finally { clearTimeout(timer); }
}

export async function request<T>(url: string, init: RequestInit, read: (response: Response) => Promise<T>, timeout = 35000): Promise<T> {
  const controller = new AbortController();
  return within(() => fetch(url, { ...init, signal: controller.signal, redirect: "error" }).then(read), timeout, () => controller.abort());
}
