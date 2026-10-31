import { clerkMiddleware, createRouteMatcher } from "@clerk/nextjs/server";
import { NextResponse } from "next/server";
import { mootCanonicalRedirectUrl, productHostRewritePath, publicReturnUrl } from "@/lib/product-hosts";

// Public: Clerk pages, health, Stripe webhook, Autumbra product/owner pages, Moot watch.
// Autumbra receipts + undo stay reachable signed-out ONLY so email tokens work;
// each handler token-gates (no token / forged / expired / other-tenant → 401).
// The squad consoles (/base, /tiger, /market-lab, /tisan, /radix, /skala, /tank) need sign-in.
// Founder console /admin/autumbra stays private.
const isPublic = createRouteMatcher([
  // CLI corridor authenticates bearer PATs in Tank, never Clerk cookies.
  "/v1/command(.*)",
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
]);

// After a host rewrite, isPublic(req) still sees the original path (/).
function rewriteIsPublic(path: string): boolean {
  return path === "/autumbra" || path.startsWith("/autumbra/") || path === "/moot" || path.startsWith("/moot/");
}

export default clerkMiddleware(async (auth, req) => {
  const host = req.headers.get("x-forwarded-host") ?? req.headers.get("host");
  const canonical = mootCanonicalRedirectUrl(host, req.nextUrl.pathname, req.nextUrl.search);
  if (canonical) {
    return NextResponse.redirect(canonical, 308);
  }

  // auth.protect() was rewriting signed-out traffic to a phantom /clerk_* path (404).
  // Explicit sign-in redirect keeps private panels (e.g. /zenas) usable when signed out.
  const rewriteTo = productHostRewritePath(host, req.nextUrl.pathname);
  const publicOk = (rewriteTo ? rewriteIsPublic(rewriteTo) : false) || isPublic(req);
  if (!publicOk) {
    const { userId, redirectToSignIn } = await auth();
    if (!userId) {
      // Back to the public address they asked for (base.tervory.com/), never the internal
      // bind or the rewritten path (https://0.0.0.0:3000/base, seen 28 Oct).
      return redirectToSignIn({ returnBackUrl: publicReturnUrl(host, req.nextUrl.pathname, req.nextUrl.search) });
    }
  }

  if (rewriteTo) {
    const url = req.nextUrl.clone();
    url.pathname = rewriteTo;
    return NextResponse.rewrite(url);
  }
});

export const config = {
  matcher: ["/((?!_next|.*\\..*).*)", "/(api|trpc)(.*)"],
};
