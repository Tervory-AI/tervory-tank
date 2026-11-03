import type { ReactNode } from "react";

import { site } from "@/lib/site";

import "./tokens.css";
import "./globals.css";

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang={site.locale}>
      <body className="bg-paper font-body text-ink">
        <main id="content" className="px-4 py-8 sm:px-6">
          {children}
        </main>
      </body>
    </html>
  );
}
