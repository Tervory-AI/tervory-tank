import { NextResponse } from "next/server";
import { baseRecords, baseRun } from "@/lib/tank";
import { currentTenant } from "@/lib/tenant";

export const runtime = "nodejs";

export async function GET(req: Request) {
  const taskId = new URL(req.url).searchParams.get("task_id") ?? undefined;
  try {
    const { tenantId } = await currentTenant();
    return NextResponse.json(await baseRecords(tenantId, taskId));
  } catch (err) {
    return NextResponse.json({ error: err instanceof Error ? err.message : "Tank unavailable" }, { status: 502 });
  }
}

// Body: { batch, csv, preview }. CSV header row names the fields; name/address/city/state/zip/phone/website are understood.
export async function POST(req: Request) {
  const body = (await req.json().catch(() => null)) as { batch?: string; csv?: string; preview?: boolean } | null;
  const batch = body?.batch?.trim() ?? "";
  const csv = body?.csv ?? "";
  if (!batch || !csv.trim()) return NextResponse.json({ error: "batch and csv required" }, { status: 400 });
  const records = parseCsv(csv);
  if (records.length === 0) return NextResponse.json({ error: "no rows found; first line must be a header" }, { status: 400 });
  if (records.length > 2000) return NextResponse.json({ error: "max 2000 rows per batch" }, { status: 400 });
  try {
    const { tenantId, userId } = await currentTenant();
    return NextResponse.json(await baseRun(tenantId, userId, batch.slice(0, 120), records, Boolean(body?.preview)), { status: 202 });
  } catch (err) {
    return NextResponse.json({ error: err instanceof Error ? err.message : "Tank unavailable" }, { status: 502 });
  }
}

// Small, forgiving CSV parser: quotes, commas inside quotes, CRLF. Header keys are lower-cased and trimmed.
function parseCsv(text: string): Record<string, string>[] {
  const rows: string[][] = [];
  let row: string[] = [];
  let cell = "";
  let q = false;
  for (let i = 0; i < text.length; i++) {
    const c = text[i];
    if (q) {
      if (c === '"' && text[i + 1] === '"') { cell += '"'; i++; }
      else if (c === '"') q = false;
      else cell += c;
    } else if (c === '"') q = true;
    else if (c === ",") { row.push(cell); cell = ""; }
    else if (c === "\n" || c === "\r") {
      if (c === "\r" && text[i + 1] === "\n") i++;
      row.push(cell); rows.push(row); row = []; cell = "";
    } else cell += c;
  }
  if (cell.length || row.length) { row.push(cell); rows.push(row); }
  const header = (rows.shift() ?? []).map((h) => h.trim().toLowerCase().replace(/\s+/g, "_"));
  return rows
    .filter((r) => r.some((v) => v.trim()))
    .map((r) => Object.fromEntries(header.map((h, i) => [h, (r[i] ?? "").trim()])));
}
