import type { Metadata } from "next";
import { ReleaseForm } from "./release-form";
import { EngineDiagram, RigShowcase, ReceiptExample } from "./home-interactions";
import { homeCopy as copy } from "./home-copy";
import { homeDescription, homeTitle } from "../lib/site";
import "./homepage.css";

export const metadata: Metadata = { alternates: { canonical: "/" } };
const mechanisms = [["Cheapest Frontier Model", "112:2552"], ["Shadow Run", "112:2557"], ["Cached Answers & Internal Code", "112:2562"], ["Savings Grow as It Learns", "112:2571"], ["Bulk / Batch Rates", "203:2251"]];
const products = [
  { name: "TANK", artwork: "imgArtwork7.svg", w: 90.411, h: 22, purpose: "AI Routing & Cost Control", body: "113:3557" },
  { name: "SKALA", artwork: "imgArtwork6.svg", w: 92.6316, h: 22, purpose: "Tested Code Tools", body: "136:2481" },
  { name: "TISAN", artwork: "imgArtwork5.svg", w: 88, h: 22, purpose: "Website Design & Development", body: "113:3568" },
  { name: "RIG", artwork: "imgArtwork4.svg", w: 39.655, h: 22, purpose: "Product Matching & Price Comparison", body: "113:3584", optional: "113:3589" },
  { name: "TRIGGER", artwork: "imgLogoTriggerCrmOriginalWhitePng.png", w: 103, h: 30.716, purpose: "CRM & Marketing Content", body: "113:3601" },
  { name: "BASE", artwork: "imgArtwork3.svg", w: 84.8875, h: 22, purpose: "Data Extraction & Structuring", body: "113:3617" },
  { name: "ZENAS", artwork: "imgArtwork2.svg", w: 61.82, h: 22, purpose: "Legal Drafting & Research", body: "113:3628" },
  { name: "TIGER", artwork: "imgArtwork1.svg", w: 71.5447, h: 22, purpose: "Competitor & Supply Monitoring", body: "113:3639" },
  { name: "MARKET LAB", artwork: "imgArtwork.svg", w: 133.333, h: 22, purpose: "Market Data Research", body: "136:2544" },
  { name: "AUTUMBRA", artwork: "imgLogoAutumbraOriginalWhitePng.png", w: 135, h: 20, purpose: "Air-Gapped Cybersecurity", body: "113:3656", optional: "113:3661" },
];
function Brand({ footer = false }: { footer?: boolean }) {
  return <a className="home-brand" href="#top" aria-label="Tervory AI"><img src={footer ? "/home/62-237-imgScanMark.svg" : "/home/59-165-imgScanMark.svg"} width="34" height="27" alt="" /><span>Tervory<sup>AI</sup></span></a>;
}
function HomeLinks() { return <><a href="#engine">How it works</a><a href="#squad">The squad</a><a href="#receipt">Receipts</a></>; }

