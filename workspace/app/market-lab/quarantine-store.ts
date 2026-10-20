import { existsSync } from "node:fs";
import { asBatch, nextStatus, type QuarantineBatch } from "./quarantine";

type Statement = {
  all: (...args: unknown[]) => unknown[];
  get: (...args: unknown[]) => unknown;
  run: (...args: unknown[]) => unknown;
};
type SqliteHandle = { prepare: (sql: string) => Statement; close: () => void };

function databasePath(): string | null {
  const raw = (process.env.FEEDS_DATABASE_URL ?? "").trim();
  if (!raw || raw.startsWith("postgres://") || raw.startsWith("postgresql://")) return null;
  const path = raw.startsWith("sqlite:///") ? raw.slice("sqlite:///".length) : raw;
  if (!path || path === ":memory:" || !existsSync(path)) return null;
  return path;
}

async function openSqlite(path: string, readOnly: boolean): Promise<SqliteHandle | null> {
  const dynamicImport = new Function("specifier", "return import(specifier)") as (
    specifier: string,
  ) => Promise<{ DatabaseSync: new (filename: string, options: { readOnly: boolean }) => SqliteHandle }>;
  try {
    const loaded = await dynamicImport("node:" + "sqlite");
    return new loaded.DatabaseSync(path, { readOnly });
  } catch {
    return null;
  }
}

export async function readFeedBatches(): Promise<QuarantineBatch[]> {
  const path = databasePath();
  if (!path) return [];
  const db = await openSqlite(path, true);
  if (!db) return [];
  try {
    const rows = db.prepare(
      `SELECT id, series_id, source_id AS source, region, currency, unit, fetched_at, status, reason
       FROM batches ORDER BY created_at, id`,
    ).all();
    return rows.map((row) => asBatch(row as Record<string, unknown>)).filter((row): row is QuarantineBatch => row !== null);
  } catch {
    return [];
  } finally {
    db.close();
  }
}

export async function writeFeedBatch(batchId: string, action: "release" | "reject" | "remove"): Promise<boolean> {
  const path = databasePath();
  if (!path) return false;
  const db = await openSqlite(path, false);
  if (!db) return false;
  try {
    const current = db.prepare("SELECT status FROM batches WHERE id = ?").get(batchId) as { status?: string } | undefined;
    const status = nextStatus(String(current?.status ?? "") as QuarantineBatch["status"], action);
    if (!current || !status) return false;
    if (action === "release") {
      const points = db.prepare("SELECT * FROM batch_points WHERE batch_id = ?").all(batchId) as Array<Record<string, unknown>>;
      for (const point of points) {
        db.prepare(
          `INSERT INTO points (series_id, date, value, fetched_at, revision, source_id, region, currency, unit, batch_id)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
           ON CONFLICT(series_id, date, revision) DO NOTHING`,
        ).run(point.series_id, point.date, point.value, point.fetched_at, point.revision, point.source_id, point.region, point.currency, point.unit, batchId);
      }
    }
    if (action === "remove") {
      db.prepare("DELETE FROM points WHERE batch_id = ?").run(batchId);
    }
    db.prepare("UPDATE batches SET status = ?, reason = CASE WHEN ? = 'pooled' THEN '' ELSE reason END WHERE id = ?").run(status, status, batchId);
    return true;
  } catch {
    return false;
  } finally {
    db.close();
  }
}
