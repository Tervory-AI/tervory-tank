import type { Metadata } from "next";
import { SiteNav } from "./nav";
import { CLERK_SIGN_IN, CLERK_SIGN_UP, homeDescription } from "../lib/site";

export const metadata: Metadata = {
  alternates: { canonical: "/" },
};

const work = ["Data", "Research", "Price checks", "Legal reviews", "A website"];

const squad = [
  {
    letter: "B",
    name: "Base",
    body: "Finds, cleans and enriches data. Takes a list of names and returns a list of people and companies you can actually contact — every field sourced and scored.",
    domain: "data · enrichment",
  },
  {
    letter: "T",
    name: "Tiger",
    body: "Watches prices and competitors. Tells you when a rival moves, what they changed and what it means for your margin.",
    domain: "pricing · competitor watch",
  },
  {
    letter: "M",
    name: "Market Lab",
    body: "Market research on demand. Sizing, segments, demand signals and the sources behind every number.",
    domain: "market research",
  },
  {
    letter: "R",
    name: "Radix",
    body: "Security. Reviews what you expose, what you store and who can reach it, and reports in plain language.",
    domain: "security",
  },
  {
    letter: "Ti",
    name: "Tisan",
    body: "Builds websites and apps from a brief. Ships working pages, not mockups, inside your tenant.",
    domain: "websites · apps",
  },
  {
    letter: "Z",
    name: "Zenas",
    body: "Legal. Reads contracts, policies and terms, flags risk and drafts what you need to sign or send.",
    domain: "legal",
  },
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
            <p className="eyebrow">One workspace · every answer priced</p>
            <h1>Ask for the work. See exactly what it cost.</h1>
            <p className="lead">{homeDescription}</p>
            <div className="hero-actions">
              <a className="btn btn-primary" href={CLERK_SIGN_UP}>
                Sign up
              </a>
            </div>
            <p className="fine">No credits. No seats. Logins at app.tervory.com.</p>
          </div>
          <ul className="work">
            {work.map((item) => (
              <li key={item}>{item}</li>
            ))}
          </ul>
        </section>

        <section className="band" id="how">
          <div className="section-head">
            <p className="eyebrow">How it works</p>
            <h2>One request. Three things happen.</h2>
            <p className="lead">
              You never pick a model, a vendor or a credit pack. You ask in plain language, and Tervory handles the rest
              — then shows you the receipt.
            </p>
          </div>
          <div className="steps">
            <article>
              <p className="step-no">01</p>
              <h3>Ask</h3>
              <p>
                Type what you need in Chat, or queue it in Tasks. “Enrich this list.” “What are competitors charging?”
                “Review this contract.” “Build me a landing page.”
              </p>
            </article>
            <article>
              <p className="step-no">02</p>
              <h3>Routed through Tank</h3>
              <p>
                Tank picks the cheapest rung that can do the job well — a frontier model, our own small model, plain
                code, or a cached answer — and hands the work to the right specialist.
              </p>
            </article>
            <article>
              <p className="step-no">03</p>
              <h3>Result, with the bill</h3>
              <p>
                The answer comes back with the model that produced it, what it cost and how long it took. You mark it
                accepted or not. That decision is what you pay for.
              </p>
            </article>
          </div>
          <p className="flow">
            <span>You</span>
            <span className="flow-line" aria-hidden="true" />
            <span>Workspace</span>
            <span className="flow-line" aria-hidden="true" />
            <span className="flow-ink">Tank</span>
            <span className="flow-line" aria-hidden="true" />
            <span>Specialist</span>
            <span className="flow-line" aria-hidden="true" />
            <span>Ledger</span>
          </p>
          <p className="flow-note">Clients see the Workspace and the Ledger. The specialists stay behind the scenes.</p>
        </section>

        <section className="band band-plain" id="specialists">
          <div className="section-head">
            <p className="eyebrow">The Squad</p>
            <h2>Six specialists. One window.</h2>
            <p className="lead">
              Each specialist is built for one kind of work and gets better at it with every job. You never talk to them
              directly — you ask in the Workspace and they deliver.
            </p>
          </div>
          <div className="cards">
            {squad.map((member) => (
              <article className="card" key={member.name}>
                <p className="glyph" aria-hidden="true">
                  {member.letter}
                </p>
                <h3>{member.name}</h3>
                <p>{member.body}</p>
                <p className="domain">{member.domain}</p>
              </article>
            ))}
          </div>
          <p className="flow-note">Clients never see the agents. They see results — and the Ledger line for each one.</p>
        </section>

        <section className="close" id="start">
          <p className="eyebrow eyebrow-on-ink">Sign up</p>
          <h2>Start with your own data.</h2>
          <p>No credits. No seats. Logins at app.tervory.com.</p>
          <a className="btn btn-primary" href={CLERK_SIGN_UP}>
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
          />
          <p>One window for the work. Every answer shows the model and the cost.</p>
        </div>
        <ul className="footer-links">
          <li>
            <a href={CLERK_SIGN_UP}>Sign up</a>
          </li>
          <li>
            <a href={CLERK_SIGN_IN}>Sign in</a>
          </li>
        </ul>
        <p className="footer-copy">© 2026 Tervory AI</p>
      </footer>
    </>
  );
}
