export type NavLink = { href: string; label: string };

export type SquadMember = {
  href: string;
  label: string;
  logo: string;
  /** Intrinsic pixel size of the official file. Display size keeps this ratio. */
  width: number;
  height: number;
  job: string;
  founderOnly: boolean;
};

/** Every squad member. Skala and Tank are founders only. */
export const SQUAD_MEMBERS: readonly SquadMember[] = [
  { href: "/base", label: "Base", logo: "/brand/base-on-dark.png", width: 2322, height: 601, job: "Fills in business records from public pages.", founderOnly: false },
  { href: "/tiger", label: "Tiger", logo: "/brand/tiger-on-dark.png", width: 2607, height: 801, job: "Watches a product page and reports price and stock.", founderOnly: false },
  { href: "/market-lab", label: "Market Lab", logo: "/brand/market-lab-on-dark.png", width: 3685, height: 608, job: "Shows how a market is moving from public feeds.", founderOnly: false },
  { href: "/rig", label: "Rig", logo: "/brand/rig-on-dark.png", width: 1173, height: 651, job: "Looks up parts, catalogues and fits.", founderOnly: false },
  { href: "/tisan", label: "Tisan", logo: "/brand/tisan-on-dark.png", width: 2806, height: 701, job: "Builds a page and checks the result.", founderOnly: false },
  { href: "/radix", label: "Radix", logo: "/brand/radix-on-dark.png", width: 1893, height: 651, job: "Checks code before it ships.", founderOnly: false },
  { href: "/zenas", label: "Zenas", logo: "/brand/zenas-on-dark.png", width: 1970, height: 701, job: "Prepares drafts for a lawyer to review.", founderOnly: false },
  { href: "/skala", label: "Skala", logo: "/brand/skala-on-dark.png", width: 3796, height: 901, job: "Keeps every skill, its versions and its scores.", founderOnly: true },
  { href: "/tank", label: "Tank", logo: "/brand/tank-on-dark.png", width: 2466, height: 601, job: "Holds the models, the keys and the ledger.", founderOnly: true },
];

/** Same list the pages used to expand in the sidebar. The shell shows one Squad button instead. */
export const SQUAD_LINKS: NavLink[] = SQUAD_MEMBERS.map(({ href, label }) => ({ href, label }));

export const TOP_LINKS: readonly NavLink[] = [
  { href: "/", label: "Dashboard" },
  { href: "/matters", label: "Projects" },
  { href: "/", label: "Chats" },
];

export const REST_LINKS: readonly NavLink[] = [
  { href: "/ledger", label: "Ledger" },
  { href: "/billing", label: "Billing" },
  { href: "/tasks", label: "Tasks" },
  { href: "/data", label: "Data" },
  { href: "/prices", label: "Prices" },
  { href: "/onboarding", label: "Settings" },
  { href: "https://tervory.com", label: "Support" },
];

export const FOUNDER_LINKS: readonly NavLink[] = [
  { href: "/admin", label: "Admin" },
  { href: "/admin/feeds", label: "Feeds" },
  { href: "/admin/homes", label: "Homes" },
  { href: "/skala/gold", label: "Training" },
  { href: "/zenas/feeds", label: "Law feeds" },
];

export const REVIEW_LINK: NavLink = { href: "/review", label: "Review" };

/** Signed-in routes that share this shell. */
export const SHELL_ROUTES: readonly string[] = [
  "/",
  "/matters",
  "/tasks",
  "/ledger",
  "/billing",
  "/prices",
  "/data",
  "/onboarding",
  "/base",
  "/tiger",
  "/market-lab",
  "/rig",
  "/tisan",
  "/radix",
  "/zenas",
  "/skala",
  "/skala/gold",
  "/tank",
  "/admin",
  "/admin/feeds",
  "/admin/homes",
  "/zenas/feeds",
  "/review",
];

const OWN_SHELL = ["/sign-in", "/sign-up"];

export function cleanPath(pathname: string): string {
  if (!pathname) return "/";
  return pathname.length > 1 && pathname.endsWith("/") ? pathname.slice(0, -1) : pathname;
}

/** Sign-in and sign-up keep Clerk's own screen. Every other page uses the sidebar. */
export function usesOwnShell(pathname: string): boolean {
  const path = cleanPath(pathname);
  return OWN_SHELL.some((prefix) => path === prefix || path.startsWith(`${prefix}/`));
}

export function squadMembers(founder: boolean): SquadMember[] {
  return SQUAD_MEMBERS.filter((member) => founder || !member.founderOnly);
}

/** Display width at a given height, in the file's own ratio. */
export function logoWidth(member: Pick<SquadMember, "width" | "height">, heightPx = 40): number {
  return Math.round((member.width / member.height) * heightPx);
}

export type PageSection = { title: string; links: NavLink[] };

