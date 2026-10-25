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

  // auth.protect() was rewriting signed-out traffic to a phantom /clerk_* path (404).
  // Explicit sign-in redirect keeps private panels (e.g. /zenas) usable when signed out.
  const rewriteTo = productHostRewritePath(host, req.nextUrl.pathname);
  const pathAfter = rewriteTo ?? req.nextUrl.pathname;
  const publicOk = isPublicProductPath(pathAfter) || isPublic(req);
  if (!publicOk) {
    const { userId, redirectToSignIn } = await auth();
    if (!userId) {
      const returnUrl = req.nextUrl.clone();
      if (rewriteTo) returnUrl.pathname = rewriteTo;
      return redirectToSignIn({ returnBackUrl: returnUrl });
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
