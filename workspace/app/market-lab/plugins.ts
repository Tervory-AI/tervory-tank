import type { KeyFlags, KeyName } from "./catalog";
import type { OnCard, PageModel } from "./model";

/** Popup title. The word Sources is reserved for answer references. */
export const POPUP_TITLE = "Plugins";
export const REFERENCE_LABEL = "Sources";

export const STUB_KEY =
  "Saving keys in Plugins is not connected yet. A key set in the environment still turns its feed on. Nothing was stored.";
export const STUB_FILE = "Uploads are not stored yet. Nothing was saved.";
export const STUB_LINK = "Source links are not stored yet. Nothing was saved.";
export const STUB_MCP = "Connections are not stored yet. Nothing was saved.";

export const PLUGIN_TABS = ["API keys", "Files", "Source links", "MCP connections"] as const;
export type PluginTab = (typeof PLUGIN_TABS)[number];

export type PublicKeyRow = {
  name: KeyName;
  title: string;
  summary: string;
  connected: boolean;
};

const KEY_ROWS: { name: KeyName; title: string; summary: string }[] = [
  {
    name: "FRED_API_KEY",
    title: "FRED",
    summary: "Freight index and its monthly change, plus copper, zinc, lead, cotton and diesel. Read live, never stored.",
  },
  { name: "CENSUS_API_KEY", title: "Census", summary: "Census population and Census trade." },
  { name: "EIA_API_KEY", title: "EIA", summary: "Weekly on-highway diesel price." },
  { name: "NOAA_TOKEN", title: "NOAA", summary: "Monthly climate. Weather alerts need no key." },
  { name: "LEGISCAN_API_KEY", title: "LegiScan", summary: "Status changes on state bills about firearms and ammunition." },
];

/** Pages a person can open. Taken from the feed list, not invented. */
const FEED_HREF: Record<string, string> = {
  listing_counts: "https://www.atf.gov/firearms/listing-federal-firearms-licensees",
  check_counts: "https://www.fbi.gov/file-repository/cjis/nics_firearm_checks_-_month_year_by_state.pdf",
  census_population: "https://api.census.gov/data/2023/acs/acs5",
  legiscan: "https://legiscan.com/legiscan",
  federal_register: "https://www.federalregister.gov/api/v1/documents.json",
  ecfr: "https://www.ecfr.gov/current/title-49",
  census_trade: "https://api.census.gov/data/timeseries/intltrade/imports/hs",
  eia_diesel: "https://api.eia.gov/v2/petroleum/pri/gnd/data/",
  world_bank_commodities: "https://api.worldbank.org/v2/country/WLD/indicator/PCOPPUSDM?format=json",
  noaa_alerts: "https://api.weather.gov/alerts/active",
  noaa_climate: "https://www.ncei.noaa.gov/cdo-web/webservices/v2",
  port_los_angeles: "https://www.portoflosangeles.org/business/statistics/container-statistics",
  bts_freight: "https://www.bts.gov/",
  licence_holders: "https://www.fws.gov/program/wildlife-and-sport-fish-restoration/apportionments-and-licenses-data",
  fred: "https://fred.stlouisfed.org/",
};

/** What the browser is allowed to know: which keys are set, never the key itself. */
export function publicKeyRows(flags: KeyFlags): PublicKeyRow[] {
  return KEY_ROWS.map((row) => ({ ...row, connected: Boolean(flags[row.name]) }));
}

export function clientPluginState(flags: KeyFlags) {
  return {
    title: POPUP_TITLE,
    keys: publicKeyRows(flags),
    files: [] as [],
    links: [] as [],
    connections: [] as [],
  };
}

export type AnswerSource = { name: string; href: string | null; date: string | null };

function hasReading(card: OnCard): boolean {
  return Boolean(card.headline || card.detail || card.lines.length || card.notices.length);
}

function blob(parts: (string | null | undefined)[]): string {
  return parts.filter((part): part is string => Boolean(part && part.trim())).join(" ");
}

function matches(text: string, query: string): boolean {
  const q = query.trim().toLowerCase();
  if (!q) return true;
  const hay = text.toLowerCase();
  if (hay.includes(q)) return true;
  const tokens = q.split(/[^a-z0-9]+/).filter((token) => token.length > 2);
  return tokens.length > 0 && tokens.every((token) => hay.includes(token));
}

function onCards(model: PageModel): OnCard[] {
  return [...model.featured, ...model.cards];
}

export function searchMarketLab(model: PageModel, query: string): { onIds: string[]; offIds: string[]; linkIds: string[] } {
  const on = onCards(model);
  const links = model.groups.flatMap((group) =>
    group.pages.map((page) => ({ ...page, group: group.title, lead: group.lead })),
  );
  if (!query.trim()) {
    return { onIds: on.map((card) => card.id), offIds: model.off.map((row) => row.id), linkIds: links.map((page) => page.id) };
  }
  return {
    onIds: on
      .filter((card) => matches(blob([card.title, card.summary, card.sourceLabel, card.headline, card.detail]), query))
      .map((card) => card.id),
    offIds: model.off.filter((row) => matches(blob([row.title, row.summary, row.keyName]), query)).map((row) => row.id),
    linkIds: links
      .filter((page) => matches(blob([page.label, page.href, page.note, page.group, page.lead]), query))
      .map((page) => page.id),
  };
}

function sourceName(card: OnCard): string {
  if (!card.sourceLabel || card.title.includes(card.sourceLabel)) return card.title;
  return `${card.title} (${card.sourceLabel})`;
}

/** References actually attached to an answer. Unread and unmatched feeds are left out. */
export function groundQuestion(model: PageModel, question: string): { sources: AnswerSource[]; context: string } {
  const readable = onCards(model).filter(hasReading);
  const matched = readable.filter((card) =>
    matches(blob([card.title, card.summary, card.sourceLabel, card.headline, card.detail, ...card.lines.flatMap((line) => [line.label, line.value])]), question),
  );
  const picked = matched.slice(0, 4);
  const sources: AnswerSource[] = picked.map((card) => ({
    name: sourceName(card),
    href: FEED_HREF[card.id] ?? null,
    date: card.asOf,
  }));
  const context = picked
    .map((card) => {
      const bits = blob([
        card.headline,
        card.detail,
        ...card.lines.map((line) => `${line.label}: ${line.value}`),
        ...card.notices.map((notice) => notice.title),
        card.problem,
      ]);
      return `${sourceName(card)}${card.asOf ? ` (${card.asOf})` : ""}: ${bits}`;
    })
    .join("\n");
  return { sources, context };
}
