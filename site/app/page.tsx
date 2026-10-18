import type { Metadata } from "next";
import { SiteFooter } from "./footer";
import { SiteNav } from "./nav";
import { CLERK_SIGN_UP, homeDescription, MAIL } from "../lib/site";

export const metadata: Metadata = {
  alternates: { canonical: "/" },
};

const SIGN_UP = CLERK_SIGN_UP;

const squad = [
  {
    name: "Base",
    mark: "/brand/base-on-light.png",
    body: "Finds, cleans and enriches data. Takes a list of names and returns a list of people and companies you can actually contact — every field sourced and scored.",
    domain: "data · enrichment",
  },
  {
    name: "Tiger",
    mark: "/brand/tiger-on-light.png",
    body: "Watches prices and competitors. Tells you when a rival moves, what they changed and what it means for your margin.",
    domain: "pricing · competitor watch",
  },
  {
    name: "Market Lab",
    mark: "/brand/market-lab-on-light.png",
    body: "Market research on demand. Sizing, segments, demand signals and the sources behind every number.",
    domain: "market research",
  },
  {
    name: "Radix",
    mark: "/brand/radix-on-light.png",
    body: "Security. Reviews what you expose, what you store and who can reach it, and reports in plain language.",
    domain: "security",
  },
  {
    name: "Tisan",
    mark: "/brand/tisan-on-light.png",
    body: "Builds websites and apps from a brief. Ships working pages, not mockups, inside your tenant.",
    domain: "websites · apps",
  },
  {
    name: "Zenas",
    mark: "/brand/zenas-on-light.png",
    body: "Legal. Reads contracts, policies and terms, flags risk and drafts what you need to sign or send.",
    domain: "legal",
  },
];

const ledgerRows = [
  ["14:02:11", "Enrich 412 Colorado FFL holders", "Base", "haiku", "1", "$0.0412", "yes"],
  ["14:02:14", "Dedupe + validate emails", "Base", "code", "3", "$0.0000", "yes"],
  ["13:58:40", "Competitor price check — 9mm, 3 rivals", "Tiger", "own-small", "2", "$0.0009", "yes"],
  ["13:51:07", "Summarise supplier contract clauses", "Zenas", "sonnet", "1", "$0.0188", "no"],
  ["13:49:55", "Market size: reloading supplies, TX", "Market Lab", "cache", "4", "$0.0000", "yes"],
] as const;

