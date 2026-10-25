import { clerkMiddleware, createRouteMatcher } from "@clerk/nextjs/server";
import { NextResponse } from "next/server";
import { productHostRewritePath } from "@/lib/product-hosts";

// Public: Clerk pages, health, Stripe webhook, and the Autumbra product page.
// Founder console /admin/autumbra stays private.
const isPublic = createRouteMatcher([
  "/sign-in(.*)",
  "/sign-up(.*)",
  "/api/health",
  "/api/billing/webhook",
  "/autumbra(.*)",
]);

export default clerkMiddleware(async (auth, req) => {
  const host = req.headers.get("x-forwarded-host") ?? req.headers.get("host");
  const rewriteTo = productHostRewritePath(host, req.nextUrl.pathname);
  if (rewriteTo) {
    const url = req.nextUrl.clone();
    url.pathname = rewriteTo;
    // After rewrite, isPublic(req) still sees the original path (/). Allow Autumbra public landing.
    const rewriteIsPublic = rewriteTo === "/autumbra" || rewriteTo.startsWith("/autumbra/");
    if (!rewriteIsPublic && !isPublic(req)) await auth.protect();
    return NextResponse.rewrite(url);
  }
  if (!isPublic(req)) await auth.protect();
});

export const config = {
  matcher: ["/((?!_next|.*\\..*).*)", "/(api|trpc)(.*)"],
};
