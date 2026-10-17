import { existsSync } from "node:fs";

import { CATALOG, COMMODITIES, KEY_NAMES, emptyFlags, type KeyFlags } from "./catalog";
import { formatDay, formatMonth } from "./format";
import { buildPage, feedsToCall, type FeedReading, type LinkCheck, type PageModel } from "./model";
import { parseAlerts, parseEcfr, parseEia, parseFred, parseRegister, parseWorldBank, type PriceLine } from "./parse";

const USER_AGENT = "Tervory Market Lab feeds (+https://app.tervory.com)";
const TIMEOUT_MS = 8000;

const LIVE_COPY = new Set(["federal_register", "noaa_alerts", "world_bank_commodities", "eia_diesel", "ecfr"]);

type PointRow = {
  source_id: string;
  ref: string;
  title: string;
  unit: string;
  geo_level: string;
  date: string;
  value: string;
  fetched_at: string;
};

type EventRow = { source_id: string; kind: string; date: string; title: string };
type RunRow = { source_id: string; finished: string; error: string | null };

type Statement = { all: () => unknown[] };
type SqliteHandle = { prepare: (sql: string) => Statement; close: () => void };

export function readFlags(env: NodeJS.ProcessEnv = process.env): KeyFlags {
  const flags = emptyFlags();
  for (const name of KEY_NAMES) flags[name] = Boolean((env[name] ?? "").trim());
  return flags;
}

function databasePath(): { kind: "none" } | { kind: "skip" } | { kind: "file"; path: string } {
  const raw = (process.env.FEEDS_DATABASE_URL ?? "").trim();
  if (!raw) return { kind: "none" };
  if (raw.startsWith("postgres://") || raw.startsWith("postgresql://")) return { kind: "skip" };
  const path = raw.startsWith("sqlite:///") ? raw.slice("sqlite:///".length) : raw;
  if (!path || path === ":memory:") return { kind: "none" };
  return { kind: "file", path };
}

/**
 * Open the feeds file for reading. The specifier is built at runtime so the
 * Next bundle does not try to pack Node's sqlite builtin.
 */
async function openSqlite(path: string): Promise<SqliteHandle> {
  const dynamicImport = new Function("specifier", "return import(specifier)") as (
    specifier: string,
  ) => Promise<{ DatabaseSync: new (filename: string, options: { readOnly: boolean }) => SqliteHandle }>;
  const loaded = await dynamicImport("node:" + "sqlite");
  return new loaded.DatabaseSync(path, { readOnly: true });
}

function asRows<T>(value: unknown[]): T[] {
  return value as T[];
}

function text(value: unknown): string {
  if (value === null || value === undefined) return "";
  return String(value);
}

async function readStore(path: string): Promise<{ readings: Record<string, FeedReading>; links: Record<string, LinkCheck>; sawRows: boolean }> {
  const db = await openSqlite(path);
  try {
    const points = asRows<PointRow>(
      db.prepare(
        `SELECT s.source_id AS source_id, s.ref AS ref, s.title AS title, s.unit AS unit,
                s.geo_level AS geo_level, p.date AS date, CAST(p.value AS TEXT) AS value,
                p.fetched_at AS fetched_at
         FROM points p
         INNER JOIN series s ON s.id = p.series_id
         INNER JOIN (
           SELECT series_id, MAX(date) AS date FROM points GROUP BY series_id
         ) latest ON latest.series_id = p.series_id AND latest.date = p.date`,
      ).all(),
    );
    const events = asRows<EventRow>(
      db.prepare(
        `SELECT source_id, kind, date, title FROM events
         WHERE kind IN ('changed', 'rule', 'regulation')`,
      ).all(),
    );
    const runs = asRows<RunRow>(
      db.prepare(`SELECT source_id, finished, error FROM fetch_runs ORDER BY finished DESC`).all(),
    );
    return shapeStore(points, events, runs);
  } finally {
    db.close();
  }
}

