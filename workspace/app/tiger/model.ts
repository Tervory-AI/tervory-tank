import type { TigerAlert, TigerObservation, TigerWatch } from "@/lib/tank";
import { everyLabel, stockLabel, watchTitle } from "../prices/format";
import type { ReadStatus } from "./copy";

export type Section = "overview" | "alerts" | "watch" | "history" | "unread";

export const SECTIONS: { id: Section; label: string }[] = [
  { id: "overview", label: "Overview" },
  { id: "alerts", label: "Alerts" },
  { id: "watch", label: "Watch list" },
  { id: "history", label: "History" },
  { id: "unread", label: "Can't read" },
];

export type ProductRow = {
  id: string;
  name: string;
  store: string;
  path: string;
  url: string;
  price: string;
  stock: string;
  checked: string;
  status: ReadStatus;
  every: string;
  alertOn: string;
  live: boolean;
};

export type ReadRow = { id: string; when: string; product: string; price: string; stock: string };
export type AlertRow = {
  id: string;
  when: string;
  product: string;
  store: string;
  kind: "Price" | "Stock";
  before: string;
  now: string;
  change: string;
  today: boolean;
  live?: boolean;
};
export type UnreadRow = { id: string; product: string; store: string; url: string; why: string; since: string };

export type TigerData = {
  example: boolean;
  refreshed: string;
  watchedCount: number;
  changesToday: number;
  unreadCount: number;
  products: ProductRow[];
  reads: ReadRow[];
  alerts: AlertRow[];
  unread: UnreadRow[];
  listNote: string | null;
};

export type SearchHit = {
  query: string;
  products: ProductRow[];
  reads: ReadRow[];
  alerts: AlertRow[];
  total: number;
};

const SKIPPED = new Set(["blocked", "robots", "error", "none", "unread"]);

/** No watched pages yet. Counts stay at zero and no sample rows are shown. */
export function emptyData(): TigerData {
  return {
    example: false,
    refreshed: "",
    watchedCount: 0,
    changesToday: 0,
    unreadCount: 0,
    products: [],
    reads: [],
    alerts: [],
    unread: [],
    listNote: null,
  };
}

export function sectionFrom(value: string | undefined): Section {
  const found = SECTIONS.find((item) => item.id === value);
  return found ? found.id : "overview";
}

function blob(parts: Array<string | null | undefined>): string {
  return parts.filter(Boolean).join(" ").toLowerCase();
}

export function searchTiger(data: TigerData, raw: string): SearchHit | null {
  const query = raw.trim();
  const q = query.toLowerCase();
  if (!q) return null;
  const products = data.products.filter((row) => blob([row.name, row.store, row.path, row.stock, row.price, row.status]).includes(q));
  const reads = data.reads.filter((row) => blob([row.product, row.price, row.stock, row.when]).includes(q));
  const alerts = data.alerts.filter((row) => blob([row.product, row.store, row.kind, row.before, row.now, row.change, row.when]).includes(q));
  return { query, products, reads, alerts, total: products.length + reads.length + alerts.length };
}

function hostOf(url: string): string {
  try {
    return new URL(url).host;
  } catch {
    return url;
  }
}

function pathOf(url: string): string {
  try {
    const parsed = new URL(url);
    return `${parsed.host}${parsed.pathname}`.replace(/\/$/, "");
  } catch {
    return url;
  }
}

function priceText(price: string | number | null, currency: string | null): string {
  if (price == null || price === "") return "—";
  const amount = Number(price);
  const body = Number.isFinite(amount) ? amount.toFixed(2) : String(price);
  const code = (currency ?? "").trim().toUpperCase();
  if (!code || code === "USD" || code === "$") return `$${body}`;
  return `${code} ${body}`;
}

function stockText(value: string | null): string {
  if (!value) return "—";
  const known = stockLabel(value);
  if (known) return known;
  if (value.toLowerCase().includes("can't read") || value.toLowerCase().includes("cant read")) return "—";
  return value.length <= 40 ? value : "—";
}

function whenLabel(ts: string): string {
  const date = new Date(ts);
  if (Number.isNaN(date.getTime())) return ts;
  const formatted = new Intl.DateTimeFormat("en-US", {
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
    timeZone: "UTC",
  }).format(date);
  return `${formatted} UTC`;
}

function latestByUrl(rows: TigerObservation[]): Map<string, TigerObservation> {
  const found = new Map<string, TigerObservation>();
  for (const row of rows) {
    const current = found.get(row.url);
    if (!current || row.ts > current.ts) found.set(row.url, row);
  }
  return found;
}

function latestAlert(alerts: TigerAlert[], url: string): TigerAlert | null {
  const rows = alerts.filter((row) => row.url === url).sort((a, b) => b.ts.localeCompare(a.ts));
  return rows[0] ?? null;
}

