import { clerkMiddleware, createRouteMatcher } from "@clerk/nextjs/server";
import { NextResponse } from "next/server";
import { productHostRewritePath } from "@/lib/product-hosts";

// Everything is private except Clerk's own sign-in/up pages, the health probe, and the Stripe webhook.
// Stripe calls the webhook with a signature, not a Clerk session.
const isPublic = createRouteMatcher(["/sign-in(.*)", "/sign-up(.*)", "/api/health", "/api/billing/webhook"]);

export default clerkMiddleware(async (auth, req) => {
  const host = req.headers.get("x-forwarded-host") ?? req.headers.get("host");
  const rewriteTo = productHostRewritePath(host, req.nextUrl.pathname);
  if (rewriteTo) {
    const url = req.nextUrl.clone();
    url.pathname = rewriteTo;
    if (!isPublic(req)) await auth.protect();
    return NextResponse.rewrite(url);
  }
  if (!isPublic(req)) await auth.protect();
});

export const config = {
  matcher: ["/((?!_next|.*\\..*).*)", "/(api|trpc)(.*)"],
};