function shapeStore(
  points: PointRow[],
  events: EventRow[],
  runs: RunRow[],
): { readings: Record<string, FeedReading>; links: Record<string, LinkCheck>; sawRows: boolean } {
  const readings: Record<string, FeedReading> = {};
  const bySource = new Map<string, PointRow[]>();
  for (const row of points) {
    const list = bySource.get(row.source_id) ?? [];
    list.push({ ...row, value: text(row.value).trim(), date: text(row.date), fetched_at: text(row.fetched_at) });
    bySource.set(row.source_id, list);
  }
  for (const [sourceId, rows] of bySource) {
    const picked = choosePoints(dedupe(rows));
    if (picked) readings[sourceId] = picked;
  }
  const diesel = readings.eia_diesel;
  if (diesel?.headline) {
    const value = diesel.headline.startsWith("$") ? diesel.headline : `$${diesel.headline}`;
    readings.eia_diesel = {
      ...diesel,
      headline: value,
      detail: diesel.goodAt ? `dollars per gallon, week of ${formatDay(diesel.goodAt)}` : diesel.detail,
    };
  }
  const prices = readings.world_bank_commodities;
  if (prices?.lines?.length) {
    readings.world_bank_commodities = {
      ...prices,
      detail: prices.detail ?? "Metals in US$ per metric ton. Cotton in US cents per pound.",
    };
  }

  const links: Record<string, LinkCheck> = {};
  const rules = new Map<string, EventRow[]>();
  for (const event of events) {
    if (event.kind === "changed") {
      const current = links[event.source_id] ?? { events: 0, latest: null };
      current.events += 1;
      const date = text(event.date).slice(0, 10);
      if (!current.latest || date > current.latest) current.latest = date;
      links[event.source_id] = current;
      continue;
    }
    const list = rules.get(event.source_id) ?? [];
    list.push(event);
    rules.set(event.source_id, list);
  }
  const register = (rules.get("federal_register") ?? [])
    .slice()
    .sort((a, b) => text(b.date).localeCompare(text(a.date)))
    .slice(0, 2);
  if (register.length && !readings.federal_register?.notices?.length) {
    const date = text(register[0]?.date).slice(0, 10);
    readings.federal_register = {
      ...readings.federal_register,
      notices: register.map((event) => ({
        title: text(event.title).trim(),
        meta: `Notice · ${formatDay(text(event.date).slice(0, 10))}`,
      })),
      goodAt: readings.federal_register?.goodAt ?? date,
    };
  }
  const regulation = (rules.get("ecfr") ?? []).slice().sort((a, b) => text(b.date).localeCompare(text(a.date)))[0];
  if (regulation && !readings.ecfr?.detail) {
    const date = text(regulation.date).slice(0, 10);
    readings.ecfr = { ...readings.ecfr, detail: `Current as of ${formatDay(date)}`, goodAt: date };
  }

  const latestRun = new Map<string, RunRow>();
  for (const run of runs) {
    if (!latestRun.has(run.source_id)) latestRun.set(run.source_id, run);
  }
  for (const [sourceId, run] of latestRun) {
    if (!text(run.error).trim()) continue;
    const current = readings[sourceId] ?? {};
    const hasGood = Boolean(current.headline || current.detail || current.lines?.length || current.notices?.length);
    readings[sourceId] = {
      ...current,
      failed: true,
      checkedAt: text(run.finished).slice(0, 10),
      goodAt: hasGood ? current.goodAt ?? null : null,
    };
  }

  return { readings, links, sawRows: points.length + events.length > 0 };
}

function dedupe(rows: PointRow[]): PointRow[] {
  const best = new Map<string, PointRow>();
  for (const row of rows) {
    const key = row.ref;
    const prior = best.get(key);
    if (!prior || row.fetched_at > prior.fetched_at) best.set(key, row);
  }
  return [...best.values()];
}

function lineLabel(row: PointRow): string {
  const known = COMMODITIES.find((item) => item.code === row.ref);
  if (known) return known.label;
  return row.title.trim() || row.ref;
}

function pointDetail(row: PointRow): string {
  const when = formatMonth(row.date);
  return row.unit ? `${row.unit}, ${when}` : when;
}

function choosePoints(rows: PointRow[]): FeedReading | null {
  const national = rows.filter((row) => row.geo_level === "national" && row.value);
  if (!national.length) return null;
  if (national.length === 1) {
    const row = national[0]!;
    return { headline: row.value, detail: pointDetail(row), goodAt: row.date.slice(0, 10) };
  }
  const total = national.find((row) => /total/i.test(row.ref) || /total/i.test(row.title));
  if (total && national.length > 6) {
    return { headline: total.value, detail: pointDetail(total), goodAt: total.date.slice(0, 10) };
  }
  return {
    lines: national.slice(0, 6).map((row) => ({ label: lineLabel(row), value: row.value })),
    goodAt: national[0]?.date.slice(0, 10) ?? null,
  };
}

