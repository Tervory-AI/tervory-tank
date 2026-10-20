"use client";

import { OrganizationSwitcher, SignedIn, UserButton, useAuth } from "@clerk/nextjs";
import Link from "next/link";
import { usePathname, useSearchParams } from "next/navigation";
import { Suspense, useEffect, useState } from "react";
import {
  FOUNDER_LINKS,
  REST_LINKS,
  REVIEW_LINK,
  TOP_LINKS,
  linkIsCurrent,
  pageSection,
  usesOwnShell,
  type NavLink,
} from "./product-nav";
import { InAppShell, SquadFounderProvider, SquadLinks } from "./squad-links";

export type ShellAccess = { founder: boolean; reviewer: boolean };

export function Shell({
  founder: initialFounder,
  reviewer: initialReviewer,
  readAccess,
  children,
}: {
  founder: boolean;
  reviewer: boolean;
  readAccess: () => Promise<ShellAccess>;
  children: React.ReactNode;
}) {
  const pathname = usePathname() ?? "";
  const { isLoaded, userId } = useAuth();
  const [founder, setFounder] = useState(initialFounder);
  const [reviewer, setReviewer] = useState(initialReviewer);
  const [menu, setMenu] = useState(false);

  useEffect(() => {
    if (!isLoaded) return;
    let live = true;
    readAccess()
      .then((value) => {
        if (!live) return;
        setFounder(value.founder);
        setReviewer(value.reviewer);
      })
      .catch(() => {
        if (!live) return;
        setFounder(false);
        setReviewer(false);
      });
    return () => {
      live = false;
    };
  }, [isLoaded, userId, readAccess]);

  useEffect(() => {
    setMenu(false);
  }, [pathname]);

  if (usesOwnShell(pathname)) return (
    <SquadFounderProvider founder={founder}>
      <main>{children}</main>
    </SquadFounderProvider>
  );

  return (
    <SquadFounderProvider founder={founder}>
      <InAppShell.Provider value={true}>
        <div className={menu ? "app-shell product menu-open" : "app-shell product"}>
          <a className="shell-skip" href="#shell-content">Skip to content</a>
          <header className="shell-mobile">
            <img src="/brand/tervory-logo-reversed.png" alt="Tervory" width={218} height={40} />
            <button type="button" className="shell-menu" id="shell-menu" aria-expanded={menu} aria-controls="app-sidebar" onClick={() => setMenu(true)}>Menu</button>
          </header>
          {menu ? (
            <button type="button" className="shell-dim" aria-label="Close menu" onClick={() => setMenu(false)} />
          ) : null}
          <Suspense fallback={<ShellBar pathname={pathname} search="" hash="" founder={founder} reviewer={reviewer} menu={menu} onClose={() => setMenu(false)} />}>
            <ShellBarLive founder={founder} reviewer={reviewer} menu={menu} onClose={() => setMenu(false)} />
          </Suspense>
          <div id="shell-content" className="shell-main">
            <main>{children}</main>
          </div>
        </div>
      </InAppShell.Provider>
    </SquadFounderProvider>
  );
}

function ShellBarLive({
  founder,
  reviewer,
  menu,
  onClose,
}: {
  founder: boolean;
  reviewer: boolean;
  menu: boolean;
  onClose: () => void;
}) {
  const pathname = usePathname() ?? "";
  const search = useSearchParams();
  const [hash, setHash] = useState("");

  useEffect(() => {
    const read = () => setHash(window.location.hash);
    read();
    window.addEventListener("hashchange", read);
    return () => window.removeEventListener("hashchange", read);
  }, [pathname]);

  return (
    <ShellBar
      pathname={pathname}
      search={search.toString()}
      hash={hash}
      founder={founder}
      reviewer={reviewer}
      menu={menu}
      onClose={onClose}
    />
  );
}

function ShellBar({
  pathname,
  search,
  hash,
  founder,
  reviewer,
  menu,
  onClose,
}: {
  pathname: string;
  search: string;
  hash: string;
  founder: boolean;
  reviewer: boolean;
  menu: boolean;
  onClose: () => void;
}) {
  const section = pageSection(pathname, founder, reviewer);
  const current = (href: string) => linkIsCurrent(href, pathname, search, hash);

  return (
    <aside id="app-sidebar" className={menu ? "shell-side open" : "shell-side"} aria-label="Sidebar">
      <div className="shell-brand">
        <img src="/brand/tervory-logo-reversed.png" alt="Tervory" width={218} height={40} />
        <button type="button" className="shell-side-close" id="shell-side-close" onClick={onClose}>Close</button>
      </div>
      <SignedIn>
        <div className="shell-account">
          <OrganizationSwitcher hidePersonal afterSelectOrganizationUrl="/" />
          <UserButton />
        </div>
      </SignedIn>
      <nav className="shell-nav" aria-label="Workspace">
        {TOP_LINKS.map((link) => (
          <ShellLink key={link.label} link={link} current={current(link.href)} onClose={onClose} />
        ))}
      </nav>
      <SquadLinks active founder={founder} />
      {section ? (
        <nav className="shell-nav shell-own" aria-label={section.title}>
          <p className="shell-kicker">{section.title}</p>
          {section.links.map((link) => (
            <ShellLink key={link.href + link.label} link={link} current={current(link.href)} onClose={onClose} />
          ))}
        </nav>
      ) : null}
      <div className="shell-spacer" />
      <nav className="shell-nav" aria-label="Account">
        {REST_LINKS.map((link) => (
          <ShellLink key={link.label} link={link} current={current(link.href)} onClose={onClose} />
        ))}
        {reviewer ? <ShellLink link={REVIEW_LINK} current={current(REVIEW_LINK.href)} onClose={onClose} /> : null}
        {founder ? FOUNDER_LINKS.map((link) => (
          <ShellLink key={link.href} link={link} current={current(link.href)} onClose={onClose} />
        )) : null}
      </nav>
    </aside>
  );
}

function ShellLink({ link, current, onClose }: { link: NavLink; current: boolean; onClose: () => void }) {
  const external = link.href.startsWith("http");
  if (external) {
    return (
      <a href={link.href} target="_blank" rel="noreferrer">
        {link.label}
        <span className="shell-sr"> (opens a new tab)</span>
      </a>
    );
  }
  return (
    <Link href={link.href} aria-current={current ? "page" : undefined} onClick={onClose}>
      {link.label}
    </Link>
  );
}
