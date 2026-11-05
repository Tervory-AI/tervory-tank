import "server-only";
import { auth, signinToken } from "./trigger-signin";

export async function signinFetch(input: URL | string | Request, init: RequestInit = {}): Promise<Response> {
  const target = new URL(input instanceof Request ? input.url : input.toString());
  const destinations = [process.env.TANK_URL ?? "http://tank:8000", process.env.TANK_URL_US, process.env.TANK_URL_ZA].filter((value): value is string => !!value);
  const allowed = destinations.some(value => {
    try { return new URL(value).origin === target.origin; } catch { return false; }
  });
  const headers = new Headers(init.headers ?? (input instanceof Request ? input.headers : undefined));
  if (allowed && headers.has("x-tank-key") && ["x-tervory-user", "x-tervory-admin", "x-tervory-role"].some(name => headers.has(name))) {
    const identity = await auth();
    if (!identity.userId || !identity.orgId) throw new Error("Trigger sign-in required");
    headers.set("x-trigger-signin-token", await signinToken());
    headers.set("x-trigger-signin-org", identity.orgId);
  }
  return globalThis.fetch(input, { ...init, headers });
}
