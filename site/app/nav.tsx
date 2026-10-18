"use client";

import { useState } from "react";

const links = [
  { href: "#how", label: "How it works" },
  { href: "#tank", label: "Tank" },
  { href: "#case-study", label: "Case study" },
  { href: "#pricing", label: "Pricing" },
];

export function SiteNav() {
  const [open, setOpen] = useState(false);

  return (
    <header className="site-nav">
      <div className="nav-bar">
        <div className="nav-left">
          <a href="#top">
            <img className="logo" src="/brand/tervory-logo-display.png" width={186} height={34} alt="Tervory AI" />
          </a>
          <nav className="nav-links" aria-label="Page">
            {links.map((link) => (
              <a key={link.href} href={link.href}>
                {link.label}
              </a>
            ))}
          </nav>
        </div>
        <div className="nav-right">
          <a className="btn btn-ghost wide-only" href="https://app.tervory.com/sign-in">
            Sign in
          </a>
          <a className="btn btn-ink" href="https://app.tervory.com/sign-up">
            Start
          </a>
          <button
            className="menu-button"
            type="button"
            aria-expanded={open}
            aria-controls="site-menu"
            aria-label={open ? "Close menu" : "Open menu"}
            onClick={() => setOpen((value) => !value)}
          >
            <span />
            <span />
            <span />
          </button>
        </div>
      </div>
      {open ? (
        <nav id="site-menu" className="nav-panel" aria-label="Page">
          {links.map((link) => (
            <a key={link.href} href={link.href} onClick={() => setOpen(false)}>
              {link.label}
            </a>
          ))}
          <a href="https://app.tervory.com/sign-in" onClick={() => setOpen(false)}>
            Sign in
          </a>
        </nav>
      ) : null}
    </header>
  );
}
