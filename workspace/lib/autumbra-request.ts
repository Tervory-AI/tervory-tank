import { boundedFetch, DEVICE_PROXY_TIMEOUT_MS } from "./tank";

// Reuse the existing Workspace deadline, including the response body. One
// attempt per request: writes are never automatically replayed after a timeout.
export const AUTUMBRA_REQUEST = { timeoutMs: DEVICE_PROXY_TIMEOUT_MS, maxAttempts: 1 };

export function autumbraRequest<T>(url: URL | string, init: RequestInit, read: (response: Response) => Promise<T>): Promise<T> {
  return boundedFetch(url, init, AUTUMBRA_REQUEST.timeoutMs, read);
}