type FetchResult = { ok: true; body: unknown } | { ok: false };

async function getJson(url: string): Promise<FetchResult> {
  try {
    const response = await fetch(url, {
      headers: { accept: "application/json", "user-agent": USER_AGENT },
      signal: AbortSignal.timeout(TIMEOUT_MS),
      cache: "no-store",
    });
    if (!response.ok) return { ok: false };
    return { ok: true, body: await response.json() };
  } catch {
    return { ok: false };
  }
}

function today(): string {
  return new Date().toISOString().slice(0, 10);
}

function markFailed(current: FeedReading | undefined): FeedReading {
  const prior = current ?? {};
  const hasGood = Boolean(prior.headline || prior.detail || prior.lines?.length || prior.notices?.length);
  return { ...prior, failed: true, checkedAt: today(), goodAt: hasGood ? prior.goodAt || today() : null };
}

function withDollar(value: string): string {
  return value.startsWith("$") ? value : `$${value}`;
}

function registerUrl(): string {
  const params = new URLSearchParams();
  params.append("conditions[agencies][]", "alcohol-tobacco-firearms-and-explosives");
  params.append("conditions[agencies][]", "pipeline-and-hazardous-materials-safety-administration");
  params.set("per_page", "5");
  params.set("order", "newest");
  return `https://www.federalregister.gov/api/v1/documents.json?${params.toString()}`;
}

function eiaUrl(key: string): string {
  const params = new URLSearchParams({
    frequency: "weekly",
    "data[0]": "value",
    "facets[product][]": "EPD2D",
    "facets[duoarea][]": "NUS",
    "sort[0][column]": "period",
    "sort[0][direction]": "desc",
    length: "5",
    api_key: key,
  });
  return `https://api.eia.gov/v2/petroleum/pri/gnd/data/?${params.toString()}`;
}

function fredUrl(series: string, key: string): string {
  const params = new URLSearchParams({
    series_id: series,
    api_key: key,
    file_type: "json",
    sort_order: "desc",
    limit: "5",
  });
  return `https://api.stlouisfed.org/fred/series/observations?${params.toString()}`;
}

function worldBankUrl(code: string): string {
  return `https://api.worldbank.org/v2/country/WLD/indicator/${encodeURIComponent(code)}?format=json&mrv=8`;
}

function secretsFromEnv(): string[] {
  const found: string[] = [];
  for (const name of KEY_NAMES) {
    const value = (process.env[name] ?? "").trim();
    if (value.length >= 8) found.push(value);
  }
  return found;
}

