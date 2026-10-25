/**
 * Product-per-host map for *.tervory.com.
 * app.tervory.com stays the client workspace home.
 * protect / autumbra land on the public Autumbra product page.
 * Founder console remains at /admin/autumbra.
 * Squad product hosts land on their existing workspace paths.
 * Separate Coolify services (rig, mcp, site, coolify) are not rewritten here.
 */

export type ProductHost = {
  host: string;
  /** Absolute path the host root rewrites to inside the workspace app. */
  rootPath: string;
  /** Short product label for docs / ops (not user-facing Ghost/Wraith names). */
  product: string;
  /** When true, only founders reach the landing (Autumbra /admin/*). */
  founderOnly?: boolean;
};

/** Hosts served by the Coolify workspace service (same as app.tervory.com). */
export const WORKSPACE_PRODUCT_HOSTS: readonly ProductHost[] = [
  { host: "protect.tervory.com", rootPath: "/autumbra", product: "Autumbra" },
  { host: "autumbra.tervory.com", rootPath: "/autumbra", product: "Autumbra" },
  { host: "zenas.tervory.com", rootPath: "/zenas", product: "Zenas" },
  { host: "base.tervory.com", rootPath: "/base", product: "Base" },
  { host: "tiger.tervory.com", rootPath: "/tiger", product: "Tiger" },
  { host: "market-lab.tervory.com", rootPath: "/market-lab", product: "Market Lab" },
  { host: "tisan.tervory.com", rootPath: "/tisan", product: "Tisan" },
  { host: "radix.tervory.com", rootPath: "/radix", product: "Radix" },
  { host: "skala.tervory.com", rootPath: "/skala", product: "Skala", founderOnly: true },
  { host: "tank.tervory.com", rootPath: "/tank", product: "Tank", founderOnly: true },
] as const;

const BY_HOST = new Map(WORKSPACE_PRODUCT_HOSTS.map((row) => [row.host, row]));

/** Strip port and lowercase; empty when missing. */
export function normalizeHost(raw: string | null | undefined): string {
  if (!raw) return "";
  const first = raw.split(",")[0]?.trim().toLowerCase() ?? "";
  return first.replace(/:\d+$/, "");
}

export function productHostFor(hostHeader: string | null | undefined): ProductHost | null {
  const host = normalizeHost(hostHeader);
  if (!host) return null;
  return BY_HOST.get(host) ?? null;
}

/**
 * Path rewrite for a product host.
 * - `/` (and empty) → that product's rootPath
 * - already on rootPath or under it → no rewrite
 * - public Clerk / health / webhook paths → no rewrite
 * - everything else on that host stays as-is (deep links work)
 */
export function productHostRewritePath(
  hostHeader: string | null | undefined,
  pathname: string,
): string | null {
  const product = productHostFor(hostHeader);
  if (!product) return null;
  const path = pathname.length > 1 && pathname.endsWith("/") ? pathname.slice(0, -1) : pathname || "/";
  if (
    path.startsWith("/sign-in") ||
    path.startsWith("/sign-up") ||
    path === "/api/health" ||
    path.startsWith("/api/billing/webhook") ||
    path.startsWith("/_next")
  ) {
    return null;
  }
  if (path === "/" || path === "") return product.rootPath;
  return null;
}

export function isAutumbraHost(hostHeader: string | null | undefined): boolean {
  const product = productHostFor(hostHeader);
  return product?.product === "Autumbra";
}
