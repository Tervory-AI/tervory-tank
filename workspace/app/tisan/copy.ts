/** Example copy for the Tisan page. Placeholders stay placeholders. No secrets. */

export const MASK = "•••• saved 17 Oct";
export const REFRESHED = "Today, 7:30 AM PT · Example";

export type View = "overview" | "builds" | "design" | "tests" | "settings";
export type Filter = "all" | "Build" | "Page" | "Test";
export type Dialog = "none" | "build" | "plugins";
export type PluginTab = "keys" | "files" | "links" | "mcp";
export type Kind = "Build" | "Page" | "Test";

export type SearchRecord = {
  id: string;
  kind: Kind;
  title: string;
  detail: string;
  view: View;
};

export const PAGE_NAV: { id: View; label: string }[] = [
  { id: "overview", label: "Overview" },
  { id: "builds", label: "Builds" },
  { id: "design", label: "Design" },
  { id: "tests", label: "Tests" },
  { id: "settings", label: "Settings" },
];

export const FILTERS: { id: Filter; label: string }[] = [
  { id: "all", label: "All" },
  { id: "Build", label: "Builds" },
  { id: "Page", label: "Pages" },
  { id: "Test", label: "Tests" },
];

/** Records search can find. A query of "landing" matches the five rows in the search frame. */
export const RECORDS: SearchRecord[] = [
  { id: "b98", kind: "Build", title: "Tervory landing page", detail: "Draft pull request #98 · Today, 7:12 AM PT · Tests passed", view: "builds" },
  { id: "b96", kind: "Build", title: "Starter site test gate", detail: "Draft pull request #96 · Yesterday, 4:40 PM PT · Tests passed", view: "builds" },
  { id: "blanding", kind: "Build", title: "Tervory landing page", detail: "Branch tisan/landing · Yesterday, 11:05 AM PT · Code checks failed", view: "builds" },
  { id: "b44", kind: "Build", title: "Starter site", detail: "Pull request #44 · 15 Oct · Tests passed", view: "builds" },
  { id: "page", kind: "Page", title: "Landing — Desktop & Mobile", detail: "Locked Figma page · saved copy in the repo", view: "design" },
  { id: "screens", kind: "Test", title: "Screens at 390, 768 and 1440 wide", detail: "Tervory landing page · Passed", view: "tests" },
  { id: "lh", kind: "Test", title: "Lighthouse", detail: "Tervory landing page · 100 in all four scores", view: "tests" },
  { id: "lint", kind: "Test", title: "Lint and type checks", detail: "eslint and tsc · Passed", view: "tests" },
  { id: "unit", kind: "Test", title: "Unit tests", detail: "vitest · Passed", view: "tests" },
  { id: "radix", kind: "Test", title: "Radix scan", detail: "Runs before any deploy · Not ready", view: "tests" },
];

export function showsChat(view: View, query: string, filter: Filter): boolean {
  return view === "overview" && query.trim() === "" && filter === "all";
}

export function showsResults(view: View, query: string, filter: Filter): boolean {
  return view === "overview" && !showsChat(view, query, filter);
}

/** Which control is the single red button. Chat views use Send. The pop-up uses its own confirm. */
export function primaryAction(input: {
  view: View;
  query: string;
  filter: Filter;
  dialog: Dialog;
  pluginTab: PluginTab;
  mobile: boolean;
}): "send" | "start" | "start-confirm" | "save-key" | "choose-files" | "add-link" | "add-connection" {
  if (input.dialog === "build") return "start-confirm";
  if (input.dialog === "plugins") {
    if (input.mobile) return "save-key";
    if (input.pluginTab === "files") return "choose-files";
    if (input.pluginTab === "links") return "add-link";
    if (input.pluginTab === "mcp") return "add-connection";
    return "save-key";
  }
  if (showsChat(input.view, input.query, input.filter)) return "send";
  return "start";
}

export function searchRecords(query: string, filter: Filter): SearchRecord[] {
  const q = query.trim().toLowerCase();
  return RECORDS.filter((row) => {
    if (filter !== "all" && row.kind !== filter) return false;
    if (!q) return true;
    return `${row.kind} ${row.title} ${row.detail}`.toLowerCase().includes(q);
  });
}

export function groupMeta(kind: Kind, count: number): { heading: string; countLabel: string } {
  if (kind === "Build") return { heading: "Builds", countLabel: count === 1 ? "1 build" : `${count} builds` };
  if (kind === "Page") return { heading: "Pages", countLabel: count === 1 ? "1 page" : `${count} pages` };
  const runs = count === 1 ? "1 test run" : `${count} test runs`;
  return { heading: "Tests", countLabel: runs };
}

