import {
  CADENCE_LABEL,
  CATALOG,
  FEATURED_IDS,
  LINK_GROUPS,
  type CatalogItem,
  type KeyFlags,
  type KeyName,
} from "./catalog";
import { formatDay, formatRefreshed } from "./format";
import type { Notice, PriceLine } from "./parse";

/** One feed's latest reading. Off feeds are ignored even if a reading is passed in. */
export type FeedReading = {
  headline?: string | null;
  detail?: string | null;
  lines?: PriceLine[];
  notices?: Notice[];
  failed?: boolean;
  checkedAt?: string | null;
  goodAt?: string | null;
};

export type LinkCheck = {
  events: number;
  latest?: string | null;
};

export type OnCard = {
  id: string;
  title: string;
  summary: string;
  sourceLabel: string;
  cadence: string;
  headline: string | null;
  detail: string | null;
  lines: PriceLine[];
  notices: Notice[];
  problem: string | null;
};

export type OffRow = {
  id: string;
  title: string;
  summary: string;
  keyName: string;
};

export type LinkPage = {
  id: string;
  label: string;
  href: string;
  note: string;
};

export type LinkGroupView = {
  id: string;
  title: string;
  cadence: string;
  pages: LinkPage[];
};

export type PageModel = {
  refreshedLabel: string;
  onCount: number;
  offCount: number;
  linkedCount: number;
  onEmpty: boolean;
  loadError: boolean;
  featured: OnCard[];
  cards: OnCard[];
  off: OffRow[];
  groups: LinkGroupView[];
};

const FRED_TITLE = "FRED economic series (7)";
const FRED_SUMMARY =
  "Freight index and its monthly change, plus copper, zinc, lead, cotton and diesel prices. Read live from FRED, never stored.";

const GRID_ORDER = [
  "noaa_alerts",
  "listing_counts",
  "check_counts",
  "ecfr",
  "world_bank_commodities",
  "bts_freight",
  "port_los_angeles",
  "licence_holders",
  "census_population",
  "census_trade",
  "noaa_climate",
  "legiscan",
];

const OFF_COPY_ORDER = ["census_population", "census_trade", "noaa_climate", "legiscan", "eia_diesel"];

const byId = new Map(CATALOG.map((item) => [item.id, item]));

export function isOn(item: CatalogItem, flags: KeyFlags): boolean {
  if (!item.keyName) return true;
  return Boolean(flags[item.keyName as KeyName]);
}

/** Copy feeds and FRED series whose key is set. Linked pages are not called. */
export function feedsToCall(flags: KeyFlags): string[] {
  return CATALOG.filter((item) => item.kind !== "linked" && isOn(item, flags)).map((item) => item.id);
}

function clean(value: string | null | undefined): string | null {
  if (typeof value !== "string") return null;
  const text = value.trim();
  return text ? text : null;
}

/** A failed check with no earlier success contributes no number. */
function shownReading(reading: FeedReading | undefined): FeedReading {
  const source = reading ?? {};
  if (source.failed && !clean(source.goodAt)) {
    return { failed: true, checkedAt: source.checkedAt ?? null };
  }
  return source;
}

function problemFor(reading: FeedReading): string | null {
  if (!reading.failed) return null;
  const checked = clean(reading.checkedAt);
  const good = clean(reading.goodAt);
  if (checked && good) {
    return `The last check on ${formatDay(checked)} did not work. The source did not answer in time. Showing the last good data, from ${formatDay(good)}.`;
  }
  if (checked) {
    return `The last check on ${formatDay(checked)} did not work. The source did not answer in time.`;
  }
  return "The last check did not work. The source did not answer in time.";
}

function cardFor(item: CatalogItem, reading: FeedReading | undefined): OnCard {
  const shown = shownReading(reading);
  return {
    id: item.id,
    title: item.title,
    summary: item.summary,
    sourceLabel: item.sourceLabel,
    cadence: CADENCE_LABEL[item.cadence],
    headline: clean(shown.headline),
    detail: clean(shown.detail),
    lines: shown.lines ?? [],
    notices: shown.notices ?? [],
    problem: problemFor(shown),
  };
}

