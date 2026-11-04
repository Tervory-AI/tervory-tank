import { getToken } from "next-auth/jwt";
import type { NextRequest } from "next/server";
import { NextResponse } from "next/server";
import { mootCanonicalRedirectUrl, productHostRewritePath, publicReturnUrl } from "@/lib/product-hosts";

// Autumbra receipts + undo stay reachable signed-out ONLY so email tokens work;
// each handler token-gates (no token / forged / expired / other-tenant → 401).
// The squad consoles (/base, /tiger, /market-lab, /tisan, /radix, /skala, /tank) need sign-in.
// Founder console /admin/autumbra stays private.
const publicRoutes = [
  "/api/auth(.*)",
  "/api/trigger-signin/signed-out",
  // MCP authenticates its own bearer credentials; OAuth public protocol endpoints.
  "/mcp",
  "/oauth/token",
  "/oauth/register",
  "/oauth/revoke",
  "/.well-known/oauth-protected-resource",
  "/.well-known/oauth-protected-resource/mcp",
  "/.well-known/oauth-authorization-server",
  "/v1/command(.*)",
  // Public visitor bot authenticates its own origin-bound embed key, including OPTIONS.
  "/v1/bot/messages",
  // Meta webhooks authenticate their raw-body signature in Tank.
  "/v1/bot/whatsapp",
  "/v1/bot/widget/(config|message|handover|poll)",
  // Self-hosted CLI release files (static, public/cli). SHA256SUMS has no dot, so the
  // matcher below does not skip it; list the release paths explicitly.
  "/cli/install.sh",
  "/cli/latest.json",
  "/cli/releases(.*)",
  "/sign-in(.*)",
  "/sign-up(.*)",
  "/api/health",
  "/api/billing/webhook",
  "/autumbra(.*)",
  "/api/autumbra/undo",
  "/api/autumbra/receipts(.*)",
  "/moot(.*)",
];

function isPublic(request: NextRequest): boolean {
  return publicRoutes.some(pattern => new RegExp(`^${pattern}$`).test(request.nextUrl.pathname));
}

// After a host rewrite, isPublic(req) still sees the original path (/).
function rewriteIsPublic(path: string): boolean {
  return path === "/autumbra" || path.startsWith("/autumbra/") || path === "/moot" || path.startsWith("/moot/");
}

export default async function middleware(req: NextRequest) {
  const host = req.headers.get("x-forwarded-host") ?? req.headers.get("host");
  const canonical = mootCanonicalRedirectUrl(host, req.nextUrl.pathname, req.nextUrl.search);
  if (canonical) {
    return NextResponse.redirect(canonical, 308);
  }

  // Explicit sign-in redirect keeps private panels (e.g. /zenas) usable when signed out.
  const rewriteTo = productHostRewritePath(host, req.nextUrl.pathname);
  const publicOk = (rewriteTo ? rewriteIsPublic(rewriteTo) : false) || isPublic(req);
  if (!publicOk) {
    const token = await getToken({ req, secret: process.env.TRIGGER_SIGNIN_WORKSPACE_SECRET, cookieName: "__Secure-tervory-signin", secureCookie: true });
    const principal = token?.principal as { expiresAt?: number } | undefined;
    if (!principal || (principal.expiresAt ?? 0) <= Date.now()) {
      // Back to the public address they asked for (base.tervory.com/), never the internal
      // bind or the rewritten path (https://0.0.0.0:3000/base, seen 28 Oct).
      const signin = new URL("/sign-in", "https://app.tervory.com");
      signin.searchParams.set("callbackUrl", publicReturnUrl(host, req.nextUrl.pathname, req.nextUrl.search));
      return NextResponse.redirect(signin);
    }
  }

  if (rewriteTo) {
    const url = req.nextUrl.clone();
    url.pathname = rewriteTo;
    return NextResponse.rewrite(url);
  }
  return NextResponse.next();
}

export const config = {
  matcher: ["/((?!_next|.*\\..*).*)", "/(api|trpc)(.*)"],
};
