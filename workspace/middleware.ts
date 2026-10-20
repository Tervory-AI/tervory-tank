import { clerkMiddleware, createRouteMatcher } from "@clerk/nextjs/server";

// Everything is private except Clerk's own sign-in/up pages, the health probe, and the Stripe webhook.
// Stripe calls the webhook with a signature, not a Clerk session.
const isPublic = createRouteMatcher(["/sign-in(.*)", "/sign-up(.*)", "/api/health", "/api/billing/webhook"]);

export default clerkMiddleware(async (auth, req) => {
  if (!isPublic(req)) await auth.protect();
});

export const config = {
  matcher: ["/((?!_next|.*\\..*).*)", "/(api|trpc)(.*)"],
};
