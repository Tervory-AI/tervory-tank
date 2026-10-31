// CLI device sign-in: the signed-in Workspace user approves or denies a code
// that `tervory login` shows. Server-side only (uses the Tank service keys).
// us-east approvals go to this Workspace's own Tank; ZA approvals go to the ZA
// Tank through the existing regionTank pattern (TANK_URL_ZA + TANK_API_KEY_ZA,
// https only). za.tervory.com has no Workspace and no Clerk login of its own.
import { regionTank, type Region } from "@/app/api/zenas/tank";

export const USER_CODE = /^[BCDFGHJKLMNPQRSTVWXZ]{4}-[BCDFGHJKLMNPQRSTVWXZ]{4}$/;

export type DeviceIdentity = { tenantId: string; userId: string; tenantAdmin?: boolean };
export type PendingDevice = { user_code: string; device_name: string; region: Region; status: string; expires_at?: string };
export type DeviceResult = { ok: true; device: PendingDevice } | { ok: false; status: number; message: string };

export function deviceRegion(value: unknown): Region | null {
  return value === "us-east" || value === "za" ? value : null;
}

export function deviceCode(value: unknown): string | null {
  const text = typeof value === "string" ? value.trim().toUpperCase() : "";
  return USER_CODE.test(text) ? text : null;
}

// Tank answers these in milliseconds. If it accepts the connection and never answers,
// the /cli/device page render and the Approve action must not wait forever.
export const DEVICE_TIMEOUT_MS = 10_000;

const MESSAGES: Record<number, string> = {
  401: "This sign-in could not be verified. Sign in again and retry.",
  404: "This code has expired, was already used, or does not exist. Run tervory login again.",
};

/** GET shows a pending code; POST records approve or deny for the signed-in user's org. */
export async function deviceApproval(identity: DeviceIdentity, region: Region, code: string,
                                     action?: "approve" | "deny"): Promise<DeviceResult> {
  if (!USER_CODE.test(code)) return { ok: false, status: 404, message: MESSAGES[404] };
  const tank = regionTank(region);
  if (!tank || !tank.key) return { ok: false, status: 503, message: "Sign-in for this region is not connected here." };
  let response: Response;
  try {
    response = await fetch(new URL(`/v1/command/device/approval/${code}`, tank.url), {
      method: action ? "POST" : "GET",
      headers: {
        "content-type": "application/json",
        "x-tank-key": tank.key,
        "x-tervory-user": identity.userId,
        "x-tervory-tenant": identity.tenantId,
        "x-tervory-role": identity.tenantAdmin === true ? "org:admin" : "",
      },
      ...(action ? { body: JSON.stringify({ action }) } : {}),
      cache: "no-store", redirect: "error", signal: AbortSignal.timeout(DEVICE_TIMEOUT_MS),
    });
  } catch {
    return { ok: false, status: 502, message: "The sign-in service could not be reached. Try again." };
  }
  if (!response.ok) {
    // Drain rather than cancel: Next's render-time dedupe fetch tees GET bodies and
    // cancel() on one branch never settles (tests/device_login_next_fetch.cjs, step 0).
    await response.arrayBuffer().catch(() => undefined);
    return { ok: false, status: response.status, message: MESSAGES[response.status] ?? "This request could not be completed. Try again." };
  }
  // A body that never finishes is cut off by the same timeout signal.
  const body: unknown = await response.json().catch(() => null);
  const device = body as Partial<PendingDevice> | null;
  if (!device || typeof device.device_name !== "string" || device.user_code !== code || typeof device.status !== "string") {
    return { ok: false, status: 502, message: "The sign-in service returned an unexpected answer." };
  }
  return { ok: true, device: { user_code: code, device_name: device.device_name, region: deviceRegion(device.region) ?? region,
    status: device.status, expires_at: typeof device.expires_at === "string" ? device.expires_at : undefined } };
}
