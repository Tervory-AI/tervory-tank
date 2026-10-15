/** Server-side calls to this region's Tank. The key never reaches the browser. */

const TANK_URL = process.env.TANK_URL ?? "http://tank:8000";
const TANK_API_KEY = process.env.TANK_API_KEY ?? "";

export function homeRegion(): "us-east" | "za" {
  return process.env.TANK_REGION === "za" ? "za" : "us-east";
}

export async function zenas(path: string, init: RequestInit = {}): Promise<Response> {
  return fetch(`${TANK_URL}/v1/zenas/${path}`, {
    ...init,
    headers: {
      "content-type": "application/json",
      "x-tank-key": TANK_API_KEY,
      ...(init.headers ?? {}),
    },
    cache: "no-store",
  });
}
