/** Server-side calls to this region's Tank. The key never reaches the browser. */

const TANK_URL = process.env.TANK_URL ?? "http://tank:8000";
const TANK_API_KEY = process.env.TANK_API_KEY ?? "";

export function homeRegion(): "us-east" | "za" {
  return process.env.TANK_REGION === "za" ? "za" : "us-east";
}

/** Every Zenas call names this server's home. A blank value is filled in, never dropped. */
function withHome(path: string, init: RequestInit): { path: string; init: RequestInit } {
  const home = homeRegion();
  const split = path.indexOf("?");
  const pathname = split === -1 ? path : path.slice(0, split);
  const params = new URLSearchParams(split === -1 ? "" : path.slice(split + 1));
  if (!params.get("home_region")) params.set("home_region", home);
  let body = init.body;
  if (typeof body === "string" && body) {
    try {
      const parsed = JSON.parse(body) as unknown;
      if (parsed && typeof parsed === "object" && !Array.isArray(parsed)) {
        const record = parsed as Record<string, unknown>;
        if (typeof record.home_region !== "string" || !record.home_region.trim()) {
          record.home_region = home;
          body = JSON.stringify(record);
        }
      }
    } catch {
      // The query string still carries the home.
    }
  }
  const query = params.toString();
  return { path: query ? `${pathname}?${query}` : pathname, init: { ...init, body } };
}

export async function zenas(path: string, init: RequestInit = {}): Promise<Response> {
  const call = withHome(path, init);
  return fetch(`${TANK_URL}/v1/zenas/${call.path}`, {
    ...call.init,
    headers: {
      "content-type": "application/json",
      "x-tank-key": TANK_API_KEY,
      ...(call.init.headers ?? {}),
    },
    cache: "no-store",
  });
}
