import { NextResponse } from "next/server";
import { ledgerSummary } from "@/lib/tank";

export const runtime = "nodejs";

export async function GET(req: Request) {
  const days = Number(new URL(req.url).searchParams.get("days") ?? "30") || 30;
  try {
    return NextResponse.json(await ledgerSummary(days));
  } catch (err) {
    return NextResponse.json({ error: err instanceof Error ? err.message : "Tank unavailable" }, { status: 502 });
  }
}
