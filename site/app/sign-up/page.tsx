import type { Metadata } from "next";
import { SiteFooter } from "../footer";
import { SiteNav } from "../nav";
import { CLERK_SIGN_IN, CLERK_SIGN_UP, signUpDescription, signUpTitle } from "../../lib/site";

export const metadata: Metadata = {
  title: signUpTitle,
  description: signUpDescription,
  alternates: { canonical: "/sign-up" },
  openGraph: {
    title: signUpTitle,
    description: signUpDescription,
    url: "/sign-up",
  },
  robots: { index: true, follow: true },
};

export default function SignUpPage() {
  return (
    <>
      <a className="skip" href="#main">
        Skip to content
      </a>
      <SiteNav />
      <main id="main" className="section signup">
        <p className="eyebrow">One path</p>
        <h1>Sign up</h1>
        <p className="lead">{signUpDescription}</p>
        <p className="signup-body">
          You set the account up on the Tervory app. There is no second account system on this site, and this page does
          not ask for a password.
        </p>
        <div className="hero-actions">
          <a className="btn btn-primary" href={CLERK_SIGN_UP}>
            Continue to sign up
          </a>
        </div>
        <p className="signup-note">
          Already have an account? <a href={CLERK_SIGN_IN}>Sign in</a>
        </p>
      </main>
      <SiteFooter />
    </>
  );
}
