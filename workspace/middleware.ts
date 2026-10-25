import { clerkMiddleware, createRouteMatcher } from "@clerk/nextjs/server";
import { NextResponse } from "next/server";
import { mootCanonicalRedirectUrl, productHostRewritePath } from "@/lib/product-hosts";

// Public: Clerk pages, health, Stripe webhook, Autumbra product page, Moot watch.
// The squad consoles (/base, /tiger, /market-lab, /tisan, /radix, /skala, /tank) need sign-in.
// Founder console /admin/autumbra stays private.
const isPublic = createRouteMatcher([
  "/sign-in(.*)",
  "/sign-up(.*)",
  "/api/health",
  "/api/billing/webhook",
  "/autumbra(.*)",
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
