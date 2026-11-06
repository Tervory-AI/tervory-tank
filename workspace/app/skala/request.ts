// Bounded reads include the response body. Mutations are never retried here.
export const SKALA_CLIENT_TIMEOUT_MS = 30_000;
export async function skalaFetch(url: string, init: RequestInit = {}, timeoutMs = SKALA_CLIENT_TIMEOUT_MS): Promise<Response> {
  const reads = (init.method ?? 'GET').toUpperCase() === 'GET';
  for (let attempt = 0; ; attempt++) {
    const controller = new AbortController();
    let timer: ReturnType<typeof setTimeout>;
    const signal = init.signal ? AbortSignal.any([init.signal, controller.signal]) : controller.signal;
    const failure = new Promise<never>((_, reject) => {
      timer = setTimeout(() => { controller.abort(); reject(new Error('The library could not be reached. Try again in a moment.')); }, timeoutMs);
    });
    const work = (async () => {
      const response = await fetch(url, {...init, signal, redirect: 'error', cache: 'no-store'});
      const body = await response.arrayBuffer();
      return new Response(body, {status: response.status, headers: response.headers});
    })();
    try {
      const response = await Promise.race([work, failure]);
      if (reads && attempt === 0 && [502, 503, 504].includes(response.status)) continue;
      return response;
    } catch (error) {
      if (!reads || attempt > 0 || signal.aborted) throw error;
    } finally { clearTimeout(timer!); }
  }
}
