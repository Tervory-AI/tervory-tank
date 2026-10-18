"use client";

import { usePathname } from "next/navigation";
import { SQUAD_LINKS } from "./product-nav";

/** The same squad list on every left panel. Each page keeps its own tabs beside this. */
export function SquadLinks({
  className = "squad-nav",
  linkClassName,
}: {
  className?: string;
  linkClassName?: string;
}) {
  const pathname = usePathname() ?? "";
  return (
    <nav className={className} aria-label="Squad">
      {SQUAD_LINKS.map((link) => {
        const current = pathname === link.href || pathname.startsWith(`${link.href}/`);
        return (
          <a key={link.href} className={linkClassName} href={link.href} aria-current={current ? "page" : undefined}>
            {link.label}
          </a>
        );
      })}
    </nav>
  );
}