export function resultSummary(query: string, count: number): string {
  const noun = count === 1 ? "result" : "results";
  const q = query.trim();
  if (!q) return `${count} ${noun} · Example`;
  return `${count} ${noun} for “${q}” · Example`;
}

export type Citation = { title: string; detail: string; view: View };

export const OPENING_THREAD: { role: "user" | "assistant"; text: string; when?: string; sources?: Citation[] }[] = [
  {
    role: "user",
    text: "Build a one-page site for the Boise gunsmith from the saved landing page.",
  },
  {
    role: "assistant",
    text: "Done. The site is built on a new branch and passed all six checks. Draft pull request #112 is open for your review. Deploy stays off until the Radix scan is ready.",
    when: "Answered 7:14 AM PT",
    sources: [
      { title: "Saved Figma page", detail: "Landing — Desktop & Mobile · saved copy in the repo", view: "design" },
      { title: "Build log", detail: "Branch tisan/boise-gunsmith · Example", view: "builds" },
      { title: "Test gate report", detail: "Lint, unit, build, three screen sizes, accessibility, Lighthouse 100 · Example", view: "tests" },
      { title: "Draft pull request #112", detail: "tervory-tank · Example", view: "builds" },
    ],
  },
];

export function replyTo(text: string): { text: string; when: string; sources: Citation[] } {
  const hits = searchRecords(text, "all").slice(0, 4);
  if (hits.length === 0) {
    return {
      text: "Example only. Nothing was sent, and no build was started. None of the example builds, pages or tests match that.",
      when: "Answered just now",
      sources: [],
    };
  }
  return {
    text: "Example only. Nothing was sent, and no build was started. These records are the closest match.",
    when: "Answered just now",
    sources: hits.map((hit) => ({ title: hit.title, detail: `${hit.detail} · Example`, view: hit.view })),
  };
}

export const STEPS = [
  { n: "1", title: "Brief", tone: "solid" as const, state: "Done", detail: "Short brief read." },
  { n: "2", title: "Design", tone: "solid" as const, state: "Done", detail: "Saved Figma page read. No live call." },
  { n: "3", title: "Build", tone: "solid" as const, state: "Done", detail: "Next.js site built." },
  { n: "4", title: "Tests", tone: "solid" as const, state: "Passed", detail: "All checks passed." },
  { n: "5", title: "Scan", tone: "quiet" as const, state: "Not ready", detail: "Radix scan is not ready yet." },
  { n: "6", title: "Deploy", tone: "quiet" as const, state: "Off", detail: "Waits for a clean scan." },
];

export const RECENT = [
  { title: "Tervory landing page", detail: "Draft pull request #98 · Today · Example", tests: "Passed", scan: "Not ready", deploy: "Off", when: "Today, 7:12 AM PT" },
  { title: "Starter site test gate", detail: "Draft pull request #96 · Example", tests: "Passed", scan: "Not ready", deploy: "Off", when: "Yesterday, 4:40 PM PT" },
  { title: "Starter site", detail: "Pull request #44 · Example", tests: "Passed", scan: "Not ready", deploy: "Off", when: "15 Oct" },
];

export const ALL_BUILDS = [
  { title: "Tervory landing page", detail: "Draft pull request #98 · Today, 7:12 AM PT · Example", code: "Passed", screens: "Passed", access: "Passed", light: "100", scan: "Not ready", deploy: "Off" },
  { title: "Starter site test gate", detail: "Draft pull request #96 · Yesterday, 4:40 PM PT · Example", code: "Passed", screens: "Passed", access: "Passed", light: "100", scan: "Not ready", deploy: "Off" },
  { title: "Tervory landing page", detail: "Branch tisan/landing · Yesterday, 11:05 AM PT · Example", code: "Failed", screens: "Not run", access: "Not run", light: "—", scan: "Not run", deploy: "Off" },
  { title: "Starter site", detail: "Pull request #44 · 15 Oct · Example", code: "Passed", screens: "Passed", access: "Passed", light: "98", scan: "Not ready", deploy: "Off" },
];

export const RULES = [
  { title: "Saved page only", detail: "Tisan reads the locked Figma page saved in the repo. It does not call Figma live." },
  { title: "No public internet", detail: "Tisan has no route to the public internet while it builds." },
  { title: "Draft pull requests", detail: "Every build ends as a draft pull request for you to review. Tisan does not merge." },
  { title: "Deploy on a clean scan", detail: "Tisan deploys only after the tests pass and the scan comes back clean." },
];

export const COLOURS = [
  { name: "Navy", hex: "#001840", swatch: "navy" },
  { name: "Red, one primary action", hex: "#E80008", swatch: "red" },
  { name: "Lines", hex: "#B8BFD0", swatch: "lines" },
  { name: "Tint", hex: "#F4F6FB", swatch: "tint" },
];

export const SPACING = [4, 8, 12, 16, 24, 32, 48];