export default function HomePage() {
  return <div className="homepage" id="top">
    <script type="application/ld+json" dangerouslySetInnerHTML={{ __html: JSON.stringify({ "@context": "https://schema.org", "@type": "WebPage", name: homeTitle, url: "https://tervory.com/", description: homeDescription }) }} />
    <a className="skip" href="#main">Skip to content</a>
    <header className="home-nav"><Brand /><nav aria-label="Page"><HomeLinks /></nav><a className="home-button nav-signin" href="https://app.tervory.com/sign-in">Sign in</a></header>
    <main id="main">
      <section className="home-hero" aria-labelledby="home-title"><div className="hero-art" aria-hidden="true"><img src="/home/67-229-imgHeroImageSwap.png" width="1440" height="1040" alt="" fetchPriority="high" /><div className="hero-fades" /></div><div className="hero-content"><h1 id="home-title">{copy["59:243"]}</h1><p className="hero-subline">{copy["59:242"]}</p><ReleaseForm hero /></div></section>
      <section className="home-section engine-section" id="engine"><p className="eyebrow">{copy["67:319"]}</p><h2>{copy["67:320"]}</h2><p className="engine-support">{copy["91:2828"]}</p><p className="engine-hint">{copy["91:2829"]}</p><EngineDiagram /><div className="mechanisms">{mechanisms.map(([title, id], i) => <article key={id}><p className="eyebrow">0{i + 1}</p><h3>{title}</h3><p>{copy[id]}</p></article>)}</div></section>
      <section className="home-section tracker-section"><p className="eyebrow">{copy["111:2593"]}</p><p className="tracker-caption">{copy["111:2599"]}</p><div className="tracker-columns">{[["111:2604", "111:2605"], ["111:2608", "111:2609"], ["111:2612", "111:2613"]].map(([title, body], i) => <article key={title}><p className="eyebrow">0{i + 1}</p><h3>{copy[title]}</h3><p>{copy[body]}</p></article>)}</div></section>
      <section className="home-section manifesto-section"><p className="eyebrow">{copy["111:5055"]}</p><div className="home-split"><h2>{copy["111:5058"]}</h2><div><p className="manifesto-lead">{copy["111:5060"]}</p><p>{copy["111:5061"]}</p></div></div><div className="home-split manifesto-receipts"><h3>{copy["111:5065"]}</h3><p>{copy["111:5067"]}</p></div></section>
      <section className="home-section flagship-section"><div className="home-split tisan-section"><div><p className="eyebrow">Flagship revenue & growth engines</p><p className="eyebrow index">01 · Tisan</p><img src="/home/67-610-imgArtwork1.svg" width="112" height="28" alt="Tisan" loading="lazy" /><h3>{copy["112:8483"]}</h3><p>{copy["112:8484"]}</p></div><div className="tisan-proof"><div className="proof-heading"><p className="eyebrow">Build check before hand-over</p><span className="tag example">Example</span></div>{["Lint", "Type checks", "Tests", "Accessibility", "Lighthouse"].map((label, i) => <div className="proof-row" key={label}><span>{label}</span><small className={i === 4 ? "" : "pass"}>{i === 4 ? <><span className="pass">●</span> e.g. 96 / 100 · 90 or above to ship</> : "✓ Pass"}</small></div>)}<div className="tested-blocks"><p className="eyebrow">{copy["112:8521"]}</p><p>{copy["112:8522"]}</p></div></div></div><div className="rig-handoff" aria-hidden="true"><img src="/home/67-610-imgRigHandOffDashed.svg" width="2" height="150" alt="" loading="lazy" /></div><RigShowcase /></section>
      <section className="home-section trigger-section"><div className="home-split"><div><p className="eyebrow">03 · Trigger</p><img className="trigger-wordmark" src="/home/112-14392-imgLogoTriggerCrmOriginalWhitePng.png" width="153" height="45.6266" alt="Trigger CRM" loading="lazy" /><h3>{copy["112:14396"]}</h3><p>{copy["112:14397"]}</p></div><div className="trigger-features">{[["112:14401", "112:14402"], ["112:14408", "112:14409"]].map(([title, body]) => <article key={title}><h4>{copy[title]}</h4><p>{copy[body]}</p></article>)}</div></div></section>
      <section className="home-section squad-section" id="squad"><p className="eyebrow">The squad</p><h2>What each product does</h2><div className="squad-matrix"><div className="squad-header eyebrow"><span>Specialist</span><span>Purpose</span><span>What it does</span><span>Status</span></div>{products.map(product => <article className="squad-row" key={product.name}><div className="specialist"><img src={`/home/113-3541-${product.artwork}`} width={product.w} height={product.h} style={{ width: product.w, height: product.h }} alt={product.name} loading="lazy" /><p className="eyebrow">{product.name}</p></div><h3>{product.purpose}</h3><div className="squad-description"><p>{copy[product.body]}</p>{product.optional ? <div className="squad-optional"><span className="tag optional">Optional</span><p>{copy[product.optional]}</p></div> : null}</div><div><span className="tag live">Live</span></div></article>)}</div></section>
      <section className="home-section receipt-section" id="receipt"><p className="eyebrow">{copy["114:3837"]}</p><h2>{copy["114:3838"]}</h2><p className="receipt-intro">{copy["114:3840"]}</p><div className="receipt-layout"><div className="receipt-lines">{[["Standard Cost", "114:3855"], ["Vault & Cache Hits ($0.00)", "114:3858"], ["Automatic Model Switching & Batch Savings", "114:3861"], ["Sales Kept by Rig", "114:3864"]].map(([title, id], i) => <article key={id}><h4>{title}</h4><p>{copy[id]}</p>{i === 3 ? <span className="tag optional">Optional</span> : null}</article>)}<p className="export-note">{copy["114:3868"]}</p></div><ReceiptExample /></div></section>
      <section className="home-close"><h2>{copy["62:239"]}</h2><p>{copy["62:240"]}</p><div className="close-actions"><a className="home-button" href="#early">Start Building on Tervory</a><a className="home-button" href="#engine">See How Tank Decides</a></div><div id="early"><ReleaseForm /></div></section>
    </main>
    <footer className="home-footer"><Brand footer /><nav aria-label="Footer"><HomeLinks /></nav><p>© 2026 Tervory AI</p></footer>
  </div>;
}
