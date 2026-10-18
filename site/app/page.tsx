import type { Metadata } from "next";
import { SiteNav } from "./nav";
import { homeDescription } from "../lib/site";

export const metadata: Metadata = {
  alternates: { canonical: "/" },
};

const steps = [
  { href: "#ask", num: "01", label: "Ask in plain language" },
  { href: "#cost", num: "02", label: "Read the answer and the bill" },
  { href: "#decide", num: "03", label: "Keep what you accept" },
];

const structured = {
  "@context": "https://schema.org",
  "@type": "WebPage",
  name: "Tervory AI",
  url: "https://tervory.com/",
  description: homeDescription,
};

export default function HomePage() {
  return (
    <>
      <script type="application/ld+json" dangerouslySetInnerHTML={{ __html: JSON.stringify(structured) }} />
      <a className="skip" href="#main">
        Skip to content
      </a>
      <SiteNav />
      <main id="main">
        <section className="hero" id="top">
          <div className="hero-copy">
            <p className="eyebrow">For a business exploring AI</p>
            <h1>Ask for the work. See what it cost.</h1>
            <p className="lead">{homeDescription}</p>
            <div className="hero-actions">
              <a className="btn btn-primary" href="/sign-up">
                Sign up
              </a>
            </div>
          </div>
          <ol className="route">
            {steps.map((step) => (
              <li key={step.href}>
                <a href={step.href}>
                  <span className="route-num">{step.num}</span>
                  <span>{step.label}</span>
                </a>
              </li>
            ))}
          </ol>
        </section>

        <section className="chapter" id="ask">
          <div className="chapter-copy">
            <p className="eyebrow">01 — Ask</p>
            <h2>Ask in plain language.</h2>
            <p>
              You do not pick a model, a vendor, or a credit pack. You describe the job: a list to clean, a price to
              check, a contract to read, or a page to build.
            </p>
          </div>
          <figure className="scene">
            <figcaption>Example</figcaption>
            <p className="scene-ask">What are competitors charging for this part?</p>
            <p className="scene-note">The job is written the way you would say it.</p>
          </figure>
        </section>

        <section className="chapter chapter-tint" id="cost">
          <div className="chapter-copy">
            <p className="eyebrow">02 — Cost</p>
            <h2>Read the answer and the bill together.</h2>
            <p>
              Each answer names the model that produced it, what it cost, and how long it took. The cheapest way that
              can do the job well is used first. The cost is shown either way.
            </p>
          </div>
          <div className="facts">
            <article>
              <h3>Model</h3>
              <p>The name of the model that produced the answer.</p>
            </article>
            <article>
              <h3>Cost</h3>
              <p>The price of that answer, down to the fraction of a cent.</p>
            </article>
            <article>
              <h3>Time</h3>
              <p>How long the answer took.</p>
            </article>
          </div>
        </section>

        <section className="chapter" id="decide">
          <div className="chapter-copy">
            <p className="eyebrow">03 — Decide</p>
            <h2>Keep what you accept.</h2>
            <p>
              You mark the result accepted or not. An accepted answer is what you pay for. If you do not accept it, the
              decision is recorded, and it is not a result you bought.
            </p>
          </div>
          <div className="choices">
            <article>
              <h3>Accepted</h3>
              <p>You pay for this result.</p>
            </article>
            <article>
              <h3>Not accepted</h3>
              <p>It stays on the record. It is not a result you bought.</p>
            </article>
          </div>
        </section>

        <section className="close" id="start">
          <p className="eyebrow eyebrow-on-ink">Sign up</p>
          <h2>Create the account on the app.</h2>
          <p>
            Sign up is one path. It opens the Tervory app, where the account is created. This site does not ask for a
            password.
          </p>
          <a className="btn btn-primary" href="/sign-up">
            Sign up
          </a>
        </section>
      </main>
      <footer className="footer">
        <div className="footer-brand">
          <img
            className="footer-logo"
            src="/brand/tervory-logo-reversed-display.png"
            width={167}
            height={31}
            alt="Tervory AI"
            loading="lazy"
          />
          <p>One window for the work. Every answer shows the model and the cost.</p>
        </div>
        <ul className="footer-links">
          <li>
            <a href="/sign-up">Sign up</a>
          </li>
          <li>
            <a href="https://app.tervory.com/sign-in">Sign in</a>
          </li>
        </ul>
        <p className="footer-copy">© 2026 Tervory AI</p>
      </footer>
    </>
  );
}
