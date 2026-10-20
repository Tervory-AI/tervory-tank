"use client";

import { useState } from "react";

const links = [
  { href: "/#work", label: "The work" },
  { href: "/#products", label: "Products" },
];

export function SiteNav() {
  const [open, setOpen] = useState(false);

  return (
    <header className="site-nav">
      <div className="nav-bar">
        <a href="/">
          <img className="logo" src="/brand/tervory-logo-display.png" width={186} height={34} alt="Tervory AI" />
        </a>
        <nav className="nav-links" aria-label="Page">
          {links.map((link) => (
            <a key={link.href} href={link.href}>
              {link.label}
            </a>
          ))}
        </nav>
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
      {open ? (
        <nav id="site-menu" className="nav-panel" aria-label="Page">
          {links.map((link) => (
            <a key={link.href} href={link.href} onClick={() => setOpen(false)}>
              {link.label}
            </a>
          ))}
        </nav>
      ) : null}
    </header>
  );
}