function unread(obs: TigerObservation | undefined): boolean {
  if (!obs) return false;
  const method = (obs.method ?? "").toLowerCase();
  if (SKIPPED.has(method) || method === "can't read") return true;
  const stock = (obs.availability ?? "").toLowerCase();
  return stock.includes("can't read") || stock.includes("cant read");
}

function whyUnread(obs: TigerObservation): string {
  const method = obs.method ?? "";
  if (method === "blocked") return "The store blocked automatic checks. Recorded and skipped.";
  if (method === "robots") return "This site asks not to be checked automatically.";
  return "The page could not be read clearly.";
}

function statusFor(obs: TigerObservation | undefined, alert: TigerAlert | null): ReadStatus {
  if (!obs) return "Not checked";
  if (unread(obs)) return "Can't read";
  if (alert?.kind === "price") return "Price changed";
  if (alert?.kind === "stock") return "Stock changed";
  return "Read";
}

function changeText(alert: TigerAlert): string {
  if (alert.kind === "price") {
    const before = priceText(alert.before, null);
    const after = priceText(alert.after, null);
    const down = Number(alert.after) < Number(alert.before);
    return down ? `Price went down from ${before} to ${after}` : `Price went up from ${before} to ${after}`;
  }
  const before = stockText(alert.before);
  const after = stockText(alert.after);
  if (after === "Out of stock") return "Now out of stock. Was in stock.";
  return `Stock changed from ${before} to ${after}.`;
}

function isToday(ts: string, now: Date): boolean {
  const date = new Date(ts);
  if (Number.isNaN(date.getTime())) return false;
  return date.toISOString().slice(0, 10) === now.toISOString().slice(0, 10);
}

export function fromTiger(
  watches: TigerWatch[],
  observations: TigerObservation[],
  alerts: TigerAlert[],
  now = new Date(),
): TigerData {
  const latest = latestByUrl(observations);
  const products: ProductRow[] = watches.map((watch) => {
    const obs = latest.get(watch.url);
    const alert = latestAlert(alerts, watch.url);
    const status = statusFor(obs, alert);
    return {
      id: watch.id,
      name: watchTitle(watch),
      store: hostOf(watch.url),
      path: pathOf(watch.url),
      url: watch.url,
      price: obs && !unread(obs) ? priceText(obs.price, obs.currency) : "—",
      stock: obs && !unread(obs) ? stockText(obs.availability) : "—",
      checked: obs ? whenLabel(obs.ts) : "Not yet",
      status,
      every: everyLabel(watch.every),
      alertOn: watch.alert_price !== false
        ? (watch.alert_stock !== false ? "Price and stock" : "Price")
        : (watch.alert_stock !== false ? "Stock" : "No alerts"),
      live: true,
    };
  });
  const reads: ReadRow[] = observations
    .filter((row) => !SKIPPED.has(row.method ?? "") && row.price != null && row.price !== "")
    .sort((a, b) => b.ts.localeCompare(a.ts))
    .slice(0, 40)
    .map((row) => ({
      id: row.id,
      when: whenLabel(row.ts),
      product: products.find((item) => item.url === row.url)?.name ?? hostOf(row.url),
      price: priceText(row.price, row.currency),
      stock: stockText(row.availability),
    }));
  const alertRows: AlertRow[] = [...alerts]
    .sort((a, b) => b.ts.localeCompare(a.ts))
    .map((alert) => ({
      id: alert.id,
      when: whenLabel(alert.ts),
      product: products.find((item) => item.url === alert.url)?.name ?? hostOf(alert.url),
      store: hostOf(alert.url),
      kind: alert.kind === "stock" ? "Stock" : "Price",
      before: alert.kind === "price" ? priceText(alert.before, null) : stockText(alert.before),
      now: alert.kind === "price" ? priceText(alert.after, null) : stockText(alert.after),
      change: changeText(alert),
      today: isToday(alert.ts, now),
      live: true,
    }));
  const unreadRows: UnreadRow[] = products
    .filter((row) => row.status === "Can't read")
    .map((row) => {
      const obs = latest.get(row.url);
      return {
        id: row.id,
        product: row.name,
        store: row.store,
        url: row.url,
        why: obs ? whyUnread(obs) : "The page could not be read clearly.",
        since: row.checked,
      };
    });
  const newest = observations.map((row) => row.ts).sort().at(-1);
  return {
    example: false,
    refreshed: newest ? whenLabel(newest) : "Not yet",
    watchedCount: products.length,
    changesToday: alertRows.filter((row) => row.today).length,
    unreadCount: unreadRows.length,
    products,
    reads,
    alerts: alertRows,
    unread: unreadRows,
    listNote: null,
  };
}
