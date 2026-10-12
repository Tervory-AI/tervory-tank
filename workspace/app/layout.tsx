import type { Metadata } from "next";
import Link from "next/link";
import "./globals.css";

export const metadata: Metadata = {
  title: "Tervory",
  description: "Ask for work. See what it cost.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>
        <header className="top">
          <Link href="/" className="brand">Tervory</Link>
          <nav>
            <Link href="/">Chat</Link>
            <Link href="/ledger">Ledger</Link>
          </nav>
        </header>
        <main>{children}</main>
      </body>
    </html>
  );
}