export const GAPS = [
  { title: "No spacing variables", detail: "The page has no named spacing.", did: "Used the spacing from the layout and listed it." },
  { title: "No font family or weights", detail: "Text styles do not name them.", did: "Left them out of the type tokens." },
  { title: "No h4 to h6", detail: "Only three heading sizes exist.", did: "Did not invent the missing sizes." },
  { title: "No button hover or disabled states", detail: "Only the resting button is drawn.", did: "Kept the resting state only." },
];

export const COMPONENTS = [
  { title: "Button", detail: "Primary and secondary", built: "components/Button.tsx" },
  { title: "Squad card", detail: "One card per Squad member", built: "components/SquadCard.tsx" },
  { title: "Logo", detail: "Tervory logo, navy and white", built: "Logo files used as they are" },
];

export const SCORES = [
  { score: "100", label: "Performance" },
  { score: "100", label: "Accessibility" },
  { score: "100", label: "Best practices" },
  { score: "100", label: "SEO" },
];

export const CHECKS = [
  { title: "Lint and type checks", tool: "eslint and tsc", proves: "The code is tidy and the types line up.", result: "Passed", tone: "solid" as const },
  { title: "Unit tests", tool: "vitest", proves: "Small parts of the site work on their own.", result: "Passed", tone: "solid" as const },
  { title: "Production build", tool: "next build", proves: "The site builds the way it will run live.", result: "Passed", tone: "solid" as const },
  { title: "Screens", tool: "Playwright at 390, 768 and 1440 wide", proves: "Pages open and work on phone, tablet and desktop.", result: "Passed", tone: "solid" as const },
  { title: "Accessibility", tool: "axe at each screen size", proves: "No accessibility errors on any page.", result: "Passed", tone: "solid" as const },
  { title: "Lighthouse", tool: "90 or above in all four scores", proves: "The site is fast and well built.", result: "Passed", tone: "solid" as const },
  { title: "Radix scan", tool: "Runs before any deploy", proves: "No secrets or known risks ship with the site.", result: "Not ready", tone: "quiet" as const },
];

export type KeyId = "github" | "packages" | "coolify" | "radix" | "preview";

export const KEYS: { id: KeyId; name: string; detail: string; env: string; saved: boolean }[] = [
  { id: "github", name: "GitHub", detail: "Opens draft pull requests. Tisan never merges.", env: "GITHUB_TOKEN", saved: true },
  { id: "packages", name: "Package cache", detail: "Packages already in the room. No public fetch.", env: "PACKAGES_TOKEN", saved: true },
  { id: "coolify", name: "Coolify", detail: "Deploy key. Stays off until the scan is clean.", env: "COOLIFY_TOKEN", saved: false },
  { id: "radix", name: "Radix", detail: "Scan before any deploy.", env: "RADIX_TOKEN", saved: false },
  { id: "preview", name: "Preview", detail: "A private look at the built site.", env: "PREVIEW_TOKEN", saved: false },
];

export const FILES = [
  { name: "landing-copy.csv", type: "CSV", size: "48 rows", when: "16 Oct", status: "Processed", map: true },
  { name: "squad-roster.xlsx", type: "XLSX", size: "12 rows", when: "15 Oct", status: "Needs checking", map: false },
  { name: "page-brief.pdf", type: "PDF", size: "4 pages", when: "12 Oct", status: "Processed", map: false },
  { name: "nav-labels.csv", type: "CSV", size: "18 rows", when: "10 Oct", status: "Needs checking", map: true },
];

export const LINKS = [
  { label: "Tervory marketing page", host: "www.example.com", checked: "Today, 7:00 AM", status: "Watching" },
  { label: "Contact page draft", host: "contact.example.com", checked: "Yesterday", status: "Changed" },
  { label: "Preview host", host: "preview.example", checked: "16 Oct", status: "Couldn't reach" },
];

export const CONNECTIONS = [
  { name: "Saved design", host: "files.example", detail: "The locked page in the repo", status: "Connected", used: "Today, 7:10 AM" },
  { name: "Radix scan", host: "scan.example", detail: "Secrets and known risks before deploy", status: "Needs sign-in", used: "Never" },
  { name: "Draft requests", host: "git.example", detail: "Opens a draft for you to review", status: "Error", used: "14 Oct" },
];

export const PLUGIN_TABS: { id: PluginTab; label: string }[] = [
  { id: "keys", label: "API keys" },
  { id: "files", label: "Files" },
  { id: "links", label: "Source links" },
  { id: "mcp", label: "MCP connections" },
];

export function toneFor(label: string): "solid" | "quiet" {
  return label === "Passed" || label === "Done" || label === "Connected" || label === "Watching" || label === "Processed" ? "solid" : "quiet";
}