function hasContent(card: OnCard): boolean {
  return Boolean(card.headline || card.detail || card.lines.length || card.notices.length || card.problem);
}

function fredCard(flags: KeyFlags, readings: Record<string, FeedReading>): OnCard | null {
  const series = CATALOG.filter((item) => item.kind === "fred");
  const first = series[0];
  if (!first || !isOn(first, flags)) return null;
  const lines: PriceLine[] = [];
  let problem: string | null = null;
  for (const item of series) {
    const shown = shownReading(readings[item.id]);
    if (!problem && shown.failed) problem = problemFor(shown);
    if (shown.lines && shown.lines.length) {
      lines.push(...shown.lines);
      continue;
    }
    const headline = clean(shown.headline);
    if (headline) lines.push({ label: item.short || item.title, value: headline });
  }
  return {
    id: "fred",
    title: FRED_TITLE,
    summary: FRED_SUMMARY,
    sourceLabel: "FRED",
    cadence: "Monthly",
    headline: null,
    detail: lines.length ? "Read live, not stored." : null,
    lines,
    notices: [],
    problem,
  };
}

function linkNote(item: CatalogItem, check: LinkCheck | undefined): string {
  if (item.linkNote) return item.linkNote;
  const events = check?.events ?? 0;
  const latest = clean(check?.latest);
  if (events <= 0 || !latest) return "Not checked yet";
  if (events === 1) return `Checked ${formatDay(latest)}`;
  return `Changed ${formatDay(latest)}`;
}

export function buildPage(
  flags: KeyFlags,
  readings: Record<string, FeedReading>,
  linkChecks: Record<string, LinkCheck>,
  options: { error?: boolean; refreshedAt?: string | null } = {},
): PageModel {
  const fredOn = CATALOG.some((item) => item.kind === "fred" && isOn(item, flags));
  const onCopy = CATALOG.filter((item) => item.kind === "copy" && isOn(item, flags)).length;
  const offCopy = CATALOG.filter((item) => item.kind === "copy" && !isOn(item, flags)).length;
  const fredCount = CATALOG.filter((item) => item.kind === "fred").length;
  const linked = CATALOG.filter((item) => item.kind === "linked");

  const featured: OnCard[] = [];
  for (const id of FEATURED_IDS) {
    const item = byId.get(id);
    if (!item || !isOn(item, flags)) continue;
    featured.push(cardFor(item, readings[id]));
  }

  const cards: OnCard[] = [];
  for (const id of GRID_ORDER) {
    const item = byId.get(id);
    if (!item || item.kind !== "copy" || !isOn(item, flags)) continue;
    if ((FEATURED_IDS as readonly string[]).includes(id)) continue;
    cards.push(cardFor(item, readings[id]));
  }
  const fred = fredCard(flags, readings);
  if (fred) cards.push(fred);

  const onCards = [...featured, ...cards];
  const loadError = Boolean(options.error);
  const off: OffRow[] = [];
  if (!fredOn) {
    off.push({ id: "fred", title: FRED_TITLE, summary: FRED_SUMMARY, keyName: "FRED_API_KEY" });
  }
  for (const id of OFF_COPY_ORDER) {
    const item = byId.get(id);
    if (!item || isOn(item, flags)) continue;
    off.push({ id: item.id, title: item.title, summary: item.summary, keyName: item.keyName });
  }

  const groups: LinkGroupView[] = LINK_GROUPS.map((group) => ({
    id: group.id,
    title: group.title,
    cadence: group.cadence,
    pages: linked
      .filter((item) => item.group === group.id)
      .map((item) => ({
        id: item.id,
        label: item.linkLabel || item.title,
        href: item.href || "",
        note: linkNote(item, linkChecks[item.id]),
      })),
  }));

  const refreshedAt = options.refreshedAt ?? "";
  return {
    refreshedLabel: refreshedAt ? formatRefreshed(refreshedAt) : "Not refreshed yet",
    onCount: onCopy + (fredOn ? fredCount : 0),
    offCount: offCopy + (fredOn ? 0 : fredCount),
    linkedCount: linked.length,
    onEmpty: !loadError && onCards.every((card) => !hasContent(card)),
    loadError,
    featured,
    cards,
    off,
    groups,
  };
}
