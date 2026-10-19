import type { Metadata } from "next";
import { SiteFooter } from "./footer";
import { SiteNav } from "./nav";
import { ReleaseForm } from "./release-form";
import { homeDescription, homeTitle } from "../lib/site";

export const metadata: Metadata = {
  alternates: { canonical: "/" },
};

const products = [
  {
    name: "Base",
    mark: "/brand/base-on-light.png",
    width: 2323,
    height: 601,
    body: "Turns a raw list into verified businesses: websites, contacts and licences, each with a source.",
  },
  {
    name: "Tiger",
    mark: "/brand/tiger-on-light.png",
    width: 2607,
    height: 801,
    body: "Watches prices and competitors, and tells you the moment a rival moves.",
  },
  {
    name: "Market Lab",
    mark: "/brand/market-lab-on-light.png",
    width: 3685,
    height: 608,
    body: "Market research with every number sourced: demand, gaps, and shifts before they show.",
  },
  {
    name: "Rig",
    mark: "/brand/rig-on-light.png",
    width: 1173,
    height: 651,
    body: "Finds the right product, and every part that fits it, in a retailer's own catalogue.",
  },
  {
    name: "Tisan",
    mark: "/brand/tisan-on-light.png",
    width: 2806,
    height: 701,
    body: "Builds websites and apps from a short brief, tested before they go live.",
  },
  {
    name: "Radix",
    mark: "/brand/radix-on-light.png",
    width: 1893,
    height: 651,
    body: "Finds what your systems and sites expose, before someone else does.",
  },
  {
    name: "Zenas",
    mark: "/brand/zenas-on-light.png",
    width: 1970,
    height: 701,
    body: "Legal research and drafting for US and South African business law, reviewed by licensed lawyers.",
  },
  {
    name: "Skala",
    mark: "/brand/skala-on-light.png",
    width: 3778,
    height: 901,
    body: "The skills library. Every skill is tested before a specialist may use it.",
  },
  {
    name: "Tank",
    mark: "/brand/tank-on-light.png",
    width: 2466,
    height: 601,
    body: "The engine underneath. It routes every task to the best-value model and keeps the receipts.",
  },
];

const structured = {
  "@context": "https://schema.org",
  "@type": "WebPage",
  name: homeTitle,
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
          <p className="eyebrow">Tervory AI · In build</p>
          <h1>Specialist AI for the work that runs a business.</h1>
          <p className="lead">
            Tervory is a squad of specialist AI agents for data, pricing, markets, legal, security and the web. Ask in
            plain language. The right specialist does the work, shows its sources, and tells you which model ran it and
            what it cost.
          </p>
          <ReleaseForm />
          <p className="note">We are opening to a small group of businesses first.</p>
        </section>
        <section className="band" id="work">
          <div className="section-head">
            <h2>How it works</h2>
          </div>
          <div className="steps">
            <article className="step">
              <h3>Ask.</h3>
              <p>Describe the job the way you would brief a colleague.</p>
            </article>
            <article className="step">
              <h3>Routed.</h3>
              <p>Tank sends it to the specialist built for that job, on the best-value route that still gets it right.</p>
            </article>
            <article className="step">
              <h3>Answered.</h3>
              <p>Every answer comes with its sources, the model that produced it, and the cost.</p>
            </article>
          </div>
        </section>
        <section className="section" id="cheaper">
          <div className="section-head">
            <h2>It gets cheaper the more it works</h2>
          </div>
          <p className="prose">
            Most AI charges the same for the hundredth question as the first. Tervory learns. When a cheaper model, or
            plain code, proves it gives the same answer, it takes over the task, automatically and only after it has
            been tested. The work stays right. The cost keeps falling.
          </p>
        </section>
        <section className="section" id="products">
          <div className="section-head">
            <h2>The squad</h2>
            <p className="sub">Nine specialists. Each one built for a single job.</p>
          </div>
          <div className="products">
            {products.map((product) => (
              <article className="product" key={product.name}>
                <img
                  className="wordmark"
                  src={product.mark}
                  width={product.width}
                  height={product.height}
                  alt={product.name}
                  loading="lazy"
                  decoding="async"
                />
                <p>{product.body}</p>
              </article>
            ))}
          </div>
        </section>
        <section className="band" id="proof">
          <div className="section-head">
            <h2>Measured, not promised</h2>
          </div>
          <p className="prose">
            Every skill passes a test set before it goes live. A cheaper route only takes over once it matches the
            results. If we cannot measure it, we do not claim it.
          </p>
        </section>
        <section className="section" id="early">
          <div className="section-head">
            <h2>Be first in</h2>
          </div>
          <p className="prose">
            We are opening Tervory to a small group of businesses first. Leave your email and we will tell you when your
            seat is ready.
          </p>
          <ReleaseForm />
        </section>
      </main>
      <SiteFooter />
    </>
  );
}
