/** Server-side calls to Tank. The key never reaches the browser. */

const TANK_URL = process.env.TANK_URL ?? "http://tank:8000";
const TANK_API_KEY = process.env.TANK_API_KEY ?? "";

export type Region = "us-east" | "za";

export function homeRegion(): Region {
  // The founder stopped ZA. This Workspace serves US work only.
  return "us-east";
}

/** Every Zenas call names this server's home. A blank value is filled in, never dropped. */
function withHome(path: string, init: RequestInit, home: Region = homeRegion(), force = false): { path: string; init: RequestInit } {
  const split = path.indexOf("?");
  const pathname = split === -1 ? path : path.slice(0, split);
  const params = new URLSearchParams(split === -1 ? "" : path.slice(split + 1));
  if (params.getAll("home_region").some(value => value && value !== "us-east")) {
    throw new Error("needs the United States region");
  }
  if (force || !params.get("home_region")) params.set("home_region", home);
  let body = init.body;
  if (typeof body === "string" && body) {
    try {
      const parsed = JSON.parse(body) as unknown;
      if (parsed && typeof parsed === "object" && !Array.isArray(parsed)) {
        const record = parsed as Record<string, unknown>;
        if (record.home_region && record.home_region !== "us-east") {
          throw new Error("needs the United States region");
        }
        if (force || typeof record.home_region !== "string" || !record.home_region.trim()) {
          record.home_region = home;
          body = JSON.stringify(record);
        }
      }
    } catch (error) {
      if (!(error instanceof SyntaxError)) throw error;
      // Invalid JSON is rejected by Tank; the query still carries the home.
    }
  }
  const query = params.toString();
  return { path: query ? `${pathname}?${query}` : pathname, init: { ...init, body } };
}

export async function zenas(path: string, init: RequestInit = {}): Promise<Response> {
  const tank = regionTank("us-east");
  if (!tank) throw new Error("needs the United States region");
  const call = withHome(path, init);
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

/**
 * Only this server's Boston Tank is active. Old cross-region configuration
 * cannot enable the stopped ZA service or move a ZA tenant's work to Boston.
 */
export function regionTank(region: Region): { url: string; key: string } | null {
  if (region !== "us-east" || process.env.TANK_REGION?.trim().toLowerCase() === "za") return null;
  return { url: TANK_URL, key: TANK_API_KEY };
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
