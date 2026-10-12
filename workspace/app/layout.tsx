import type { Metadata } from "next";
import Link from "next/link";
import { ClerkProvider, OrganizationSwitcher, SignedIn, UserButton } from "@clerk/nextjs";
import "./globals.css";

export const metadata: Metadata = {
  title: "Tervory",
  description: "Ask for work. See what it cost.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <ClerkProvider>
      <html lang="en">
        <body>
          <header className="top">
            <Link href="/" className="brand">Tervory</Link>
            <nav>
              <Link href="/">Chat</Link>
              <Link href="/tasks">Tasks</Link>
              <Link href="/ledger">Ledger</Link>
            </nav>
            <SignedIn>
              <div className="who">
                <OrganizationSwitcher hidePersonal afterSelectOrganizationUrl="/" />
                <UserButton />
              </div>
            </SignedIn>
          </header>
          <main>{children}</main>
        </body>
      </html>
    </ClerkProvider>
  );
}