const mobileRows = [
  ["Enrich 412 Colorado FFL holders", "base · haiku · rung 1 · $0.0412"],
  ["Dedupe + validate emails", "base · code · rung 3 · $0.0000"],
  ["Competitor price check — 9mm", "tiger · own-small · rung 2 · $0.0009"],
  ["Market size: reloading, TX", "market lab · cache · rung 4 · $0.0000"],
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
            <p className="lead wide-only">
              Tervory is one window where you ask for data, research, price checks, legal reviews or a website.
              Specialists do the work. Every answer comes back with the model that produced it and the price it cost —
              down to the fraction of a cent.
            </p>
            <p className="lead narrow-only">
              One window where you ask for data, research, price checks, legal reviews or a website. Specialists do the
              work. Every answer comes back with the model that produced it and the price it cost.
            </p>
            <div className="hero-actions">
              <a className="btn btn-primary" href={SIGN_UP}>
                Start with your own data
              </a>
            </div>
            <p className="fine wide-only">No credits. No seats. Logins at app.tervory.com.</p>
          </div>
          <div className="window" aria-hidden="true">
            <div className="titlebar">
              <img className="wide-only" src="/brand/window-dots.svg" width={42} height={10} alt="" />
              <div className="tabs">
                <span className="tab tab-on">Chat</span>
                <span className="tab">Tasks</span>
                <span className="tab">Ledger</span>
              </div>
              <p className="tenant">
                <span className="wide-only">Example · workspace</span>
                <span className="narrow-only">Example</span>
              </p>
            </div>
            <div className="thread">
              <div className="bubble-row">
                <p className="request wide-only">
                  Find every licensed firearms dealer in Texas with a working email, and flag the ones that stock
                  reloading supplies.
                </p>
                <p className="request narrow-only">Find every licensed firearms dealer in Texas with a working email.</p>
              </div>
              <div className="answer">
                <p className="example">Example</p>
                <p className="wide-only">
                  Done. 2,418 Texas licensees matched. 1,906 have a verified email, 1,377 have a website, and 212 list
                  reloading supplies. Each row carries its source and a confidence score.
                </p>
                <p className="narrow-only">
                  Done. 2,418 Texas licensees matched, 1,906 with a verified email. Every row has a source and a
                  confidence score.
                </p>
                <div className="preview wide-only">
                  <div className="preview-head">
                    <span>Dealer</span>
                    <span>City</span>
                    <span>Email</span>
                    <span>Conf.</span>
                  </div>
                  <div className="preview-row">
                    <span>Lone Star Arms</span>
                    <span>Austin</span>
                    <span className="verified">verified</span>
                    <span>0.96</span>
                  </div>
                  <div className="preview-row">
                    <span>Hill Country Outfitters</span>
                    <span>Kerrville</span>
                    <span className="verified">verified</span>
                    <span>0.91</span>
                  </div>
                  <div className="preview-row">
                    <span>Brazos Reloading</span>
                    <span>Waco</span>
                    <span className="verified">verified</span>
                    <span>0.88</span>
                  </div>
                </div>
                <div className="answer-meta wide-only">
                  <p className="meta-line">haiku · rung 1 · $0.00003 · 2.7s</p>
                  <div className="feedback">
                    <span className="thumb">👍</span>
                    <span className="thumb">👎</span>
                    <span className="accepted">Accepted</span>
                  </div>
                </div>
                <div className="narrow-only">
                  <p className="meta-line">haiku · rung 1 · $0.00003 · 2.7s</p>
                  <div className="feedback">
                    <span className="thumb">👍</span>
                    <span className="thumb">👎</span>
                    <span className="accepted">Accepted</span>
                  </div>
                </div>
              </div>
              <div className="composer wide-only">
                <span>Ask for anything — data, research, pricing, legal, a site…</span>
                <span className="run">Run</span>
              </div>
            </div>
          </div>
          <p className="fine narrow-only">No credits. No seats. Logins at app.tervory.com.</p>
        </section>

        <section className="section band-subtle" id="how">
          <div className="section-head">
            <p className="eyebrow">How it works</p>
            <h2>One request. Three things happen.</h2>
            <p className="lead wide-only">
              You never pick a model, a vendor or a credit pack. You ask in plain language, and Tervory handles the rest
              — then shows you the receipt.
            </p>
            <p className="lead narrow-only">
              You never pick a model, a vendor or a credit pack. You ask, Tervory handles the rest — then shows you the
              receipt.
            </p>
          </div>
          <div className="steps">
            <article className="step">
              <p className="step-no mono">01</p>
              <div>
                <h3 className="step-title">Ask</h3>
                <p className="step-body wide-only">
                  Type what you need in Chat, or queue it in Tasks. “Enrich this list.” “What are competitors charging?”
                  “Review this contract.” “Build me a landing page.”
                </p>
                <p className="step-body narrow-only">Type what you need in Chat, or queue it in Tasks.</p>
              </div>
            </article>
            <article className="step">
              <p className="step-no mono">02</p>
              <div>
                <h3 className="step-title">Routed through Tank</h3>
                <p className="step-body wide-only">
                  Tank picks the cheapest rung that can do the job well — a frontier model, our own small model, plain
                  code, or a cached answer — and hands the work to the right specialist.
                </p>
                <p className="step-body narrow-only">
                  Tank picks the cheapest rung that can do the job well and hands it to the right specialist.
                </p>
              </div>
            </article>
            <article className="step">
              <p className="step-no mono">03</p>
              <div>
                <h3 className="step-title">Result, with the bill</h3>
                <p className="step-body wide-only">
                  The answer comes back with the model that produced it, what it cost and how long it took. You mark it
                  accepted or not. That decision is what you pay for.
                </p>
                <p className="step-body narrow-only">
                  The answer comes back with the model, the cost and the time. You mark it accepted or not.
                </p>
              </div>
            </article>
          </div>
          <div className="flow">
            <span className="chip">You</span>
            <span className="flow-line" />
            <span className="chip">Workspace</span>
            <span className="flow-line" />
            <span className="chip chip-ink">Tank</span>
            <span className="flow-line" />
            <span className="chip">Specialist</span>
            <span className="flow-line" />
            <span className="chip">Ledger</span>
            <p className="flow-note">Clients see the Workspace and the Ledger. The specialists stay behind the scenes.</p>
          </div>
        </section>

        <section className="section band-ink" id="tank">
          <div className="section-head">
            <p className="eyebrow">Tank · the cost ladder</p>
            <h2 className="wide-only">Every call climbs down a ladder. The second time is cheaper. The tenth is free.</h2>
            <h2 className="narrow-only">The second time is cheaper. The tenth is free.</h2>
            <p className="lead wide-only">
              Tank routes each request to the lowest rung that can answer it well, and logs the result. As Tervory
              learns your work, more of it moves down the ladder — and off the bill.
            </p>
            <p className="lead narrow-only">
              Tank routes each request to the lowest rung that can answer it well. As Tervory learns your work, more of
              it moves down the ladder — and off the bill.
            </p>
          </div>
          <div className="rungs rungs-narrow narrow-only">
            <div className="rung-narrow">
              <div className="bar bar-full w-350">
                <span>Frontier model</span>
                <span>$$$$</span>
              </div>
              <p className="rung-line">
                <span className="rung-label">RUNG 1</span>
                <span>New or hard work. Full cost logged.</span>
              </p>
            </div>
            <div className="rung-narrow">
              <div className="bar w-273">
                <span>Owned small model</span>
                <span>$$</span>
              </div>
              <p className="rung-line">
                <span className="rung-label">RUNG 2</span>
                <span>Seen-before patterns on a model we run. Cents.</span>
              </p>
            </div>
            <div className="rung-narrow">
              <div className="bar w-196">
                <span>Code</span>
                <span>¢</span>
              </div>
              <p className="rung-line">
                <span className="rung-label">RUNG 3</span>
                <span>Tasks that are really rules become code. No model call.</span>
              </p>
            </div>
            <div className="rung-narrow">
              <div className="bar w-119">
                <span>Cache</span>
                <span>free</span>
              </div>
              <p className="rung-line">
                <span className="rung-label">RUNG 4</span>
                <span>Answered before? Served again. Zero spend.</span>
              </p>
            </div>
          </div>
          <div className="rungs rungs-wide">
            <div className="rung-wide">
              <p className="rung-label">RUNG 1</p>
              <div className="track">
                <div className="bar bar-full w-380">
                  <span>Frontier model</span>
                  <span>$$$$</span>
                </div>
              </div>
              <p className="rung-copy">New or hard work. A frontier model answers; the full cost is logged against the request.</p>
            </div>
            <div className="rung-wide">
              <p className="rung-label">RUNG 2</p>
              <div className="track">
                <div className="bar w-296">
                  <span>Owned small model</span>
                  <span>$$</span>
                </div>
              </div>
              <p className="rung-copy">Patterns Tervory has seen before run on a model we own and run ourselves. Cents, not dollars.</p>
            </div>
            <div className="rung-wide">
              <p className="rung-label">RUNG 3</p>
              <div className="track">
                <div className="bar w-213">
                  <span>Code</span>
                  <span>¢</span>
                </div>
              </div>
              <p className="rung-copy">When a task is really a rule — parse, match, validate — it becomes code. No model call at all.</p>
            </div>
            <div className="rung-wide">
              <p className="rung-label">RUNG 4</p>
              <div className="track">
                <div className="bar w-129">
                  <span>Cache</span>
                  <span>free</span>
                </div>
              </div>
              <p className="rung-copy">Answered before? Served again from the cache. Zero model spend, logged as zero.</p>
            </div>
          </div>
          <div className="ladder-note">
            <span className="pill pill-red">Transparent by design</span>
            <p>Every call — whichever rung answered — is written to your Ledger with the model, the cost and whether you accepted it.</p>
          </div>
          <span className="pill pill-red narrow-only">Transparent by design</span>
        </section>

        <section className="section" id="squad">
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
                <img className="wordmark" src={member.mark} alt="" />
                <div>
                  <h3 className="card-title">{member.name}</h3>
                  <p className="card-body">{member.body}</p>
                </div>
                <p className="domain">{member.domain}</p>
              </article>
            ))}
          </div>
          <p className="squad-note wide-only">
            Clients never see the agents. They see results — and the Ledger line for each one.
          </p>
        </section>

        <section className="section band-subtle" id="ledger">
          <div className="section-head">
            <p className="eyebrow">The Ledger</p>
            <h2>You see the bill as it happens.</h2>
            <p className="lead">
              Not at month end. Not as a credit balance. Every call, as it lands: which model answered, what it cost,
              how long it took, and whether you accepted the result. Cost per accepted answer is the only number that
              matters.
            </p>
          </div>
          <div className="tiles-label">
            <p className="example">Example</p>
          </div>
          <div className="tiles">
            <article className="tile">
              <p className="tile-kicker">Calls</p>
              <p className="tile-value">12,406</p>
              <p className="tile-note">this month</p>
            </article>
            <article className="tile">
              <p className="tile-kicker">Accepted</p>
              <p className="tile-value tile-accepted">11,871</p>
              <p className="tile-note">95.7% acceptance</p>
            </article>
            <article className="tile">
              <p className="tile-kicker">Spend</p>
              <p className="tile-value">$38.12</p>
              <p className="tile-note">model spend, all rungs</p>
            </article>
            <article className="tile">
              <p className="tile-kicker">
                <span className="wide-only">Per accepted answer</span>
                <span className="narrow-only">Per accepted</span>
              </p>
              <p className="tile-value tile-cost">$0.0032</p>
              <p className="tile-note">and falling</p>
            </article>
          </div>
          <div className="table-wrap wide-only">
            <table>
              <thead>
                <tr>
                  <th>Time</th>
                  <th>Request</th>
                  <th>Specialist</th>
                  <th>Model</th>
                  <th>Rung</th>
                  <th>Cost</th>
                  <th>Accepted</th>
                </tr>
              </thead>
              <tbody>
                {ledgerRows.map((row) => (
                  <tr key={row[0]}>
                    <td className="num">{row[0]}</td>
                    <td className="request-cell">{row[1]}</td>
                    <td>{row[2]}</td>
                    <td className="num">{row[3]}</td>
                    <td className="num">{row[4]}</td>
                    <td className="num">{row[5]}</td>
                    <td className={row[6] === "yes" ? "yes" : "pending"}>{row[6] === "yes" ? "✓" : "—"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <div className="rows narrow-only">
            {mobileRows.map((row) => (
              <div className="row-card" key={row[1]}>
                <div className="row-top">
                  <span>{row[0]}</span>
                  <span>✓</span>
                </div>
                <p className="row-meta mono">{row[1]}</p>
              </div>
            ))}
          </div>
          <div className="notes">
            <article className="note">
              <h3>Per tenant, per request</h3>
              <p>Every client organisation is its own isolated tenant. Your Ledger only ever shows your work.</p>
            </article>
            <article className="note">
              <h3>Accepted means paid for</h3>
              <p>Mark an answer accepted and it counts. Reject it and it is logged, but it is not a result you bought.</p>
            </article>
            <article className="note">
              <h3>Exportable</h3>
              <p>The Ledger is yours. Download it, reconcile it, show it to your accountant.</p>
            </article>
          </div>
        </section>

        <section className="section" id="pricing">
          <div className="section-head">
            <p className="eyebrow">Pricing</p>
            <h2>Pay for accepted answers. Not credits.</h2>
            <p className="lead">
              Pricing is being finalised. The shape is settled: a small platform fee, plus model spend passed through at
              cost and shown in your Ledger. No per-seat pricing, no credit packs, no surprise overage.
            </p>
          </div>
          <div className="tiers">
            <article className="tier">
              <div>
                <h3 className="tier-name">Starter</h3>
                <p className="tier-blurb">For one business with one dataset to fix.</p>
              </div>
              <div>
                <p className="price">Pricing being finalised</p>
                <p className="price-note">Platform fee + model spend at cost</p>
              </div>
              <div className="rule" />
              <ul className="feature-list">
                <li><span className="mark">—</span> One tenant, one workspace</li>
                <li><span className="mark">—</span> Chat and Tasks</li>
                <li><span className="mark">—</span> Base, Tiger and Market Lab</li>
                <li><span className="mark">—</span> Ledger with full cost visibility</li>
                <li className="wide-only"><span className="mark">—</span> Model spend at cost</li>
              </ul>
              <a className="btn btn-secondary" href={SIGN_UP}>Start with your own data</a>
            </article>
            <article className="tier tier-ink">
              <div>
                <h3 className="tier-name">Business</h3>
                <p className="tier-blurb">For a team that wants all six specialists on call.</p>
              </div>
              <div>
                <p className="price">Pricing being finalised</p>
                <p className="price-note">Platform fee + model spend at cost</p>
              </div>
              <div className="rule" />
              <ul className="feature-list">
                <li><span className="mark">—</span> Everything in Starter</li>
                <li className="wide-only"><span className="mark">—</span> All six specialists, including Tisan and Zenas</li>
                <li className="narrow-only"><span className="mark">—</span> All six specialists</li>
                <li><span className="mark">—</span> Scheduled tasks and watches</li>
                <li><span className="mark">—</span> Team logins at app.tervory.com</li>
                <li className="wide-only"><span className="mark">—</span> Priority routing on Tank</li>
              </ul>
              <a className="btn btn-primary" href={SIGN_UP}>Start</a>
            </article>
            <article className="tier">
              <div>
                <h3 className="tier-name">Case Study partner</h3>
                <p className="tier-blurb">For a business willing to publish a result.</p>
              </div>
              <div>
                <p className="price">Pricing being finalised</p>
                <p className="price-note">Platform fee + model spend at cost</p>
              </div>
              <div className="rule" />
              <ul className="feature-list">
                <li><span className="mark">—</span> A real project, scoped together</li>
                <li className="wide-only"><span className="mark">—</span> Reduced platform fee in exchange for a public case study</li>
                <li className="narrow-only"><span className="mark">—</span> Reduced fee for a public case study</li>
                <li><span className="mark">—</span> Hands-on with the founder</li>
                <li className="wide-only"><span className="mark">—</span> Your results published, with your approval</li>
              </ul>
              <a className="btn btn-ink" href={MAIL}>Talk to the founder</a>
            </article>
          </div>
        </section>
      </main>
      <SiteFooter />
    </>
  );
}