export async function loadMarketLab(): Promise<PageModel> {
  const flags = readFlags();
  const callable = new Set(feedsToCall(flags));
  let readings: Record<string, FeedReading> = {};
  let links: Record<string, LinkCheck> = {};
  let sawRows = false;
  let storeError = false;

  const target = databasePath();
  if (target.kind === "file") {
    if (!existsSync(target.path)) {
      readings = {};
    } else {
      try {
        const stored = await readStore(target.path);
        readings = stored.readings;
        links = stored.links;
        sawRows = stored.sawRows;
      } catch {
        storeError = true;
      }
    }
  }

  let liveRead = false;
  if (!storeError) {
    const tasks: Promise<void>[] = [];
    if (callable.has("federal_register")) {
      tasks.push(
        getJson(registerUrl()).then((result) => {
          if (!result.ok) {
            readings.federal_register = markFailed(readings.federal_register);
            return;
          }
          const parsed = parseRegister(result.body);
          if (!parsed) {
            readings.federal_register = markFailed(readings.federal_register);
            return;
          }
          liveRead = true;
          readings.federal_register = parsed.notices.length
            ? { notices: parsed.notices, goodAt: today() }
            : { detail: "No notices in this check.", goodAt: today() };
        }),
      );
    }
    if (callable.has("noaa_alerts")) {
      tasks.push(
        getJson("https://api.weather.gov/alerts/active?status=actual").then((result) => {
          if (!result.ok) {
            readings.noaa_alerts = markFailed(readings.noaa_alerts);
            return;
          }
          const parsed = parseAlerts(result.body);
          if (!parsed) {
            readings.noaa_alerts = markFailed(readings.noaa_alerts);
            return;
          }
          liveRead = true;
          const name = parsed.example && parsed.example.length <= 80 ? parsed.example : null;
          readings.noaa_alerts = {
            headline: String(parsed.count),
            detail: name ? `active alerts · ${name}` : "active alerts",
            goodAt: today(),
          };
        }),
      );
    }
    if (callable.has("world_bank_commodities")) {
      tasks.push(
        Promise.all(COMMODITIES.map(async (item) => ({ item, result: await getJson(worldBankUrl(item.code)) }))).then(
          (results) => {
            const lines: PriceLine[] = [];
            let failed = false;
            for (const { item, result } of results) {
              if (!result.ok) {
                failed = true;
                continue;
              }
              const parsed = parseWorldBank(result.body, item.code);
              if (!parsed) continue;
              lines.push({ label: parsed.label, value: parsed.value });
            }
            if (!lines.length) {
              readings.world_bank_commodities = markFailed(readings.world_bank_commodities);
              return;
            }
            liveRead = true;
            readings.world_bank_commodities = {
              lines,
              detail: "Metals in US$ per metric ton. Cotton in US cents per pound.",
              goodAt: today(),
              failed: failed && lines.length === 0,
            };
          },
        ),
      );
    }
    if (callable.has("ecfr")) {
      tasks.push(
        getJson("https://www.ecfr.gov/api/versioner/v1/structure/current/title-49.json").then((result) => {
          if (!result.ok) {
            readings.ecfr = markFailed(readings.ecfr);
            return;
          }
          const parsed = parseEcfr(result.body);
          if (!parsed) {
            readings.ecfr = markFailed(readings.ecfr);
            return;
          }
          liveRead = true;
          readings.ecfr = { detail: `Current as of ${formatDay(parsed.date)}`, goodAt: parsed.date };
        }),
      );
    }
    if (callable.has("eia_diesel")) {
      const key = (process.env.EIA_API_KEY ?? "").trim();
      tasks.push(
        getJson(eiaUrl(key)).then((result) => {
          if (!result.ok) {
            readings.eia_diesel = markFailed(readings.eia_diesel);
            return;
          }
          const parsed = parseEia(result.body);
          if (!parsed) {
            readings.eia_diesel = markFailed(readings.eia_diesel);
            return;
          }
          liveRead = true;
          readings.eia_diesel = {
            headline: withDollar(parsed.value),
            detail: `dollars per gallon, week of ${formatDay(parsed.period)}`,
            goodAt: parsed.period,
          };
        }),
      );
    }
    if (flags.FRED_API_KEY) {
      const key = (process.env.FRED_API_KEY ?? "").trim();
      for (const item of CATALOG) {
        if (item.kind !== "fred" || !item.fredSeries || !callable.has(item.id)) continue;
        const series = item.fredSeries;
        const id = item.id;
        tasks.push(
          getJson(fredUrl(series, key)).then((result) => {
            if (!result.ok) {
              readings[id] = markFailed(readings[id]);
              return;
            }
            const parsed = parseFred(result.body);
            if (!parsed) {
              readings[id] = markFailed(readings[id]);
              return;
            }
            liveRead = true;
            readings[id] = { headline: parsed.value, goodAt: parsed.date };
          }),
        );
      }
    }
    await Promise.all(tasks);
  }

  for (const id of Object.keys(readings)) {
    if (!callable.has(id)) delete readings[id];
  }

  const page = buildPage(flags, readings, links, {
    error: storeError,
    refreshedAt: liveRead || sawRows ? new Date().toISOString() : null,
  });
  return scrubSecrets(page, secretsFromEnv());
}

export function scrubSecrets<T>(value: T, secrets: string[]): T {
  const usable = secrets.filter((secret) => secret.length >= 8);
  const walk = (input: unknown): unknown => {
    if (typeof input === "string") {
      let text = input;
      for (const secret of usable) {
        if (text.includes(secret)) text = text.split(secret).join("");
      }
      return text.replace(/(api_key|apikey|token)=([^&\s]+)/gi, "$1=");
    }
    if (Array.isArray(input)) return input.map(walk);
    if (input && typeof input === "object") {
      const out: Record<string, unknown> = {};
      for (const [key, item] of Object.entries(input)) out[key] = walk(item);
      return out;
    }
    return input;
  };
  return walk(value) as T;
}
