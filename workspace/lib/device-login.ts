// CLI device sign-in: the signed-in Workspace user approves or denies a code
// that `tervory login` shows. Server-side only (uses the Tank service keys).
// us-east approvals go to this Workspace's own Tank (TANK_URL + TANK_API_KEY).
// ZA approvals go to the ZA Tank at TANK_URL_ZA (https only) with the dedicated
// TANK_DEVICE_APPROVAL_KEY_ZA, which the ZA Tank accepts for the two approval
// routes only. TANK_API_KEY_ZA (the ZA homes key) is never used here: it cannot
// approve sign-ins. za.tervory.com has no Workspace and no Clerk login of its own.
import { homeRegion, regionTank, type Region } from "@/app/api/zenas/tank";
import { boundedFetch } from "@/lib/tank";

export const USER_CODE = /^[BCDFGHJKLMNPQRSTVWXZ]{4}-[BCDFGHJKLMNPQRSTVWXZ]{4}$/;

export type DeviceIdentity = { tenantId: string; userId: string; tenantAdmin?: boolean };
export type PendingDevice = { user_code: string; device_name: string; region: Region; status: string; created_at?: string;
                              expires_at?: string };
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
  // The user's own Clerk session is checked before this call; a 401 here means this
  // Workspace's service link to the region's Tank is refused, so "sign in again" would mislead.
  401: "Sign-in approval for this region is not available right now. Your Workspace session is fine; contact Tervory support.",
  // The ZA Tank refuses founder accounts on the Boston-held approval key (review of #506, should-fix 1).
  // There is no other place to approve it (za.tervory.com has no Workspace), so say so.
  403: "Founder accounts cannot sign the CLI in to this region; there is no other place to approve it. Nothing was approved. Use tervory login --region us-east instead.",
  404: "This code has expired, was already used, or does not exist. Run tervory login again.",
};

/** The Tank and key that may record an approval for `region`, or null when not connected here. */
export function approvalTank(region: Region): { url: string; key: string } | null {
  if (region === homeRegion()) return regionTank(region);
  const url = ((region === "za" ? process.env.TANK_URL_ZA : process.env.TANK_URL_US) ?? "").trim().replace(/\/+$/, "");
  const key = ((region === "za" ? process.env.TANK_DEVICE_APPROVAL_KEY_ZA : process.env.TANK_DEVICE_APPROVAL_KEY_US) ?? "").trim();
  if (!url || !key) return null;
  let parsed: URL;
  try { parsed = new URL(url); } catch { return null; }
  if (parsed.protocol !== "https:" || parsed.username || parsed.password) return null;
  return { url, key };
}

/** GET shows a pending code; POST records approve or deny for the signed-in user's org. */
export async function deviceApproval(identity: DeviceIdentity, region: Region, code: string,
                                     action?: "approve" | "deny"): Promise<DeviceResult> {
  if (!USER_CODE.test(code)) return { ok: false, status: 404, message: MESSAGES[404] };
  const tank = approvalTank(region);
  if (!tank || !tank.key) return { ok: false, status: 503, message: "Sign-in for this region is not connected here." };
  // Hard deadline over the whole call, body included: undici 6 with redirect:"error"
  // ignores the abort of a stalled body after a GC (lib/tank.ts boundedFetch).
  let answer: { response: Response; body: unknown };
  try {
    answer = await boundedFetch(new URL(`/v1/command/device/approval/${code}`, tank.url), {
      method: action ? "POST" : "GET",
      headers: {
        "content-type": "application/json",
        "x-tank-key": tank.key,
        "x-tervory-user": identity.userId,
        "x-tervory-tenant": identity.tenantId,
        "x-tervory-role": identity.tenantAdmin === true ? "org:admin" : "",
      },
      ...(action ? { body: JSON.stringify({ action }) } : {}),
      cache: "no-store", signal: AbortSignal.timeout(DEVICE_TIMEOUT_MS),
    }, DEVICE_TIMEOUT_MS, async response => {
      if (!response.ok) {
        // Drain rather than cancel: Next's render-time dedupe fetch tees GET bodies and
        // cancel() on one branch never settles (tests/device_login_next_fetch.cjs, step 0).
        await response.arrayBuffer().catch(() => undefined);
        return { response, body: null };
      }
      return { response, body: await response.json().catch(() => null) };
    });
  } catch {
    return { ok: false, status: 502, message: "The sign-in service could not be reached. Try again." };
  }
  const { response, body } = answer;
  if (!response.ok) {
    return { ok: false, status: response.status, message: MESSAGES[response.status] ?? "This request could not be completed. Try again." };
  }
  const device = body as Partial<PendingDevice> | null;
  if (!device || typeof device.device_name !== "string" || device.user_code !== code || typeof device.status !== "string") {
    return { ok: false, status: 502, message: "The sign-in service returned an unexpected answer." };
  }
  return { ok: true, device: { user_code: code, device_name: device.device_name, region: deviceRegion(device.region) ?? region,
    status: device.status, created_at: typeof device.created_at === "string" ? device.created_at : undefined,
    expires_at: typeof device.expires_at === "string" ? device.expires_at : undefined } };
}
