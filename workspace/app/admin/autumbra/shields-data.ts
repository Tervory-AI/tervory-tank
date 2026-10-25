import "server-only";

import {
  applyFixtureTap,
  fixtureBoard,
  isFixtureShield,
  type Shield,
  type ShieldBoard,
  type ShieldTile,
} from "./shields-fixtures";

export type { Shield, ShieldBoard, ShieldReceipt, ShieldTile } from "./shields-fixtures";
export { FIXTURE_BOARD, PRACTICE_SHIELD_ID, fixtureBoard, isFixtureShield } from "./shields-fixtures";

// Autumbra Enforce shields: founder-only reads and taps through Tank (`/v1/ghost/shields/*`).
// Server-side only (uses TANK_API_KEY). When Tank is down, Practice fixtures keep the board usable.
const TANK_URL = process.env.TANK_URL ?? "http://tank:8000";
const TANK_API_KEY = process.env.TANK_API_KEY ?? "";

async function call<T>(path: string, userId: string, method: "GET" | "POST"): Promise<T> {
  const res = await fetch(`${TANK_URL}/v1/ghost/shields/${path}`, {
    method, cache: "no-store",
    headers: { "content-type": "application/json", "x-tank-key": TANK_API_KEY, "x-tervory-admin": userId },
  });
  if (!res.ok) throw new Error(`Autumbra shields ${res.status}`);
  return (await res.json()) as T;
}

/** Never rejects: live Tank board when available, else Practice fixtures (dry_run). */
export async function shieldBoard(userId: string): Promise<ShieldBoard> {
  try {
    const [tile, list] = await Promise.all([
      call<ShieldTile>("tile", userId, "GET"),
      call<{ shields: Shield[] }>("list", userId, "GET"),
    ]);
    return { tile, shields: list.shields };
  } catch {
    return fixtureBoard();
  }
}

export async function shieldTap(userId: string, id: string, tap: "raise" | "undo"): Promise<Shield> {
  if (!/^[0-9a-f-]{36}$/.test(id)) throw new Error("Invalid shield");
  if (isFixtureShield(id)) {
    return applyFixtureTap(id, tap);
  }
  try {
    return await call<Shield>(`${id}/${tap}`, userId, "POST");
  } catch {
    // Tank failed after a fixture board was shown, or id is known to fixtures.
    if (isFixtureShield(id)) return applyFixtureTap(id, tap);
    throw new Error("Autumbra shields tap unavailable");
  }
}
