import "server-only";
import { mootPublishedMatches } from "@/lib/tank";

export type MatchRecord = {
  matchId: string;
  published: boolean;
  title: string;
  fairnessReading: string;
  judgmentOrder: string;
  judgmentReasons?: string[];
  reveal: string;
  transcript?: { role: string; text: string }[];
  authorities?: { name: string; source_url?: string }[];
  costUsd?: number | null;
};


const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;
const OFFLINE = /fixture|\[TEST\]|CVE-2024-0000|ThreatPayload|00000000-0000-0000-0000/i;

function publicMatch(value: unknown): value is MatchRecord {
  if (!value || typeof value !== "object") return false;
  const row = value as MatchRecord;
  return row.published === true && UUID.test(row.matchId) && typeof row.title === "string"
    && row.title.trim().length > 0 && !OFFLINE.test(JSON.stringify(row));
}

/** Only the room's published platform matches may reach the public watch pages. */
export async function listPublishedMatches(matchId?: string): Promise<MatchRecord[]> {
  try {
    const response = await mootPublishedMatches(matchId);
    return Array.isArray(response.matches) ? response.matches.filter(publicMatch) : [];
  } catch {
    return [];
  }
}

export async function getMatch(matchId: string): Promise<MatchRecord | null> {
  if (!UUID.test(matchId)) return null;
  return (await listPublishedMatches(matchId)).find(row => row.matchId === matchId) ?? null;
}

export async function isPublicWatch(matchId: string): Promise<boolean> {
  return (await getMatch(matchId)) !== null;
}
