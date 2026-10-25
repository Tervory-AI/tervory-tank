import { clerkMiddleware, createRouteMatcher } from "@clerk/nextjs/server";
import { NextResponse } from "next/server";
import { productHostRewritePath } from "@/lib/product-hosts";

// Public: Clerk sign-in/up, health, Stripe webhook, Autumbra product + demo.
// Visitors must be able to read /autumbra without an auth fight.
const isPublic = createRouteMatcher([
  "/sign-in(.*)",
  "/sign-up(.*)",
  "/api/health",
  "/api/billing/webhook",
  "/autumbra(.*)",
]);

function isAutumbraPublicPath(pathname: string): boolean {
  return pathname === "/autumbra" || pathname.startsWith("/autumbra/");
}

export default clerkMiddleware(async (auth, req) => {
  const host = req.headers.get("x-forwarded-host") ?? req.headers.get("host");
  const rewriteTo = productHostRewritePath(host, req.nextUrl.pathname);
  if (rewriteTo) {
    const url = req.nextUrl.clone();
    url.pathname = rewriteTo;
    if (!isPublic(req) && !isAutumbraPublicPath(rewriteTo)) await auth.protect();
    return NextResponse.rewrite(url);
  }
  if (!isPublic(req)) await auth.protect();
});

export const config = {
  matcher: ["/((?!_next|.*\\..*).*)", "/(api|trpc)(.*)"],
};