const PAGE_SECTIONS: { prefix: string; title: string; links: NavLink[] }[] = [
  { prefix: "/admin/feeds", title: "Feeds", links: [{ href: "/admin/feeds", label: "Feed status" }] },
  { prefix: "/admin/homes", title: "Homes", links: [{ href: "/admin/homes", label: "Home region" }] },
  {
    prefix: "/admin",
    title: "Admin",
    links: [
      { href: "/admin?days=30", label: "30 days" },
      { href: "/admin?days=90", label: "90 days" },
      { href: "/admin?days=365", label: "365 days" },
    ],
  },
  { prefix: "/skala/gold", title: "Training", links: [{ href: "/skala/gold", label: "Squad training" }] },
  { prefix: "/zenas/feeds", title: "Law feeds", links: [{ href: "/zenas/feeds", label: "Both regions" }] },
  {
    prefix: "/base",
    title: "Base",
    links: [
      { href: "/base#overview", label: "Overview" },
      { href: "/base#search", label: "Search" },
      { href: "/base#ask", label: "Ask Base" },
      { href: "/base#batches", label: "Batches" },
      { href: "/base#skills", label: "Skills" },
    ],
  },
  { prefix: "/tiger", title: "Tiger", links: [{ href: "/tiger", label: "Overview" }] },
  {
    prefix: "/market-lab",
    title: "Market Lab",
    links: [
      { href: "/market-lab#overview", label: "Overview" },
      { href: "/market-lab#on", label: "Public feeds" },
      { href: "/market-lab#ml-ask", label: "Ask Market Lab" },
      { href: "/market-lab#linked", label: "Linked pages" },
    ],
  },
  { prefix: "/rig", title: "Rig", links: [{ href: "/rig", label: "Overview" }] },
  { prefix: "/tisan", title: "Tisan", links: [{ href: "/tisan", label: "Overview" }] },
  { prefix: "/radix", title: "Radix", links: [{ href: "/radix", label: "Overview" }] },
  { prefix: "/zenas", title: "Zenas", links: [{ href: "/zenas", label: "Overview" }] },
  { prefix: "/skala", title: "Skala", links: [{ href: "/skala", label: "Library" }] },
  { prefix: "/tank", title: "Tank", links: [{ href: "/tank", label: "Overview" }] },
  {
    prefix: "/billing",
    title: "Billing",
    links: [
      { href: "/billing", label: "Plans" },
      { href: "/billing?tab=usage", label: "Usage" },
      { href: "/billing?tab=invoices", label: "Invoices" },
    ],
  },
  { prefix: "/review", title: "Review", links: [{ href: "/review", label: "Queue" }] },
];

function founderPage(pathname: string): boolean {
  const path = cleanPath(pathname);
  return path === "/tank" || path.startsWith("/tank/")
    || path === "/skala" || path.startsWith("/skala/")
    || path === "/admin" || path.startsWith("/admin/")
    || path === "/zenas/feeds" || path.startsWith("/zenas/feeds/");
}

/** The current page's own section, directly under Squad. Null when the page is already in the standard list. */
export function pageSection(pathname: string, founder = false, reviewer = false): PageSection | null {
  const path = cleanPath(pathname);
  if (!founder && founderPage(path)) return null;
  if ((path === "/review" || path.startsWith("/review/")) && !reviewer) return null;
  const match = PAGE_SECTIONS.find((section) => path === section.prefix || path.startsWith(`${section.prefix}/`));
  return match ? { title: match.title, links: match.links } : null;
}

export function pathMatches(href: string, pathname: string): boolean {
  const path = cleanPath(href.split(/[?#]/)[0] || "/");
  const current = cleanPath(pathname);
  if (path === "/") return current === "/";
  return current === path || current.startsWith(`${path}/`);
}

/** Whether a sidebar or section link is the page on screen. */
export function linkIsCurrent(href: string, pathname: string, search = "", hash = ""): boolean {
  const url = new URL(href, "http://tervory.local");
  const path = cleanPath(pathname);
  if (url.pathname !== path) return false;
  if (url.hash) {
    const have = hash || "";
    if (url.hash === "#overview") return have === "" || have === "#overview";
    return have === url.hash;
  }
  const wanted = url.searchParams;
  const have = new URLSearchParams(search.startsWith("?") ? search.slice(1) : search);
  if (wanted.has("tab")) return wanted.get("tab") === have.get("tab");
  if (wanted.has("days")) return wanted.get("days") === (have.get("days") || "90");
  if (path === "/billing") {
    const tab = have.get("tab");
    return !tab || tab === "plans";
  }
  if (path === "/admin") {
    const days = have.get("days");
    return !days || days === "90";
  }
  return true;
}

/** Labels in sidebar order, for tests. Squad is the single pop-out control. */
export function sidebarLabels(pathname: string, founder: boolean, reviewer: boolean): string[] {
  const labels: string[] = [...TOP_LINKS.map((link) => link.label), "Squad"];
  const section = pageSection(pathname, founder, reviewer);
  if (section) labels.push(section.title, ...section.links.map((link) => link.label));
  labels.push(...REST_LINKS.map((link) => link.label));
  if (reviewer) labels.push(REVIEW_LINK.label);
  if (founder) labels.push(...FOUNDER_LINKS.map((link) => link.label));
  return labels;
}

/** Arrow keys move between squad members. Escape closes the pop-out. */
export function squadKey(key: string, index: number, count: number): number | "close" | null {
  if (key === "Escape") return "close";
  if (count <= 0) return null;
  const current = index < 0 ? -1 : index;
  if (key === "ArrowDown") return current < 0 ? 0 : (current + 1) % count;
  if (key === "ArrowUp") return current < 0 ? count - 1 : (current - 1 + count) % count;
  if (key === "Home") return 0;
  if (key === "End") return count - 1;
  return null;
}
