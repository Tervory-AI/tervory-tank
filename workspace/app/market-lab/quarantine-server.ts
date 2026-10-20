import "server-only";
import { auth } from "@clerk/nextjs/server";
import { isListedFounder } from "../review/founder";
import { asBatch, type QuarantineBatch } from "./quarantine";
import { readFeedBatches } from "./quarantine-store";

export async function loadQuarantine(): Promise<QuarantineBatch[] | null> {
  try {
    const { userId } = await auth();
    if (!isListedFounder(userId, process.env.TERVORY_ADMIN_USER_IDS)) return null;
  } catch {
    return null;
  }
  const fromFile = await readFeedBatches();
  const key = process.env.TANK_KEY_MARKET_LAB ?? "";
  if (!key) return fromFile;
  try {
    const host = process.env.MARKET_LAB_URL ?? "http://agent-market-lab:8000";
    const response = await fetch(`${host}/quarantine`, {
      headers: { "X-Tank-Key": key },
      cache: "no-store",
    });
    if (!response.ok) return fromFile;
    const body = (await response.json()) as { batches?: unknown };
    if (!Array.isArray(body.batches)) return fromFile;
    const remote = body.batches
      .map((row) => (row && typeof row === "object" ? asBatch(row as Record<string, unknown>) : null))
      .filter((row): row is QuarantineBatch => row !== null);
    return remote.length ? remote : fromFile;
  } catch {
    return fromFile;
  }
}
