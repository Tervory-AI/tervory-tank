export type NavLink = { href: string; label: string };

/** Every squad page. The left panel on each page links to this list. */
export const SQUAD_LINKS: NavLink[] = [
  { href: "/base", label: "Base" },
  { href: "/tiger", label: "Tiger" },
  { href: "/market-lab", label: "Market Lab" },
  { href: "/rig", label: "Rig" },
  { href: "/tisan", label: "Tisan" },
  { href: "/radix", label: "Radix" },
  { href: "/zenas", label: "Zenas" },
  { href: "/skala", label: "Skala" },
  { href: "/tank", label: "Tank" },
];

/** Product header. Skala and Tank stay in the founder list. The other squad pages are on every header. */
export function headerLinks(founder: boolean): NavLink[] {
  const links: NavLink[] = [
    { href: "/", label: "Chat" },
    { href: "/tasks", label: "Tasks" },
    { href: "/data", label: "Data" },
  ];
  if (founder) links.push({ href: "/skala", label: "Skala" });
  links.push({ href: "/ledger", label: "Ledger" });
  if (founder) links.push({ href: "/tank", label: "Tank" });
  for (const link of SQUAD_LINKS) {
    if (!links.some((item) => item.href === link.href)) links.push(link);
  }
  return links;
}

const OWN_SHELL = [
  "/sign-in",
  "/sign-up",
  "/onboarding",
  "/base",
  "/tiger",
  "/market-lab",
  "/rig",
  "/tisan",
  "/radix",
  "/zenas",
];

/** Sign-in, sign-up, onboarding, and the squad pages that bring their own frame. */
export function usesOwnShell(pathname: string): boolean {
  const path = pathname.length > 1 && pathname.endsWith("/") ? pathname.slice(0, -1) : pathname;
  return OWN_SHELL.some((prefix) => path === prefix || path.startsWith(`${prefix}/`));
}
