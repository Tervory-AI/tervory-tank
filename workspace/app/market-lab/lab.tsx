"use client";

import { useEffect, useState } from "react";
import { LINKED, OFF_FEEDS, ON_FEEDS, REFRESHED } from "./copy";
import { Sources } from "./sources";

type Section = "overview" | "on" | "off" | "linked";

const PAGE_NAV: { id: Section; label: string }[] = [
  { id: "overview", label: "Overview" },
  { id: "on", label: "On" },
  { id: "off", label: "Off (needs a key)" },
  { id: "linked", label: "Linked pages" },
];

function Tag() {
  return <span className="tag">Example</span>;
}

export function Lab() {
  const [section, setSection] = useState<Section>("overview");
  const [sourcesOpen, setSourcesOpen] = useState(false);
  const [menuOpen, setMenuOpen] = useState(false);

  useEffect(() => {
    function onKey(event: KeyboardEvent) {
      if (event.key !== "Escape") return;
      setSourcesOpen(false);
      setMenuOpen(false);
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  function show(next: Section) {
    setSourcesOpen(false);
    setMenuOpen(false);
    setSection(next);
    document.getElementById(next)?.scrollIntoView({ block: "start" });
  }

  function openSources() {
    setMenuOpen(false);
    setSourcesOpen(true);
  }

  const rootClass = ["market-lab", sourcesOpen ? "sources-open" : "", menuOpen ? "menu-open" : ""].filter(Boolean).join(" ");

  return (
    <div className={rootClass}>
      <header className="topbar">
        <img src="/brand/tervory-logo-reversed.png" alt="Tervory" />
        <button type="button" className="menu" aria-expanded={menuOpen} onClick={() => setMenuOpen((open) => !open)}>
          Menu
        </button>
      </header>

      <aside className="panel" aria-label="Market Lab">
        <div className="panel-top">
          <img src="/brand/tervory-logo-reversed.png" alt="Tervory" />
        </div>
        <div className="panel-own">
          <div className="logo-slot">Market Lab logo, coming later</div>
          <nav aria-label="Market Lab sections">
            {PAGE_NAV.map((item) => (
              <button
                key={item.id}
                type="button"
                className={item.id === section && !sourcesOpen ? "nav on" : "nav"}
                onClick={() => show(item.id)}
              >
                {item.label}
              </button>
            ))}
            <button type="button" className={sourcesOpen ? "nav on" : "nav"} onClick={openSources}>
              Sources
            </button>
          </nav>
        </div>
        <div className="panel-bottom">
          <a className="nav" href="/">Workspace</a>
          <button type="button" className="nav">Help</button>
          <p className="refreshed">
            <span>Last refreshed</span>
            <b>{REFRESHED}</b>
          </p>
        </div>
      </aside>

      <div className="body">
        <header className="head" id="overview">
          <div>
            <div className="page-slot">Market Lab logo, coming later</div>
            <h1>Market Lab</h1>
            <p className="lede">Public data feeds that show how your market is moving, in one place.</p>
          </div>
          <button type="button" className="primary">Refresh feeds</button>
        </header>

        <section className="counts" aria-label="Counts">
          <article className="count">
            <b>9</b>
            <strong>On</strong>
            <p className="fine">Feeds that need no key and are being read.</p>
          </article>
          <article className="count">
            <b>6</b>
            <strong>Off</strong>
            <p className="fine">Feeds that stay off until a key is set.</p>
          </article>
          <article className="count">
            <b>4</b>
            <strong>Linked pages</strong>
            <p className="fine">Pages that use these feeds.</p>
          </article>
        </section>

        <section className="block" id="on">
          <h2>On</h2>
          <p className="intro">These feeds need no key. They read public sources and show their latest value.</p>
          <div className="cards">
            {ON_FEEDS.map((feed) => (
              <article className="card" key={feed.title}>
                <div className="card-top">
                  <h3>{feed.title}</h3>
                  <span className="pill"><i />On</span>
                </div>
                <p>{feed.detail}</p>
                <div className="value-row">
                  <span className="value">{feed.value}</span>
                  <span className="unit">{feed.unit}</span>
                  <Tag />
                </div>
                <p className="meta">{feed.meta}</p>
              </article>
            ))}
          </div>
        </section>

        <section className="block" id="off">
          <h2>Off</h2>
          <p className="intro">These feeds stay off until their key is set by your admin. They are not called.</p>
          <ul className="off-list">
            {OFF_FEEDS.map((feed) => (
              <li key={feed.title}>
                <span className="name">{feed.title}</span>
                <span>Off. Needs a key.</span>
                <span className="env">{feed.env}</span>
                <span className="quiet">Not called</span>
              </li>
            ))}
          </ul>
        </section>

        <section className="block" id="linked">
          <h2>Linked pages</h2>
          <p className="intro">Other pages that use these feeds.</p>
          <div className="linked">
            {LINKED.map((page) => (
              <article key={page.title}>
                <h3>{page.title}</h3>
                <p>{page.detail}</p>
                <span className="open">Open page →</span>
              </article>
            ))}
          </div>
        </section>

        <footer className="foot">
          <p>Public sources only. FRED data is read live and never stored.</p>
          <p className="small">Values marked Example are placeholders in this design.</p>
        </footer>
      </div>

      {sourcesOpen ? <Sources onClose={() => setSourcesOpen(false)} /> : null}
    </div>
  );
}
