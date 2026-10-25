import { clerkMiddleware, createRouteMatcher } from "@clerk/nextjs/server";
import { NextResponse } from "next/server";
import { productHostRewritePath } from "@/lib/product-hosts";

// Everything is private except Clerk's own sign-in/up pages, the health probe, and the Stripe webhook.
// Stripe calls the webhook with a signature, not a Clerk session.
const isPublic = createRouteMatcher(["/sign-in(.*)", "/sign-up(.*)", "/api/health", "/api/billing/webhook"]);

export default clerkMiddleware(async (auth, req) => {
  if (isPublic(req)) return;

  const host = req.headers.get("x-forwarded-host") ?? req.headers.get("host");
  const rewriteTo = productHostRewritePath(host, req.nextUrl.pathname);

  // auth.protect() was rewriting signed-out traffic to a phantom /clerk_* path (404).
  // Explicit sign-in redirect keeps protect/autumbra and squad hosts usable.
  const { userId, redirectToSignIn } = await auth();
  if (!userId) {
    const returnUrl = req.nextUrl.clone();
    if (rewriteTo) returnUrl.pathname = rewriteTo;
    return redirectToSignIn({ returnBackUrl: returnUrl });
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
