export type NavLink = { href: string; label: string };

/** Product header: Chat, Tasks, Data, Skala, Ledger, Tank. Skala and Tank stay for a founder only. */
export function headerLinks(founder: boolean): NavLink[] {
  const links: NavLink[] = [
    { href: "/", label: "Chat" },
    { href: "/tasks", label: "Tasks" },
    { href: "/data", label: "Data" },
  ];
  if (founder) links.push({ href: "/skala", label: "Skala" });
  links.push({ href: "/ledger", label: "Ledger" });
  if (founder) links.push({ href: "/tank", label: "Tank" });
  return links;
}

const OWN_SHELL = ["/sign-in", "/sign-up", "/onboarding"];

/** Sign-in, sign-up, and onboarding do not use the product header. */
export function usesOwnShell(pathname: string): boolean {
  const path = pathname.length > 1 && pathname.endsWith("/") ? pathname.slice(0, -1) : pathname;
  return OWN_SHELL.some((prefix) => path === prefix || path.startsWith(`${prefix}/`));
}
