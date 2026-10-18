import type { Metadata } from "next";
import { SiteFooter } from "./footer";
import { SiteNav } from "./nav";
import { ReleaseForm } from "./release-form";
import { homeDescription } from "../lib/site";

export const metadata: Metadata = {
  alternates: { canonical: "/" },
};

const products = [
  {
    name: "Base",
    mark: "/brand/base-on-light.png",
    width: 124,
    body: "Finds, cleans and enriches data. A list of names comes back as people and companies you can contact, each field with a source.",
  },
  {
    name: "Tiger",
    mark: "/brand/tiger-on-light.png",
    width: 104,
    body: "Watches prices and competitors, and says when a rival moves.",
  },
  {
    name: "Market Lab",
    mark: "/brand/market-lab-on-light.png",
    width: 194,
    body: "Market research. Sizing, segments, demand, and the source behind a number.",
  },
  {
    name: "Rig",
    mark: "/brand/rig-on-light.png",
    width: 58,
    body: "Finds a product in a shop's catalogue.",
  },
  {
    name: "Tisan",
    mark: "/brand/tisan-on-light.png",
    width: 128,
    body: "Builds a website or an app from a short brief.",
  },
  {
    name: "Radix",
    mark: "/brand/radix-on-light.png",
    width: 93,
    body: "Reviews what a system exposes, what it stores, and who can reach it.",
  },
  {
    name: "Zenas",
    mark: "/brand/zenas-on-light.png",
    width: 90,
    body: "Reads contracts, policies and terms, and flags risk.",
  },
  {
    name: "Skala",
    mark: "/brand/skala-on-light.png",
    width: 134,
    body: "Keeps the skills each specialist uses.",
  },
  {
    name: "Tank",
    mark: "/brand/tank-on-light.png",
    width: 131,
    body: "The only path to a model. An answer names the model that did the work.",
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
          <p className="eyebrow">Being built</p>
          <h1>One window for the work.</h1>
          <p className="lead">
            Tervory is one place to ask for data, research, price checks, legal reviews, or a website. Specialists do
            the work. An answer shows which model did it.
          </p>
          <p className="closed">Nothing is open yet.</p>
          <ReleaseForm />
        </section>
        <section className="band" id="work">
          <div className="section-head">
            <p className="eyebrow">The work</p>
            <h2>What is being built.</h2>
          </div>
          <div className="steps">
            <article className="step">
              <p className="step-no">01</p>
              <h3>Ask</h3>
              <p>You describe the work in plain language.</p>
            </article>
            <article className="step">
              <p className="step-no">02</p>
              <h3>Routed</h3>
              <p>Tank sends it to the specialist for that job.</p>
            </article>
            <article className="step">
              <p className="step-no">03</p>
              <h3>Answer</h3>
              <p>The answer shows which model did the work.</p>
            </article>
          </div>
        </section>
        <section className="section" id="research">
          <div className="section-head">
            <p className="eyebrow">Research</p>
            <h2>Research underway.</h2>
          </div>
          <div className="research">
            <p>Skills are tested before a specialist uses them.</p>
            <p>A cheaper model has to agree before it takes over a task.</p>
          </div>
        </section>
        <section className="section" id="products">
          <div className="section-head">
            <p className="eyebrow">Products</p>
            <h2>Nine products. None of them is open yet.</h2>
          </div>
          <div className="products">
            {products.map((product) => (
              <article className="product" key={product.name}>
                <img className="wordmark" src={product.mark} width={product.width} height={32} alt={product.name} />
                <p>{product.body}</p>
              </article>
            ))}
          </div>
        </section>
      </main>
      <SiteFooter />
    </>
  );
}
