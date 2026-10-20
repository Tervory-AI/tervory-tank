import type { Metadata } from "next";
import type { ReactNode } from "react";

import { site } from "@/lib/site";

import "./tokens.css";
import "./globals.css";

export const metadata: Metadata = {
  title: site.name,
  description: site.name,
};

function Logo() {
  if (!site.logoUrl) {
    return null;
  }
  return (
    // The logo host is chosen per site, so this stays a plain image.
    // eslint-disable-next-line @next/next/no-img-element
    <img src={site.logoUrl} alt={`${site.name} logo`} width={32} height={32} className="h-8 w-8" />
  );
}

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang={site.locale}>
      <body className="bg-paper font-body text-ink">
        <a
          href="#content"
          className="sr-only focus:not-sr-only focus:absolute focus:left-4 focus:top-4 focus:bg-paper focus:px-3 focus:py-2"
        >
          Skip to content
        </a>
        <header className="border-b border-line">
          <nav
            aria-label="Primary"
            className="flex flex-wrap items-center gap-x-2 gap-y-1 px-4 py-3 sm:px-6"
          >
            <Logo />
            <p className="font-heading text-lg">{site.name}</p>
            <ul className="flex flex-wrap items-center gap-1">
              {site.pages.map((page) => (
                <li key={page.href}>
                  <a
                    className="inline-flex min-h-12 min-w-12 items-center justify-center px-3"
                    href={page.href}
                  >
                    {page.label}
                  </a>
                </li>
              ))}
            </ul>
          </nav>
        </header>
        <main id="content" className="px-4 py-8 sm:px-6">
          {children}
        </main>
        <footer className="border-t border-line px-4 py-4 sm:px-6">
          <p>{site.name}</p>
        </footer>
      </body>
    </html>
  );
}
