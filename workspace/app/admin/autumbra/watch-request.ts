import "server-only";
import type { GhostIncident, GhostPanel } from "@/lib/tank";
import { autumbraRequest } from "@/lib/autumbra-request";

async function call<T>(userId: string, path: string, body?: object): Promise<T> {
  const key = process.env.TANK_API_KEY?.trim();
  if (!key) throw new Error("Missing setting: TANK_API_KEY");
  return autumbraRequest(`${process.env.TANK_URL ?? "http://tank:8000"}/v1/ghost/${path}`, {
    method: body ? "POST" : "GET", cache: "no-store",
    headers: {"content-type": "application/json", "x-tank-key": key, "x-tervory-admin": userId},
    ...(body ? {body: JSON.stringify(body)} : {}),
  }, async res => {
    if (!res.ok) throw new Error("Autumbra could not finish the investigation. Check its room and Tank connection.");
    return await res.json() as T;
  });
}
export const ghostPanel = (user: string) => call<GhostPanel>(user, "incidents");
export const ghostLook = (user: string, target: string, signal: string) => call<GhostIncident>(user, "look", {target, signal});
export const ghostResolve = (user: string, id: string, cause: string, fix: string) =>
  call<GhostIncident>(user, `incidents/${encodeURIComponent(id)}/resolve`, {cause, fix});
