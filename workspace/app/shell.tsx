"use client";

import { OrganizationSwitcher, SignedIn, UserButton, useAuth } from "@clerk/nextjs";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useState } from "react";
import { headerLinks, usesOwnShell } from "./product-nav";

export function Shell({
  founder: initialFounder,
  readFounder,
  children,
}: {
  founder: boolean;
  readFounder: () => Promise<boolean>;
  children: React.ReactNode;
}) {
  const pathname = usePathname() ?? "";
  const { isLoaded, userId } = useAuth();
  const [founder, setFounder] = useState(initialFounder);

  useEffect(() => {
    if (!isLoaded) return;
    let live = true;
    readFounder()
      .then((value) => {
        if (live) setFounder(value);
      })
      .catch(() => {
        if (live) setFounder(false);
      });
    return () => {
      live = false;
    };
  }, [isLoaded, userId, readFounder]);

  if (usesOwnShell(pathname)) return <main>{children}</main>;

  return (
    <>
      <header className="top">
        <Link href="/" className="brand">Tervory</Link>
        <nav>
          {headerLinks(founder).map((link) => (
            <Link key={link.href} href={link.href}>{link.label}</Link>
          ))}
        </nav>
        <SignedIn>
          <div className="who">
            <OrganizationSwitcher hidePersonal afterSelectOrganizationUrl="/" />
            <UserButton />
          </div>
        </SignedIn>
      </header>
      <main>{children}</main>
    </>
  );
}
