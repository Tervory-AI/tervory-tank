/** Server-side calls to Tank. The key never reaches the browser. */

const TANK_URL = process.env.TANK_URL ?? "http://tank:8000";
const TANK_API_KEY = process.env.TANK_API_KEY ?? "";

export type Region = "us-east" | "za";

export function homeRegion(): Region {
  return process.env.TANK_REGION === "za" ? "za" : "us-east";
}

/** Every Zenas call names this server's home. A blank value is filled in, never dropped. */
function withHome(path: string, init: RequestInit, home: Region = homeRegion(), force = false): { path: string; init: RequestInit } {
  const split = path.indexOf("?");
  const pathname = split === -1 ? path : path.slice(0, split);
  const params = new URLSearchParams(split === -1 ? "" : path.slice(split + 1));
  if (force || !params.get("home_region")) params.set("home_region", home);
  let body = init.body;
  if (typeof body === "string" && body) {
    try {
      const parsed = JSON.parse(body) as unknown;
      if (parsed && typeof parsed === "object" && !Array.isArray(parsed)) {
        const record = parsed as Record<string, unknown>;
        if (force || typeof record.home_region !== "string" || !record.home_region.trim()) {
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

/**
 * The Tank that owns a region. This server's own Tank for its own region.
 * The other region's Tank only through its public HTTPS address and its own
 * Workspace key (TANK_URL_ZA + TANK_API_KEY_ZA, or TANK_URL_US + TANK_API_KEY_US).
 * Null when that region is not connected here.
 */
export function regionTank(region: Region): { url: string; key: string } | null {
  if (region === homeRegion()) return { url: TANK_URL, key: TANK_API_KEY };
  const url = ((region === "za" ? process.env.TANK_URL_ZA : process.env.TANK_URL_US) ?? "").trim().replace(/\/+$/, "");
  const key = ((region === "za" ? process.env.TANK_API_KEY_ZA : process.env.TANK_API_KEY_US) ?? "").trim();
  if (!url || !key) return null;
  let parsed: URL;
  try {
    parsed = new URL(url);
  } catch {
    return null;
  }
  if (parsed.protocol !== "https:" || parsed.username || parsed.password) return null;
  return { url, key };
}

/**
 * Call /v1/zenas/* on the Tank that owns `region`. The home on the call is
 * always that region, so the other Tank's own region check passes only for
 * its own tenants. Used for founder-only calls that carry no personal data
 * (a tenant id and a region code). Matter data never goes through here.
 */
export async function zenasIn(region: Region, path: string, init: RequestInit = {}): Promise<Response | null> {
  const tank = regionTank(region);
  if (!tank) return null;
  const call = withHome(path, init, region, true);
  return fetch(`${tank.url}/v1/zenas/${call.path}`, {
    ...call.init,
    headers: {
      "content-type": "application/json",
      "x-tank-key": tank.key,
      ...(call.init.headers ?? {}),
    },
    cache: "no-store",
  });
}
