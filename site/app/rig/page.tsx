import type { Metadata } from "next";
import { RigProductDemo } from "./rig-product-demo";
import { rigCopy as copy } from "./rig-copy";
import "./rig.css";

export const metadata: Metadata = {
  title: "Rig — Tervory AI",
  description: copy["56:162"],
  alternates: { canonical: "/rig" },
};

function Brand() {
  return <a className="rp-brand" href="/" aria-label="Tervory AI"><img src="/home/59-165-imgScanMark.svg" width="34" height="27" alt="" /><span>Tervory<sup>AI</sup></span></a>;
}

export default function RigPage() {
  return <div className="rig-product" data-node-id="56:127" data-mobile-node-id="56:798">
    <a className="skip" href="#main">Skip to content</a>
    <div className="rp-dark">
      <header className="rp-nav"><div className="rp-brand-group"><Brand /><span className="rp-product-name">Rig</span></div><nav aria-label="Page"><a href="#how" className="rp-desktop-link">{copy["56:150"]}</a><a href="/" className="rp-desktop-link">{copy["56:151"]}</a><a href="https://app.tervory.com/sign-in">{copy["56:152"]}</a></nav></header>
      <main id="main">
        <section className="rp-hero" aria-labelledby="rig-title" data-node-id="56:154"><div className="rp-statement"><p className="rp-kicker">{copy["56:157"]}</p><h1 id="rig-title"><span className="rp-desktop-wording">{copy["56:159"]}</span><span className="rp-mobile-wording">One item<br />out of stock.</span><span>{copy["56:160"]}</span></h1></div><div className="rp-intro"><p>{copy["56:162"]}</p><div className="rp-actions"><a className="rp-button rp-primary" href="/#early">{copy["I56:164;13:27"]}</a><a href="#how">{copy["56:166"]}</a></div></div></section>
        <RigProductDemo />
      </main>
    </div>
    <section className="rp-benefits rp-section" aria-labelledby="benefits-title" data-node-id="56:560"><div><p className="rp-kicker">{copy["56:562"]}</p><h2 id="benefits-title">{copy["56:563"]}</h2></div><div className="rp-benefit-list">{[["56:568", "56:570", "56:572"], ["56:576", "56:578", "56:580"], ["56:584", "56:586", "56:588"], ["56:592", "56:594", "56:596"]].map(([number,title,body])=><article key={title}><p className="rp-kicker">{copy[number]}</p><h3>{copy[title]}</h3><p>{copy[body]}</p></article>)}</div></section>
    <section className="rp-close rp-section" data-node-id="56:598"><div><p className="rp-kicker">{copy["56:600"]}</p><h2>{copy["56:601"]}</h2></div><div><p>{copy["56:603"]}</p><a className="rp-button" href="/#early">{copy["I56:604;13:69"]}</a></div></section>
    <footer className="rp-footer rp-section" data-node-id="56:606"><div><Brand /><p>{copy["I56:606;44:111"]}</p></div><p className="rp-copyright">{copy["I56:606;44:139"]}</p></footer>
  </div>;
}
