"use client";

import { useState } from "react";
import { CLERK_SIGN_IN, CLERK_SIGN_UP } from "../lib/site";

const links = [
  { href: "/#how", label: "How it works" },
  { href: "/#specialists", label: "Specialists" },
];

export function SiteNav({ signUp = true }: { signUp?: boolean }) {
  const [open, setOpen] = useState(false);

  return (
    <header className="site-nav">
      <div className="nav-bar">
        <div className="nav-left">
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
        </div>
        <div className="nav-right">
          <a className="btn btn-ghost wide-only" href={CLERK_SIGN_IN}>
            Sign in
          </a>
          {signUp ? (
            <a className="btn btn-primary" href={CLERK_SIGN_UP}>
              Sign up
            </a>
          ) : null}
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
          <a href={CLERK_SIGN_IN} onClick={() => setOpen(false)}>
            Sign in
          </a>
        </nav>
      ) : null}
    </header>
  );
}
