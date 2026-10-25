import { clerkMiddleware, createRouteMatcher } from "@clerk/nextjs/server";
import { NextResponse } from "next/server";
import {
  isPublicProductPath,
  mootCanonicalRedirectUrl,
  productHostRewritePath,
} from "@/lib/product-hosts";

// Public: product host roots, Clerk pages, health, Stripe webhook.
// Founder console /admin/autumbra stays private.
const isPublic = createRouteMatcher([
  "/sign-in(.*)",
  "/sign-up(.*)",
  "/api/health",
  "/api/billing/webhook",
  "/autumbra(.*)",
  "/moot(.*)",
  "/base(.*)",
  "/tiger(.*)",
  "/market-lab(.*)",
  "/tisan(.*)",
  "/radix(.*)",
  "/skala(.*)",
  "/tank(.*)",
]);

export default clerkMiddleware(async (auth, req) => {
  const host = req.headers.get("x-forwarded-host") ?? req.headers.get("host");
  const canonical = mootCanonicalRedirectUrl(host, req.nextUrl.pathname, req.nextUrl.search);
  if (canonical) {
    return NextResponse.redirect(canonical, 308);
  }
  const rewriteTo = productHostRewritePath(host, req.nextUrl.pathname);
  if (rewriteTo) {
    const url = req.nextUrl.clone();
    url.pathname = rewriteTo;
    // After rewrite, isPublic(req) still sees the original path (/).
    if (!isPublicProductPath(rewriteTo) && !isPublic(req)) await auth.protect();
    return NextResponse.rewrite(url);
  }
  if (!isPublic(req)) await auth.protect();
});

export const config = {
  matcher: ["/((?!_next|.*\\..*).*)", "/(api|trpc)(.*)"],
};
